import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord
from valve_runner import run_zone, finish_run, stop_zone


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, application_rate_mm_per_min=2.0))
        s.add(Schedule(zone_id=1))
        s.commit()
        yield s


def make_relay():
    relay = MagicMock()
    relay.status = {"valve_1": "closed", "valve_2": "closed"}
    return relay


def test_run_zone_opens_valve_and_creates_record(session):
    relay = make_relay()
    scheduler = MagicMock()
    run = run_zone(1, 300, "manual", 7.5, 0.0, relay, session, scheduler)
    relay.open_valve.assert_called_once_with(1)
    assert run.id is not None
    assert run.zone_id == 1
    assert run.trigger == "manual"
    assert run.status == "running"
    assert run.et_deficit_mm == pytest.approx(7.5)


def test_run_zone_schedules_auto_close(session):
    relay = make_relay()
    scheduler = MagicMock()
    run_zone(1, 300, "scheduled", 5.0, 1.0, relay, session, scheduler)
    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args.kwargs
    assert call_kwargs["id"] == "close_zone_1"
    assert call_kwargs["replace_existing"] is True


def test_finish_run_closes_valve_and_marks_completed():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.commit()
        run = RunRecord(zone_id=1, started_at=datetime.now(), trigger="manual", status="running")
        s.add(run)
        s.commit()
        run_id = run.id

    relay = make_relay()
    with patch("valve_runner.get_relay", return_value=relay), \
         patch("valve_runner.engine", engine):
        finish_run(run_id, 1)

    relay.close_valve.assert_called_once_with(1)
    with Session(engine) as s:
        updated = s.get(RunRecord, run_id)
        assert updated.status == "completed"
        assert updated.ended_at is not None
        assert updated.duration_seconds is not None


def test_stop_zone_marks_run_interrupted(session):
    relay = make_relay()
    scheduler = MagicMock()
    run = run_zone(1, 300, "manual", 5.0, 0.0, relay, session, scheduler)
    stopped = stop_zone(1, relay, session, scheduler)
    relay.close_valve.assert_called_with(1)
    scheduler.remove_job.assert_called_once_with("close_zone_1")
    assert stopped.status == "interrupted"
    assert stopped.ended_at is not None


def test_stop_zone_returns_none_if_no_active_run(session):
    relay = make_relay()
    scheduler = MagicMock()
    result = stop_zone(1, relay, session, scheduler)
    assert result is None

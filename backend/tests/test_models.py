import pytest
from datetime import datetime
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_zone_config_defaults(session):
    zone = ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0)
    session.add(zone)
    session.commit()
    session.refresh(zone)
    assert zone.et_coefficient == 0.8
    assert zone.application_rate_mm_per_min == 2.0
    assert zone.et_deficit_mm == 0.0
    assert zone.last_et_sync_at is None


def test_schedule_defaults(session):
    session.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
    session.commit()
    sched = Schedule(zone_id=1)
    session.add(sched)
    session.commit()
    session.refresh(sched)
    assert sched.enabled is False
    assert sched.preferred_time == "06:00"
    assert sched.et_threshold_mm == 5.0
    assert sched.max_duration_seconds == 1800


def test_run_record_creation(session):
    session.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
    session.commit()
    run = RunRecord(
        zone_id=1,
        started_at=datetime(2026, 4, 26, 6, 0),
        trigger="manual",
        et_deficit_mm=7.2,
        precipitation_mm=0.5,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.id is not None
    assert run.ended_at is None
    assert run.duration_seconds is None
    assert run.status == "running"

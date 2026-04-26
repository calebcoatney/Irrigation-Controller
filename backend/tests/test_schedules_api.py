import pytest
from unittest.mock import MagicMock, PropertyMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord
from database import get_session
from deps import get_relay
from routers.schedules import router

test_app = FastAPI()
test_app.include_router(router)


def make_mock_relay(valve_state: str = "closed"):
    relay = MagicMock()
    type(relay).available = PropertyMock(return_value=True)
    relay.status = {"valve_1": valve_state, "valve_2": "closed"}
    return relay


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, et_deficit_mm=8.0))
        s.add(Schedule(zone_id=1, enabled=True, et_threshold_mm=5.0, max_duration_seconds=600))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        s.add(Schedule(zone_id=2))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    mock_relay = make_mock_relay()
    mock_scheduler = MagicMock()

    test_app.dependency_overrides[get_session] = override
    test_app.dependency_overrides[get_relay] = lambda: mock_relay

    import routers.schedules as sched_module
    sched_module._get_scheduler = lambda: mock_scheduler

    yield TestClient(test_app), mock_relay, mock_scheduler, engine
    test_app.dependency_overrides.clear()


def test_get_schedule(client):
    tc, *_ = client
    resp = tc.get("/api/zones/1/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone_id"] == 1
    assert data["enabled"] is True


def test_update_schedule(client):
    tc, *_ = client
    resp = tc.put("/api/zones/1/schedule", json={
        "enabled": False,
        "preferred_time": "07:30",
        "et_threshold_mm": 6.0,
        "max_duration_seconds": 900,
    })
    assert resp.status_code == 200
    assert resp.json()["preferred_time"] == "07:30"
    assert resp.json()["enabled"] is False


def test_run_now_opens_valve_and_creates_record(client):
    tc, mock_relay, mock_scheduler, _ = client
    resp = tc.post("/api/zones/1/schedule/run-now")
    assert resp.status_code == 200
    mock_relay.open_valve.assert_called_once_with(1)
    mock_scheduler.add_job.assert_called_once()
    data = resp.json()
    assert data["trigger"] == "manual"
    assert data["status"] == "running"


def test_run_now_returns_409_if_already_running(client):
    tc, mock_relay, *_ = client
    mock_relay.status = {"valve_1": "open", "valve_2": "closed"}
    resp = tc.post("/api/zones/1/schedule/run-now")
    assert resp.status_code == 409


def test_stop_zone(client):
    tc, mock_relay, mock_scheduler, engine = client
    # First create a running record
    with Session(engine) as s:
        from datetime import datetime
        run = RunRecord(zone_id=1, started_at=datetime.now(), trigger="manual", status="running")
        s.add(run)
        s.commit()
    resp = tc.post("/api/zones/1/stop")
    assert resp.status_code == 200
    mock_relay.close_valve.assert_called_with(1)

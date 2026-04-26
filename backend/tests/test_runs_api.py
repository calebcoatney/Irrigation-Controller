import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, RunRecord
from database import get_session
from routers.runs import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    now = datetime.now()
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        for i in range(5):
            s.add(RunRecord(
                zone_id=1,
                started_at=now - timedelta(hours=i + 1),
                ended_at=now - timedelta(hours=i),
                trigger="scheduled",
                et_deficit_mm=6.0,
                precipitation_mm=0.0,
                duration_seconds=300,
                status="completed",
            ))
        s.add(RunRecord(
            zone_id=2,
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1, minutes=50),
            trigger="manual",
            et_deficit_mm=0.0,
            precipitation_mm=0.0,
            duration_seconds=300,
            status="completed",
        ))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def test_get_runs_returns_list(client):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6


def test_get_runs_filtered_by_zone(client):
    resp = client.get("/api/runs?zone_id=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["zone_id"] == 2


def test_get_runs_most_recent_first(client):
    resp = client.get("/api/runs?zone_id=1")
    assert resp.status_code == 200
    data = resp.json()
    times = [r["started_at"] for r in data]
    assert times == sorted(times, reverse=True)


def test_get_run_detail(client):
    all_runs = client.get("/api/runs").json()
    run_id = all_runs[0]["id"]
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


def test_get_run_detail_not_found(client):
    resp = client.get("/api/runs/9999")
    assert resp.status_code == 404

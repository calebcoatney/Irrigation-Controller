import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.pool import StaticPool
from models import ZoneConfig, Schedule
from database import get_session
from routers.zones import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def test_get_zones_returns_both(client):
    resp = client.get("/api/zones")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["zone_id"] == 1
    assert data[1]["zone_id"] == 2


def test_update_zone_config(client):
    resp = client.put("/api/zones/1/config", json={
        "name": "Front Lawn",
        "lat": 39.9,
        "lng": -104.9,
        "et_coefficient": 0.65,
        "application_rate_mm_per_min": 1.5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Front Lawn"
    assert data["et_coefficient"] == pytest.approx(0.65)


def test_update_zone_config_invalid_id(client):
    resp = client.put("/api/zones/3/config", json={"name": "Ghost"})
    assert resp.status_code == 404

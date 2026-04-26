import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, Session, SQLModel
from unittest.mock import patch, MagicMock
from models import ZoneConfig, Schedule
from database import get_session
from routers.weather_status import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, et_deficit_mm=7.2,
                         last_et_sync_at=datetime(2026, 4, 25, 0, 5)))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0, et_deficit_mm=3.1))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def _mock_weather(et_mm, precip_mm):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "daily": {
            "et0_fao_evapotranspiration": [et_mm],
            "precipitation_sum": [precip_mm],
        }
    }
    return mock


def test_weather_status_returns_zone_deficits(client):
    with patch("weather.httpx.get", return_value=_mock_weather(5.1, 0.3)):
        resp = client.get("/api/weather/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "zones" in data
    assert len(data["zones"]) == 2
    assert data["zones"][0]["zone_id"] == 1
    assert data["zones"][0]["et_deficit_mm"] == pytest.approx(7.2)


def test_weather_status_includes_forecast(client):
    with patch("weather.httpx.get", return_value=_mock_weather(5.1, 0.3)):
        resp = client.get("/api/weather/status")
    data = resp.json()
    assert "forecast" in data
    assert data["forecast"]["et_mm"] == pytest.approx(5.1)
    assert data["forecast"]["precip_mm"] == pytest.approx(0.3)

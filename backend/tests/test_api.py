from unittest.mock import MagicMock, PropertyMock
import pytest
from fastapi.testclient import TestClient
from main import app
from deps import get_relay


def make_mock_relay(available: bool = True, state: dict | None = None) -> MagicMock:
    mock = MagicMock()
    type(mock).available = PropertyMock(return_value=available)
    mock.status = state or {"valve_1": "closed", "valve_2": "closed"}
    return mock


@pytest.fixture
def client():
    mock_relay = make_mock_relay()
    app.dependency_overrides[get_relay] = lambda: mock_relay
    yield TestClient(app), mock_relay
    app.dependency_overrides.clear()


@pytest.fixture
def client_unavailable():
    mock_relay = make_mock_relay(available=False)
    app.dependency_overrides[get_relay] = lambda: mock_relay
    yield TestClient(app), mock_relay
    app.dependency_overrides.clear()


def test_status_returns_both_valves(client):
    test_client, _ = client
    response = test_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "valve_1" in data
    assert "valve_2" in data


def test_open_valve_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "open", "valve_2": "closed"}
    response = test_client.post("/api/valve/1/open")
    assert response.status_code == 200
    mock_relay.open_valve.assert_called_once_with(1)
    assert response.json()["valve_1"] == "open"


def test_close_valve_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "closed", "valve_2": "closed"}
    response = test_client.post("/api/valve/1/close")
    assert response.status_code == 200
    mock_relay.close_valve.assert_called_once_with(1)


def test_open_valve_2_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "closed", "valve_2": "open"}
    response = test_client.post("/api/valve/2/open")
    assert response.status_code == 200
    mock_relay.open_valve.assert_called_once_with(2)


def test_open_valve_503_when_relay_unavailable(client_unavailable):
    test_client, _ = client_unavailable
    response = test_client.post("/api/valve/1/open")
    assert response.status_code == 503
    assert "detail" in response.json()


def test_close_valve_503_when_relay_unavailable(client_unavailable):
    test_client, _ = client_unavailable
    response = test_client.post("/api/valve/1/close")
    assert response.status_code == 503


def test_invalid_valve_id_returns_422(client):
    test_client, _ = client
    response = test_client.post("/api/valve/3/open")
    assert response.status_code == 422


def test_invalid_valve_id_zero_returns_422(client):
    test_client, _ = client
    response = test_client.post("/api/valve/0/close")
    assert response.status_code == 422

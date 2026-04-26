import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from weather import fetch_daily_weather


def _mock_response(et_mm: float, precip_mm: float) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "daily": {
            "et0_fao_evapotranspiration": [et_mm],
            "precipitation_sum": [precip_mm],
        }
    }
    return mock


def test_fetch_returns_et_and_precip():
    with patch("weather.httpx.get", return_value=_mock_response(5.2, 1.4)) as mock_get:
        result = fetch_daily_weather(40.0, -105.0, date(2026, 4, 25))
    assert result["et_mm"] == pytest.approx(5.2)
    assert result["precip_mm"] == pytest.approx(1.4)
    params = mock_get.call_args.kwargs["params"]
    assert params["latitude"] == 40.0
    assert params["longitude"] == -105.0
    assert params["start_date"] == "2026-04-25"
    assert params["end_date"] == "2026-04-25"


def test_fetch_raises_on_http_error():
    mock = MagicMock()
    mock.raise_for_status.side_effect = Exception("503 Service Unavailable")
    with patch("weather.httpx.get", return_value=mock):
        with pytest.raises(Exception, match="503"):
            fetch_daily_weather(40.0, -105.0, date(2026, 4, 25))

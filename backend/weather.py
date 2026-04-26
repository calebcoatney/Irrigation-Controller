import httpx
from datetime import date

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_daily_weather(lat: float, lng: float, target_date: date) -> dict:
    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": "et0_fao_evapotranspiration,precipitation_sum",
        "timezone": "auto",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
    }
    resp = httpx.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {
        "et_mm": data["daily"]["et0_fao_evapotranspiration"][0],
        "precip_mm": data["daily"]["precipitation_sum"][0],
    }

import logging
from datetime import date
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session
from models import ZoneConfig
from weather import fetch_daily_weather

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/weather/status")
def get_weather_status(session: Session = Depends(get_session)):
    zones = session.exec(select(ZoneConfig)).all()
    forecast = None
    if zones and (zones[0].lat != 0.0 or zones[0].lng != 0.0):
        try:
            today = date.today()
            forecast = fetch_daily_weather(zones[0].lat, zones[0].lng, today)
        except Exception:
            logger.warning("Failed to fetch weather forecast for zone %s", zones[0].zone_id, exc_info=True)
            forecast = None

    return {
        "zones": [
            {
                "zone_id": z.zone_id,
                "name": z.name,
                "et_deficit_mm": z.et_deficit_mm,
                "last_et_sync_at": z.last_et_sync_at.isoformat() if z.last_et_sync_at else None,
            }
            for z in zones
        ],
        "forecast": forecast,
    }

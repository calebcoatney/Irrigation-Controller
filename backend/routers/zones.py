from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional

from database import get_session
from models import ZoneConfig

router = APIRouter()


class ZoneConfigUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    et_coefficient: Optional[float] = None
    application_rate_mm_per_min: Optional[float] = None


@router.get("/api/zones")
def get_zones(session: Session = Depends(get_session)) -> list[ZoneConfig]:
    return session.exec(select(ZoneConfig)).all()


@router.put("/api/zones/{zone_id}/config")
def update_zone_config(
    zone_id: int,
    body: ZoneConfigUpdate,
    session: Session = Depends(get_session),
) -> ZoneConfig:
    zone = session.get(ZoneConfig, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(zone, field, value)
    session.add(zone)
    session.commit()
    session.refresh(zone)
    return zone

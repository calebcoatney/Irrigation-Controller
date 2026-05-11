from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional, Callable

from database import get_session
from deps import get_relay
from models import ZoneConfig, Schedule
from valve_runner import run_zone, stop_zone
from et_logic import compute_duration_seconds
from relay import RelayController, RelayError

router = APIRouter()

_get_scheduler: Callable = lambda: None


def set_scheduler_getter(getter: Callable) -> None:
    global _get_scheduler
    _get_scheduler = getter


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    preferred_time: Optional[str] = None
    et_threshold_mm: Optional[float] = None
    max_duration_seconds: Optional[int] = None


@router.get("/api/zones/{zone_id}/schedule")
def get_schedule(zone_id: int, session: Session = Depends(get_session)) -> Schedule:
    sched = session.get(Schedule, zone_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule for zone {zone_id} not found")
    return sched


@router.put("/api/zones/{zone_id}/schedule")
def update_schedule(
    zone_id: int,
    body: ScheduleUpdate,
    session: Session = Depends(get_session),
) -> Schedule:
    sched = session.get(Schedule, zone_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule for zone {zone_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(sched, field, value)
    session.add(sched)
    session.commit()
    session.refresh(sched)
    return sched


@router.post("/api/zones/{zone_id}/schedule/run-now")
def run_now(
    zone_id: int,
    relay: RelayController = Depends(get_relay),
    session: Session = Depends(get_session),
):
    if zone_id not in (1, 2):
        raise HTTPException(status_code=422, detail="zone_id must be 1 or 2")
    if not relay.available:
        raise HTTPException(status_code=503, detail="Relay device not found")
    if relay.status.get(f"valve_{zone_id}") == "open":
        raise HTTPException(status_code=409, detail="Zone is already running")
    zone = session.get(ZoneConfig, zone_id)
    sched = session.get(Schedule, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    fallback_duration = 300
    if sched and zone.et_deficit_mm >= sched.et_threshold_mm:
        duration = compute_duration_seconds(
            zone.et_deficit_mm,
            zone.application_rate_mm_per_min,
            sched.max_duration_seconds,
        )
    else:
        duration = fallback_duration
    scheduler = _get_scheduler()
    ran_from_deficit = sched and zone.et_deficit_mm >= sched.et_threshold_mm
    try:
        run = run_zone(zone_id, duration, "manual", zone.et_deficit_mm, 0.0, relay, session, scheduler)
    except RelayError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if ran_from_deficit:
        zone.et_deficit_mm = 0.0
    else:
        applied_mm = (duration / 60) * zone.application_rate_mm_per_min
        zone.et_deficit_mm = max(0.0, zone.et_deficit_mm - applied_mm)
    session.add(zone)
    session.commit()
    session.refresh(run)
    return run


@router.post("/api/zones/{zone_id}/stop")
def stop(
    zone_id: int,
    relay: RelayController = Depends(get_relay),
    session: Session = Depends(get_session),
):
    if zone_id not in (1, 2):
        raise HTTPException(status_code=422, detail="zone_id must be 1 or 2")
    scheduler = _get_scheduler()
    stopped = stop_zone(zone_id, relay, session, scheduler)
    if stopped is None:
        return {"message": "No active run found"}
    return stopped

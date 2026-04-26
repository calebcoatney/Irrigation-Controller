from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class ZoneConfig(SQLModel, table=True):
    zone_id: int = Field(primary_key=True)
    name: str
    lat: float = 0.0
    lng: float = 0.0
    et_coefficient: float = 0.8
    application_rate_mm_per_min: float = 2.0
    et_deficit_mm: float = 0.0
    last_et_sync_at: Optional[datetime] = None


class Schedule(SQLModel, table=True):
    zone_id: int = Field(primary_key=True, foreign_key="zoneconfig.zone_id")
    enabled: bool = False
    preferred_time: str = "06:00"
    et_threshold_mm: float = 5.0
    max_duration_seconds: int = 1800


class RunRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="zoneconfig.zone_id")
    started_at: datetime
    ended_at: Optional[datetime] = None
    trigger: str
    et_deficit_mm: float = 0.0
    precipitation_mm: float = 0.0
    duration_seconds: Optional[int] = None
    status: str = "running"

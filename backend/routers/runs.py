from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional

from database import get_session
from models import RunRecord

router = APIRouter()


@router.get("/api/runs")
def get_runs(
    zone_id: Optional[int] = Query(default=None),
    limit: int = Query(default=30, le=200),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
) -> list[RunRecord]:
    stmt = select(RunRecord).order_by(RunRecord.started_at.desc()).offset(offset).limit(limit)
    if zone_id is not None:
        stmt = stmt.where(RunRecord.zone_id == zone_id)
    return session.exec(stmt).all()


@router.get("/api/runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> RunRecord:
    run = session.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run

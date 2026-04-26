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
    stmt = select(RunRecord)
    if zone_id is not None:
        stmt = stmt.where(RunRecord.zone_id == zone_id)
    stmt = stmt.order_by(RunRecord.started_at.desc()).offset(offset).limit(limit)
    return session.exec(stmt).all()


@router.get("/api/runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> RunRecord:
    run = session.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.delete("/api/runs")
def delete_all_runs(session: Session = Depends(get_session)):
    runs = session.exec(select(RunRecord)).all()
    for run in runs:
        session.delete(run)
    session.commit()
    return {"deleted": len(runs)}


@router.delete("/api/runs/{run_id}")
def delete_run(run_id: int, session: Session = Depends(get_session)):
    run = session.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    session.delete(run)
    session.commit()
    return {"deleted": 1}

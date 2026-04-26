from datetime import datetime, timedelta
from sqlmodel import Session, select
from models import RunRecord

from deps import get_relay
from database import engine


def run_zone(
    zone_id: int,
    duration_seconds: int,
    trigger: str,
    et_deficit_mm: float,
    precipitation_mm: float,
    relay,
    session: Session,
    scheduler,
) -> RunRecord:
    relay.open_valve(zone_id)
    run = RunRecord(
        zone_id=zone_id,
        started_at=datetime.now(),
        trigger=trigger,
        et_deficit_mm=et_deficit_mm,
        precipitation_mm=precipitation_mm,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    scheduler.add_job(
        finish_run,
        "date",
        run_date=datetime.now() + timedelta(seconds=duration_seconds),
        args=[run.id, zone_id],
        id=f"close_zone_{zone_id}",
        replace_existing=True,
    )
    return run


def finish_run(run_id: int, zone_id: int) -> None:
    relay = get_relay()
    relay.close_valve(zone_id)
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run and run.status == "running":
            now = datetime.now()
            run.ended_at = now
            run.duration_seconds = int((now - run.started_at).total_seconds())
            run.status = "completed"
            session.add(run)
            session.commit()


def stop_zone(zone_id: int, relay, session: Session, scheduler) -> RunRecord | None:
    relay.close_valve(zone_id)
    try:
        scheduler.remove_job(f"close_zone_{zone_id}")
    except Exception:
        pass
    run = session.exec(
        select(RunRecord)
        .where(RunRecord.zone_id == zone_id)
        .where(RunRecord.status == "running")
        .order_by(RunRecord.started_at.desc())
    ).first()
    if run:
        now = datetime.now()
        run.ended_at = now
        run.duration_seconds = int((now - run.started_at).total_seconds())
        run.status = "interrupted"
        session.add(run)
        session.commit()
        session.refresh(run)
    return run

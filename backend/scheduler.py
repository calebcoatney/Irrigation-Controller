from datetime import datetime, date, timedelta
from sqlmodel import Session, select
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from database import engine
from models import ZoneConfig, Schedule
from et_logic import update_deficit, compute_duration_seconds
from weather import fetch_daily_weather

_scheduler: BackgroundScheduler | None = None

JOBSTORE_URL = "sqlite:////data/irrigation.db"


def get_scheduler() -> BackgroundScheduler:
    return _scheduler


def create_scheduler() -> BackgroundScheduler:
    global _scheduler
    jobstores = {"default": SQLAlchemyJobStore(url=JOBSTORE_URL)}
    _scheduler = BackgroundScheduler(jobstores=jobstores)
    return _scheduler


def register_jobs(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        nightly_et_sync,
        "cron",
        hour=0,
        minute=5,
        id="nightly_et_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        morning_schedule_check,
        "cron",
        minute="*",
        id="morning_schedule_check",
        replace_existing=True,
    )


def nightly_et_sync() -> None:
    yesterday = date.today() - timedelta(days=1)
    with Session(engine) as session:
        zones = session.exec(select(ZoneConfig)).all()
        for zone in zones:
            if zone.lat == 0.0 and zone.lng == 0.0:
                continue
            try:
                weather = fetch_daily_weather(zone.lat, zone.lng, yesterday)
                zone.et_deficit_mm = update_deficit(
                    zone.et_deficit_mm,
                    weather["et_mm"],
                    weather["precip_mm"],
                    zone.et_coefficient,
                )
                zone.last_et_sync_at = datetime.now()
                session.add(zone)
            except Exception:
                pass
        session.commit()


def morning_schedule_check() -> None:
    from deps import get_relay
    from valve_runner import run_zone

    current_time = datetime.now().strftime("%H:%M")
    with Session(engine) as session:
        zones = session.exec(select(ZoneConfig)).all()
        for zone in zones:
            sched = session.get(Schedule, zone.zone_id)
            if not sched or not sched.enabled:
                continue
            if sched.preferred_time != current_time:
                continue
            if zone.et_deficit_mm < sched.et_threshold_mm:
                continue
            relay = get_relay()
            if relay.status.get(f"valve_{zone.zone_id}") == "open":
                continue
            duration = compute_duration_seconds(
                zone.et_deficit_mm,
                zone.application_rate_mm_per_min,
                sched.max_duration_seconds,
            )
            run_zone(zone.zone_id, duration, "scheduled", zone.et_deficit_mm, 0.0, relay, session, _scheduler)
            zone.et_deficit_mm = 0.0
            session.add(zone)
            session.commit()

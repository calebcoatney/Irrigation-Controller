# Sophisticated Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ET-based auto-scheduling, Open-Meteo weather integration, run history logging, and a tabbed dashboard UI to the irrigation controller.

**Architecture:** APScheduler runs inside the FastAPI process using SQLite as its job store; SQLModel manages three new tables (zone_config, schedules, run_records) in `/data/irrigation.db`. The React frontend becomes a tabbed SPA (Dashboard, Schedule, History, Settings) using React Router.

**Tech Stack:** Python — FastAPI, SQLModel, APScheduler[sqlalchemy], httpx; Frontend — React 19, Vite, react-router-dom; DB — SQLite via Docker volume; Weather — Open-Meteo (no API key)

---

## File Map

### Backend — new files

| File | Responsibility |
|------|---------------|
| `backend/deps.py` | Relay singleton + `get_relay` FastAPI dependency |
| `backend/database.py` | SQLite engine, `get_session`, `init_db` |
| `backend/models.py` | SQLModel table classes |
| `backend/et_logic.py` | Pure ET math: `update_deficit`, `compute_duration_seconds` |
| `backend/weather.py` | Open-Meteo API client |
| `backend/valve_runner.py` | `run_zone`, `finish_run`, `stop_zone` |
| `backend/scheduler.py` | APScheduler instance, nightly sync job, schedule check job |
| `backend/routers/__init__.py` | Empty |
| `backend/routers/zones.py` | `GET /api/zones`, `PUT /api/zones/{id}/config` |
| `backend/routers/schedules.py` | `GET/PUT /api/zones/{id}/schedule`, `POST run-now`, `POST stop` |
| `backend/routers/runs.py` | `GET /api/runs`, `GET /api/runs/{id}` |
| `backend/routers/weather_status.py` | `GET /api/weather/status` |
| `backend/tests/conftest.py` | Shared in-memory DB fixtures |
| `backend/tests/test_et_logic.py` | ET math unit tests |
| `backend/tests/test_weather.py` | Weather client tests (mocked httpx) |
| `backend/tests/test_valve_runner.py` | valve_runner unit tests |
| `backend/tests/test_zones_api.py` | Zone config endpoint tests |
| `backend/tests/test_schedules_api.py` | Schedule + run-now + stop endpoint tests |
| `backend/tests/test_runs_api.py` | Run history endpoint tests |
| `backend/tests/test_weather_status_api.py` | Weather status endpoint tests |

### Backend — modified files

| File | Change |
|------|--------|
| `backend/main.py` | Import `get_relay` from `deps`, add lifespan, register routers |
| `backend/requirements.txt` | Add `sqlmodel`, `apscheduler[sqlalchemy]` (httpx already present) |
| `backend/tests/test_api.py` | Change `from main import app, get_relay` → import `get_relay` from `deps` |

### Frontend — new files

| File | Responsibility |
|------|---------------|
| `frontend/src/api.js` | Fetch wrappers for all API calls |
| `frontend/src/Nav.jsx` | Tab navigation bar |
| `frontend/src/components/ZoneCard.jsx` | Enhanced zone card (extracted + extended) |
| `frontend/src/components/WeatherStrip.jsx` | Weather summary bar |
| `frontend/src/pages/Dashboard.jsx` | Dashboard tab |
| `frontend/src/pages/Schedule.jsx` | Schedule config tab |
| `frontend/src/pages/History.jsx` | Run history tab with expandable rows |
| `frontend/src/pages/Settings.jsx` | Zone settings tab |

### Frontend — modified files

| File | Change |
|------|--------|
| `frontend/src/App.jsx` | React Router shell with `<Nav>` and route outlets |
| `frontend/src/App.css` | Styles for nav, weather strip, schedule/history/settings panels |
| `frontend/package.json` | Add `react-router-dom` |

### Infrastructure

| File | Change |
|------|--------|
| `docker-compose.yml` | Add bind-mount volume for `/data` |

---

## Task 1: Backend dependencies and Docker volume

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
pyserial==3.5
sqlmodel==0.0.22
apscheduler[sqlalchemy]==3.10.4
httpx==0.28.1
pytest==8.3.5
```

- [ ] **Step 2: Update docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    devices:
      - /dev/irrigation_relay:/dev/irrigation_relay
    volumes:
      - type: bind
        source: /srv/irrigation-controller/data
        target: /data
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt docker-compose.yml
git commit -m "chore: add sqlmodel, apscheduler deps and data volume mount"
```

---

## Task 2: Relay dependency, data models, and database setup

**Files:**
- Create: `backend/deps.py`
- Create: `backend/models.py`
- Create: `backend/database.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_models.py`:

```python
import pytest
from datetime import datetime
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_zone_config_defaults(session):
    zone = ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0)
    session.add(zone)
    session.commit()
    session.refresh(zone)
    assert zone.et_coefficient == 0.8
    assert zone.application_rate_mm_per_min == 2.0
    assert zone.et_deficit_mm == 0.0
    assert zone.last_et_sync_at is None


def test_schedule_defaults(session):
    session.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
    session.commit()
    sched = Schedule(zone_id=1)
    session.add(sched)
    session.commit()
    session.refresh(sched)
    assert sched.enabled is False
    assert sched.preferred_time == "06:00"
    assert sched.et_threshold_mm == 5.0
    assert sched.max_duration_seconds == 1800


def test_run_record_creation(session):
    session.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
    session.commit()
    run = RunRecord(
        zone_id=1,
        started_at=datetime(2026, 4, 26, 6, 0),
        trigger="manual",
        et_deficit_mm=7.2,
        precipitation_mm=0.5,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.id is not None
    assert run.ended_at is None
    assert run.duration_seconds is None
    assert run.status == "running"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create deps.py**

Create `backend/deps.py`:

```python
from relay import RelayController

_relay = RelayController()


def get_relay() -> RelayController:
    return _relay
```

- [ ] **Step 4: Create models.py**

Create `backend/models.py`:

```python
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
```

- [ ] **Step 5: Create database.py**

Create `backend/database.py`:

```python
from sqlmodel import create_engine, Session, SQLModel, select
from models import ZoneConfig, Schedule

DATABASE_URL = "sqlite:////data/irrigation.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for zone_id, name in [(1, "Front Yard"), (2, "Back Yard")]:
            if not session.get(ZoneConfig, zone_id):
                session.add(ZoneConfig(zone_id=zone_id, name=name))
                session.add(Schedule(zone_id=zone_id))
        session.commit()
```

- [ ] **Step 6: Create tests/conftest.py**

Create `backend/tests/conftest.py`:

```python
import pytest
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="seeded_engine")
def seeded_engine_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for zone_id, name in [(1, "Front Yard"), (2, "Back Yard")]:
            session.add(ZoneConfig(zone_id=zone_id, name=name, lat=40.0, lng=-105.0))
            session.add(Schedule(zone_id=zone_id))
        session.commit()
    return engine
```

- [ ] **Step 7: Update test_api.py import**

In `backend/tests/test_api.py`, change line 4:

```python
# Before:
from main import app, get_relay

# After:
from main import app
from deps import get_relay
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
cd backend && python -m pytest -v
```

Expected: all existing tests + 3 new model tests pass

- [ ] **Step 9: Commit**

```bash
git add backend/deps.py backend/models.py backend/database.py \
        backend/tests/conftest.py backend/tests/test_models.py \
        backend/tests/test_api.py
git commit -m "feat: relay dependency, SQLModel data models, database setup"
```

---

## Task 3: ET logic

**Files:**
- Create: `backend/et_logic.py`
- Create: `backend/tests/test_et_logic.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_et_logic.py`:

```python
import pytest
from et_logic import update_deficit, compute_duration_seconds


def test_update_deficit_basic():
    result = update_deficit(0.0, et_mm=5.0, precip_mm=0.0, et_coefficient=0.8)
    assert result == pytest.approx(4.0)


def test_update_deficit_rain_reduces_deficit():
    result = update_deficit(3.0, et_mm=5.0, precip_mm=6.0, et_coefficient=0.8)
    assert result == pytest.approx(0.0)


def test_update_deficit_never_negative():
    result = update_deficit(0.0, et_mm=2.0, precip_mm=10.0, et_coefficient=0.8)
    assert result == 0.0


def test_update_deficit_accumulates_over_days():
    deficit = 0.0
    deficit = update_deficit(deficit, et_mm=6.0, precip_mm=0.0, et_coefficient=0.8)
    deficit = update_deficit(deficit, et_mm=6.0, precip_mm=2.0, et_coefficient=0.8)
    assert deficit == pytest.approx(7.6)


def test_compute_duration_basic():
    result = compute_duration_seconds(
        deficit_mm=10.0,
        application_rate_mm_per_min=2.0,
        max_duration_seconds=1800,
    )
    assert result == 300


def test_compute_duration_capped_by_max():
    result = compute_duration_seconds(
        deficit_mm=100.0,
        application_rate_mm_per_min=2.0,
        max_duration_seconds=600,
    )
    assert result == 600


def test_compute_duration_zero_rate_returns_max():
    result = compute_duration_seconds(
        deficit_mm=10.0,
        application_rate_mm_per_min=0.0,
        max_duration_seconds=900,
    )
    assert result == 900
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_et_logic.py -v
```

Expected: `ModuleNotFoundError: No module named 'et_logic'`

- [ ] **Step 3: Implement et_logic.py**

Create `backend/et_logic.py`:

```python
def update_deficit(current_deficit: float, et_mm: float, precip_mm: float, et_coefficient: float) -> float:
    new_deficit = current_deficit + (et_mm * et_coefficient) - precip_mm
    return max(new_deficit, 0.0)


def compute_duration_seconds(deficit_mm: float, application_rate_mm_per_min: float, max_duration_seconds: int) -> int:
    if application_rate_mm_per_min <= 0:
        return max_duration_seconds
    duration_seconds = int((deficit_mm / application_rate_mm_per_min) * 60)
    return min(duration_seconds, max_duration_seconds)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_et_logic.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/et_logic.py backend/tests/test_et_logic.py
git commit -m "feat: ET deficit and run duration math"
```

---

## Task 4: Open-Meteo weather client

**Files:**
- Create: `backend/weather.py`
- Create: `backend/tests/test_weather.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_weather.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_weather.py -v
```

Expected: `ModuleNotFoundError: No module named 'weather'`

- [ ] **Step 3: Implement weather.py**

Create `backend/weather.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_weather.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/weather.py backend/tests/test_weather.py
git commit -m "feat: Open-Meteo weather client"
```

---

## Task 5: Valve runner

**Files:**
- Create: `backend/valve_runner.py`
- Create: `backend/tests/test_valve_runner.py`

Three functions:
- `run_zone` — opens valve, creates RunRecord, schedules APScheduler auto-close job
- `finish_run` — called by APScheduler; closes valve, marks run completed
- `stop_zone` — closes valve immediately, cancels scheduler job, marks run interrupted

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_valve_runner.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord
from valve_runner import run_zone, finish_run, stop_zone


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, application_rate_mm_per_min=2.0))
        s.add(Schedule(zone_id=1))
        s.commit()
        yield s


def make_relay():
    relay = MagicMock()
    relay.status = {"valve_1": "closed", "valve_2": "closed"}
    return relay


def test_run_zone_opens_valve_and_creates_record(session):
    relay = make_relay()
    scheduler = MagicMock()
    run = run_zone(1, 300, "manual", 7.5, 0.0, relay, session, scheduler)
    relay.open_valve.assert_called_once_with(1)
    assert run.id is not None
    assert run.zone_id == 1
    assert run.trigger == "manual"
    assert run.status == "running"
    assert run.et_deficit_mm == pytest.approx(7.5)


def test_run_zone_schedules_auto_close(session):
    relay = make_relay()
    scheduler = MagicMock()
    run_zone(1, 300, "scheduled", 5.0, 1.0, relay, session, scheduler)
    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args.kwargs
    assert call_kwargs["id"] == "close_zone_1"
    assert call_kwargs["replace_existing"] is True


def test_finish_run_closes_valve_and_marks_completed():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.commit()
        run = RunRecord(zone_id=1, started_at=datetime.now(), trigger="manual", status="running")
        s.add(run)
        s.commit()
        run_id = run.id

    relay = make_relay()
    with patch("valve_runner.get_relay", return_value=relay), \
         patch("valve_runner.engine", engine):
        finish_run(run_id, 1)

    relay.close_valve.assert_called_once_with(1)
    with Session(engine) as s:
        updated = s.get(RunRecord, run_id)
        assert updated.status == "completed"
        assert updated.ended_at is not None
        assert updated.duration_seconds is not None


def test_stop_zone_marks_run_interrupted(session):
    relay = make_relay()
    scheduler = MagicMock()
    run = run_zone(1, 300, "manual", 5.0, 0.0, relay, session, scheduler)
    stopped = stop_zone(1, relay, session, scheduler)
    relay.close_valve.assert_called_with(1)
    scheduler.remove_job.assert_called_once_with("close_zone_1")
    assert stopped.status == "interrupted"
    assert stopped.ended_at is not None


def test_stop_zone_returns_none_if_no_active_run(session):
    relay = make_relay()
    scheduler = MagicMock()
    result = stop_zone(1, relay, session, scheduler)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_valve_runner.py -v
```

Expected: `ModuleNotFoundError: No module named 'valve_runner'`

- [ ] **Step 3: Implement valve_runner.py**

Create `backend/valve_runner.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_valve_runner.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/valve_runner.py backend/tests/test_valve_runner.py
git commit -m "feat: valve runner with auto-close and stop support"
```

---

## Task 6: Scheduler

**Files:**
- Create: `backend/scheduler.py`

No isolated unit tests here — the job functions depend on DB + relay. Covered by integration when wired into main.py.

- [ ] **Step 1: Create scheduler.py**

Create `backend/scheduler.py`:

```python
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
```

- [ ] **Step 2: Verify imports resolve**

```bash
cd backend && python -c "from scheduler import create_scheduler, register_jobs; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler.py
git commit -m "feat: APScheduler with nightly ET sync and schedule check jobs"
```

---

## Task 7: Zone config router

**Files:**
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/zones.py`
- Create: `backend/tests/test_zones_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_zones_api.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule
from database import get_session
from routers.zones import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def test_get_zones_returns_both(client):
    resp = client.get("/api/zones")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["zone_id"] == 1
    assert data[1]["zone_id"] == 2


def test_update_zone_config(client):
    resp = client.put("/api/zones/1/config", json={
        "name": "Front Lawn",
        "lat": 39.9,
        "lng": -104.9,
        "et_coefficient": 0.65,
        "application_rate_mm_per_min": 1.5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Front Lawn"
    assert data["et_coefficient"] == pytest.approx(0.65)


def test_update_zone_config_invalid_id(client):
    resp = client.put("/api/zones/3/config", json={"name": "Ghost"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_zones_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'routers'`

- [ ] **Step 3: Create routers/__init__.py**

```bash
touch backend/routers/__init__.py
```

- [ ] **Step 4: Create routers/zones.py**

Create `backend/routers/zones.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_zones_api.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/__init__.py backend/routers/zones.py backend/tests/test_zones_api.py
git commit -m "feat: zone config GET and PUT endpoints"
```

---

## Task 8: Schedules router (including run-now and stop)

**Files:**
- Create: `backend/routers/schedules.py`
- Create: `backend/tests/test_schedules_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_schedules_api.py`:

```python
import pytest
from unittest.mock import MagicMock, PropertyMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule, RunRecord
from database import get_session
from deps import get_relay
from routers.schedules import router

test_app = FastAPI()
test_app.include_router(router)


def make_mock_relay(valve_state: str = "closed"):
    relay = MagicMock()
    type(relay).available = PropertyMock(return_value=True)
    relay.status = {"valve_1": valve_state, "valve_2": "closed"}
    return relay


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, et_deficit_mm=8.0))
        s.add(Schedule(zone_id=1, enabled=True, et_threshold_mm=5.0, max_duration_seconds=600))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        s.add(Schedule(zone_id=2))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    mock_relay = make_mock_relay()
    mock_scheduler = MagicMock()

    test_app.dependency_overrides[get_session] = override
    test_app.dependency_overrides[get_relay] = lambda: mock_relay

    import routers.schedules as sched_module
    sched_module._get_scheduler = lambda: mock_scheduler

    yield TestClient(test_app), mock_relay, mock_scheduler, engine
    test_app.dependency_overrides.clear()


def test_get_schedule(client):
    tc, *_ = client
    resp = tc.get("/api/zones/1/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone_id"] == 1
    assert data["enabled"] is True


def test_update_schedule(client):
    tc, *_ = client
    resp = tc.put("/api/zones/1/schedule", json={
        "enabled": False,
        "preferred_time": "07:30",
        "et_threshold_mm": 6.0,
        "max_duration_seconds": 900,
    })
    assert resp.status_code == 200
    assert resp.json()["preferred_time"] == "07:30"
    assert resp.json()["enabled"] is False


def test_run_now_opens_valve_and_creates_record(client):
    tc, mock_relay, mock_scheduler, _ = client
    resp = tc.post("/api/zones/1/schedule/run-now")
    assert resp.status_code == 200
    mock_relay.open_valve.assert_called_once_with(1)
    mock_scheduler.add_job.assert_called_once()
    data = resp.json()
    assert data["trigger"] == "manual"
    assert data["status"] == "running"


def test_run_now_returns_409_if_already_running(client):
    tc, mock_relay, *_ = client
    mock_relay.status = {"valve_1": "open", "valve_2": "closed"}
    resp = tc.post("/api/zones/1/schedule/run-now")
    assert resp.status_code == 409


def test_stop_zone(client):
    tc, mock_relay, mock_scheduler, engine = client
    # First start a run
    with Session(engine) as s:
        from datetime import datetime
        run = RunRecord(zone_id=1, started_at=datetime.now(), trigger="manual", status="running")
        s.add(run)
        s.commit()
    resp = tc.post("/api/zones/1/stop")
    assert resp.status_code == 200
    mock_relay.close_valve.assert_called_with(1)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_schedules_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'routers.schedules'`

- [ ] **Step 3: Create routers/schedules.py**

Create `backend/routers/schedules.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional, Callable

from database import get_session
from deps import get_relay
from models import ZoneConfig, Schedule
from valve_runner import run_zone, stop_zone
from et_logic import compute_duration_seconds
from relay import RelayController

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
    from relay import RelayError
    try:
        run = run_zone(zone_id, duration, "manual", zone.et_deficit_mm, 0.0, relay, session, scheduler)
    except RelayError as e:
        raise HTTPException(status_code=503, detail=str(e))
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_schedules_api.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/schedules.py backend/tests/test_schedules_api.py
git commit -m "feat: schedule CRUD, run-now, and stop endpoints"
```

---

## Task 9: Run history router

**Files:**
- Create: `backend/routers/runs.py`
- Create: `backend/tests/test_runs_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runs_api.py`:

```python
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, RunRecord
from database import get_session
from routers.runs import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    now = datetime.now()
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0))
        for i in range(5):
            s.add(RunRecord(
                zone_id=1,
                started_at=now - timedelta(hours=i + 1),
                ended_at=now - timedelta(hours=i),
                trigger="scheduled",
                et_deficit_mm=6.0,
                precipitation_mm=0.0,
                duration_seconds=300,
                status="completed",
            ))
        s.add(RunRecord(
            zone_id=2,
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1, minutes=50),
            trigger="manual",
            et_deficit_mm=0.0,
            precipitation_mm=0.0,
            duration_seconds=300,
            status="completed",
        ))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def test_get_runs_returns_list(client):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6


def test_get_runs_filtered_by_zone(client):
    resp = client.get("/api/runs?zone_id=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["zone_id"] == 2


def test_get_runs_most_recent_first(client):
    resp = client.get("/api/runs?zone_id=1")
    assert resp.status_code == 200
    data = resp.json()
    times = [r["started_at"] for r in data]
    assert times == sorted(times, reverse=True)


def test_get_run_detail(client):
    all_runs = client.get("/api/runs").json()
    run_id = all_runs[0]["id"]
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


def test_get_run_detail_not_found(client):
    resp = client.get("/api/runs/9999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_runs_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'routers.runs'`

- [ ] **Step 3: Create routers/runs.py**

Create `backend/routers/runs.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_runs_api.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/runs.py backend/tests/test_runs_api.py
git commit -m "feat: run history GET endpoints"
```

---

## Task 10: Weather status router

**Files:**
- Create: `backend/routers/weather_status.py`
- Create: `backend/tests/test_weather_status_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_weather_status_api.py`:

```python
import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from unittest.mock import patch, MagicMock
from models import ZoneConfig, Schedule
from database import get_session
from routers.weather_status import router

test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, et_deficit_mm=7.2,
                         last_et_sync_at=datetime(2026, 4, 25, 0, 5)))
        s.add(ZoneConfig(zone_id=2, name="Back Yard", lat=40.0, lng=-105.0, et_deficit_mm=3.1))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def _mock_weather(et_mm, precip_mm):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "daily": {
            "et0_fao_evapotranspiration": [et_mm],
            "precipitation_sum": [precip_mm],
        }
    }
    return mock


def test_weather_status_returns_zone_deficits(client):
    with patch("weather.httpx.get", return_value=_mock_weather(5.1, 0.3)):
        resp = client.get("/api/weather/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "zones" in data
    assert len(data["zones"]) == 2
    assert data["zones"][0]["zone_id"] == 1
    assert data["zones"][0]["et_deficit_mm"] == pytest.approx(7.2)


def test_weather_status_includes_forecast(client):
    with patch("weather.httpx.get", return_value=_mock_weather(5.1, 0.3)):
        resp = client.get("/api/weather/status")
    data = resp.json()
    assert "forecast" in data
    assert data["forecast"]["et_mm"] == pytest.approx(5.1)
    assert data["forecast"]["precip_mm"] == pytest.approx(0.3)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_weather_status_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'routers.weather_status'`

- [ ] **Step 3: Create routers/weather_status.py**

Create `backend/routers/weather_status.py`:

```python
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session
from models import ZoneConfig
from weather import fetch_daily_weather

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_weather_status_api.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/weather_status.py backend/tests/test_weather_status_api.py
git commit -m "feat: weather and ET status endpoint"
```

---

## Task 11: Wire up main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Replace main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from relay import RelayController, RelayError
from deps import get_relay
from database import init_db
from scheduler import create_scheduler, register_jobs, get_scheduler
from routers import zones, schedules, runs, weather_status
from routers.schedules import set_scheduler_getter


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = create_scheduler()
    set_scheduler_getter(get_scheduler)
    register_jobs(scheduler)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)
app.include_router(zones.router)
app.include_router(schedules.router)
app.include_router(runs.router)
app.include_router(weather_status.router)


@app.get("/api/status")
def get_status(relay: RelayController = Depends(get_relay)):
    return relay.status


@app.post("/api/valve/{valve_id}/open")
def open_valve(valve_id: int, relay: RelayController = Depends(get_relay)):
    if valve_id not in (1, 2):
        raise HTTPException(status_code=422, detail="valve_id must be 1 or 2")
    if not relay.available:
        raise HTTPException(status_code=503, detail="Relay device not found at /dev/irrigation_relay")
    try:
        relay.open_valve(valve_id)
    except RelayError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return relay.status


@app.post("/api/valve/{valve_id}/close")
def close_valve(valve_id: int, relay: RelayController = Depends(get_relay)):
    if valve_id not in (1, 2):
        raise HTTPException(status_code=422, detail="valve_id must be 1 or 2")
    if not relay.available:
        raise HTTPException(status_code=503, detail="Relay device not found at /dev/irrigation_relay")
    try:
        relay.close_valve(valve_id)
    except RelayError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return relay.status
```

- [ ] **Step 2: Run full test suite**

```bash
cd backend && python -m pytest -v
```

Expected: all tests pass (including original test_api.py)

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: wire up routers and scheduler into main app lifespan"
```

---

## Task 12: Frontend dependencies and API client

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/api.js`

- [ ] **Step 1: Add react-router-dom**

In `frontend/package.json`, add to `"dependencies"`:

```json
"react-router-dom": "^7.6.0"
```

- [ ] **Step 2: Install**

```bash
cd frontend && npm install
```

- [ ] **Step 3: Create src/api.js**

Create `frontend/src/api.js`:

```js
const JSON_HEADERS = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const resp = await fetch(path, options);
  const data = await resp.json();
  if (!resp.ok) throw Object.assign(new Error(data.detail || "Request failed"), { status: resp.status });
  return data;
}

export const getStatus = () => request("/api/status");
export const getZones = () => request("/api/zones");
export const updateZoneConfig = (id, body) =>
  request(`/api/zones/${id}/config`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) });
export const getSchedule = (id) => request(`/api/zones/${id}/schedule`);
export const updateSchedule = (id, body) =>
  request(`/api/zones/${id}/schedule`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) });
export const runNow = (id) => request(`/api/zones/${id}/schedule/run-now`, { method: "POST" });
export const stopZone = (id) => request(`/api/zones/${id}/stop`, { method: "POST" });
export const getRuns = (params = {}) =>
  request(`/api/runs?${new URLSearchParams(params)}`);
export const getRun = (id) => request(`/api/runs/${id}`);
export const getWeatherStatus = () => request("/api/weather/status");
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api.js
git commit -m "feat: add react-router-dom and centralized API client"
```

---

## Task 13: App shell and navigation

**Files:**
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/Nav.jsx`

- [ ] **Step 1: Create Nav.jsx**

Create `frontend/src/Nav.jsx`:

```jsx
import { NavLink } from "react-router-dom";

export default function Nav() {
  return (
    <nav className="nav">
      <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Dashboard
      </NavLink>
      <NavLink to="/schedule" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Schedule
      </NavLink>
      <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        History
      </NavLink>
      <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Settings
      </NavLink>
    </nav>
  );
}
```

- [ ] **Step 2: Replace App.jsx**

```jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Nav from "./Nav";
import Dashboard from "./pages/Dashboard";
import Schedule from "./pages/Schedule";
import History from "./pages/History";
import Settings from "./pages/Settings";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <h1>Irrigation Controller</h1>
          <Nav />
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/Nav.jsx
git commit -m "feat: tabbed SPA shell with React Router and nav"
```

---

## Task 14: Dashboard page

**Files:**
- Create: `frontend/src/components/ZoneCard.jsx`
- Create: `frontend/src/components/WeatherStrip.jsx`
- Create: `frontend/src/pages/Dashboard.jsx`

- [ ] **Step 1: Create ZoneCard.jsx**

Create `frontend/src/components/ZoneCard.jsx`:

```jsx
export default function ZoneCard({ zone, schedule, valveState, loading, onRunNow, onStop }) {
  const isRunning = valveState === "open";
  return (
    <div className={`zone-card ${isRunning ? "running" : ""}`}>
      <div className="zone-card-header">
        <h2>{zone.name}</h2>
        <span className={`badge ${isRunning ? "open" : "closed"}`}>
          {isRunning ? "Running" : "Idle"}
        </span>
      </div>
      <div className="zone-meta">
        <span>Deficit: {zone.et_deficit_mm.toFixed(1)} mm</span>
        {schedule?.enabled && (
          <span>Threshold: {schedule.et_threshold_mm} mm · {schedule.preferred_time}</span>
        )}
      </div>
      <button
        className={isRunning ? "btn-stop" : "btn-run"}
        onClick={() => isRunning ? onStop(zone.zone_id) : onRunNow(zone.zone_id)}
        disabled={loading}
      >
        {loading ? "Working…" : isRunning ? "Stop" : "Run Now"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Create WeatherStrip.jsx**

Create `frontend/src/components/WeatherStrip.jsx`:

```jsx
export default function WeatherStrip({ forecast }) {
  if (!forecast) return null;
  const { et_mm, precip_mm } = forecast;
  return (
    <div className="weather-strip">
      <span>Today — ET: <strong>{et_mm.toFixed(1)} mm</strong></span>
      <span>Rain: <strong>{precip_mm.toFixed(1)} mm</strong></span>
      {precip_mm >= et_mm && <span className="weather-note">Rain covers ET today</span>}
    </div>
  );
}
```

- [ ] **Step 3: Create Dashboard.jsx**

Create `frontend/src/pages/Dashboard.jsx`:

```jsx
import { useState, useEffect } from "react";
import ZoneCard from "../components/ZoneCard";
import WeatherStrip from "../components/WeatherStrip";
import { getStatus, getZones, getSchedule, getWeatherStatus, runNow, stopZone } from "../api";

export default function Dashboard() {
  const [status, setStatus] = useState({ valve_1: "closed", valve_2: "closed" });
  const [zones, setZones] = useState([]);
  const [schedules, setSchedules] = useState({});
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getStatus().then(setStatus),
      getZones().then((zs) => {
        setZones(zs);
        return Promise.all(zs.map((z) => getSchedule(z.zone_id)));
      }).then((scheds) =>
        setSchedules(Object.fromEntries(scheds.map((s) => [s.zone_id, s])))
      ),
      getWeatherStatus().then((ws) => setForecast(ws.forecast)),
    ]).catch(() => setError("Cannot reach backend"));
  }, []);

  async function handleRunNow(id) {
    setLoading((l) => ({ ...l, [id]: true }));
    try {
      await runNow(id);
      const s = await getStatus();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((l) => ({ ...l, [id]: false }));
    }
  }

  async function handleStop(id) {
    setLoading((l) => ({ ...l, [id]: true }));
    try {
      await stopZone(id);
      const s = await getStatus();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((l) => ({ ...l, [id]: false }));
    }
  }

  return (
    <div className="page">
      {error && <div className="error-banner">{error}</div>}
      <WeatherStrip forecast={forecast} />
      <div className="zones">
        {zones.map((zone) => (
          <ZoneCard
            key={zone.zone_id}
            zone={zone}
            schedule={schedules[zone.zone_id]}
            valveState={status[`valve_${zone.zone_id}`]}
            loading={loading[zone.zone_id] ?? false}
            onRunNow={handleRunNow}
            onStop={handleStop}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ZoneCard.jsx frontend/src/components/WeatherStrip.jsx \
        frontend/src/pages/Dashboard.jsx
git commit -m "feat: dashboard page with zone cards, weather strip, run-now and stop"
```

---

## Task 15: Schedule page

**Files:**
- Create: `frontend/src/pages/Schedule.jsx`

- [ ] **Step 1: Create Schedule.jsx**

Create `frontend/src/pages/Schedule.jsx`:

```jsx
import { useState, useEffect } from "react";
import { getZones, getSchedule, updateSchedule } from "../api";

function SchedulePanel({ zone, initialSchedule }) {
  const [sched, setSched] = useState(initialSchedule);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const deficit = zone.et_deficit_mm;
  const daysToRun = sched.et_threshold_mm > 0 && deficit < sched.et_threshold_mm
    ? `~${Math.ceil((sched.et_threshold_mm - deficit) / 4)} days at current ET rate`
    : deficit >= sched.et_threshold_mm
    ? "Threshold met — will run at " + sched.preferred_time
    : "—";

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateSchedule(zone.zone_id, sched);
      setSched(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="schedule-panel">
      <div className="schedule-panel-header">
        <h2>{zone.name}</h2>
        <label className="toggle">
          <input
            type="checkbox"
            checked={sched.enabled}
            onChange={(e) => setSched({ ...sched, enabled: e.target.checked })}
          />
          <span>{sched.enabled ? "Enabled" : "Disabled"}</span>
        </label>
      </div>
      <div className="schedule-fields">
        <label>
          Run time
          <input
            type="time"
            value={sched.preferred_time}
            onChange={(e) => setSched({ ...sched, preferred_time: e.target.value })}
          />
        </label>
        <label>
          ET threshold (mm)
          <input
            type="number"
            step="0.5"
            min="1"
            value={sched.et_threshold_mm}
            onChange={(e) => setSched({ ...sched, et_threshold_mm: parseFloat(e.target.value) })}
          />
        </label>
        <label>
          Max duration (min)
          <input
            type="number"
            step="1"
            min="1"
            value={Math.round(sched.max_duration_seconds / 60)}
            onChange={(e) => setSched({ ...sched, max_duration_seconds: parseInt(e.target.value) * 60 })}
          />
        </label>
      </div>
      <p className="schedule-estimate">Estimated next run: {daysToRun}</p>
      <button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : saved ? "Saved" : "Save"}
      </button>
    </div>
  );
}

export default function Schedule() {
  const [zones, setZones] = useState([]);
  const [schedules, setSchedules] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    getZones()
      .then((zs) => {
        setZones(zs);
        return Promise.all(zs.map((z) => getSchedule(z.zone_id)));
      })
      .then((scheds) => setSchedules(Object.fromEntries(scheds.map((s) => [s.zone_id, s]))))
      .catch(() => setError("Cannot reach backend"));
  }, []);

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      <div className="schedule-panels">
        {zones.map((z) =>
          schedules[z.zone_id] ? (
            <SchedulePanel key={z.zone_id} zone={z} initialSchedule={schedules[z.zone_id]} />
          ) : null
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Schedule.jsx
git commit -m "feat: schedule configuration page"
```

---

## Task 16: History page

**Files:**
- Create: `frontend/src/pages/History.jsx`

- [ ] **Step 1: Create History.jsx**

Create `frontend/src/pages/History.jsx`:

```jsx
import { useState, useEffect } from "react";
import { getRuns } from "../api";

function formatDuration(seconds) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function RunRow({ run }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr className={`run-row ${run.status}`} onClick={() => setExpanded((e) => !e)} style={{ cursor: "pointer" }}>
        <td>Zone {run.zone_id}</td>
        <td>{formatDate(run.started_at)}</td>
        <td>{formatDuration(run.duration_seconds)}</td>
        <td><span className={`badge trigger-${run.trigger}`}>{run.trigger}</span></td>
        <td><span className={`badge status-${run.status}`}>{run.status}</span></td>
      </tr>
      {expanded && (
        <tr className="run-detail">
          <td colSpan={5}>
            <div className="run-detail-grid">
              <span>ET deficit at trigger:</span><strong>{run.et_deficit_mm.toFixed(2)} mm</strong>
              <span>Precipitation (24h):</span><strong>{run.precipitation_mm.toFixed(2)} mm</strong>
              <span>Trigger:</span><strong>{run.trigger}</strong>
              <span>Status:</span><strong>{run.status}</strong>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function History() {
  const [runs, setRuns] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState(null);
  const LIMIT = 30;

  useEffect(() => {
    getRuns({ limit: LIMIT + 1, offset: 0 })
      .then((data) => {
        setHasMore(data.length > LIMIT);
        setRuns(data.slice(0, LIMIT));
        setOffset(LIMIT);
      })
      .catch(() => setError("Cannot reach backend"));
  }, []);

  async function loadMore() {
    const data = await getRuns({ limit: LIMIT + 1, offset });
    setHasMore(data.length > LIMIT);
    setRuns((prev) => [...prev, ...data.slice(0, LIMIT)]);
    setOffset((o) => o + LIMIT);
  }

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      {runs.length === 0 ? (
        <p className="empty">No runs recorded yet.</p>
      ) : (
        <table className="run-table">
          <thead>
            <tr>
              <th>Zone</th><th>Started</th><th>Duration</th><th>Trigger</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => <RunRow key={r.id} run={r} />)}
          </tbody>
        </table>
      )}
      {hasMore && (
        <button className="load-more" onClick={loadMore}>Load more</button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/History.jsx
git commit -m "feat: run history page with expandable detail rows"
```

---

## Task 17: Settings page and CSS

**Files:**
- Create: `frontend/src/pages/Settings.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create Settings.jsx**

Create `frontend/src/pages/Settings.jsx`:

```jsx
import { useState, useEffect } from "react";
import { getZones, updateZoneConfig } from "../api";

const ET_REFERENCE = [
  { label: "Cool-season grass lawn", value: 0.80 },
  { label: "Warm-season grass lawn", value: 0.65 },
  { label: "Established shrubs / drip", value: 0.50 },
  { label: "Vegetable garden", value: 1.00 },
];

function ZoneSettings({ initialZone }) {
  const [zone, setZone] = useState(initialZone);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateZoneConfig(zone.zone_id, {
        name: zone.name,
        lat: zone.lat,
        lng: zone.lng,
        et_coefficient: zone.et_coefficient,
        application_rate_mm_per_min: zone.application_rate_mm_per_min,
      });
      setZone(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="settings-panel">
      <h2>Zone {zone.zone_id}</h2>
      <div className="settings-fields">
        <label>
          Name
          <input value={zone.name} onChange={(e) => setZone({ ...zone, name: e.target.value })} />
        </label>
        <label>
          Latitude
          <input type="number" step="0.0001" value={zone.lat}
            onChange={(e) => setZone({ ...zone, lat: parseFloat(e.target.value) })} />
        </label>
        <label>
          Longitude
          <input type="number" step="0.0001" value={zone.lng}
            onChange={(e) => setZone({ ...zone, lng: parseFloat(e.target.value) })} />
        </label>
        <label>
          ET coefficient
          <input type="number" step="0.05" min="0.1" max="1.5" value={zone.et_coefficient}
            onChange={(e) => setZone({ ...zone, et_coefficient: parseFloat(e.target.value) })} />
          <span className="field-hint">
            Reference: {ET_REFERENCE.map((r) => `${r.label} = ${r.value}`).join(" · ")}
          </span>
        </label>
        <label>
          Application rate (mm/min)
          <input type="number" step="0.1" min="0.1" value={zone.application_rate_mm_per_min}
            onChange={(e) => setZone({ ...zone, application_rate_mm_per_min: parseFloat(e.target.value) })} />
        </label>
      </div>
      <button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : saved ? "Saved" : "Save"}
      </button>
    </div>
  );
}

export default function Settings() {
  const [zones, setZones] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    getZones().then(setZones).catch(() => setError("Cannot reach backend"));
  }, []);

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      <div className="settings-panels">
        {zones.map((z) => <ZoneSettings key={z.zone_id} initialZone={z} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Replace App.css**

```css
/* ── Reset & base ────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: #f5f5f4; color: #1c1917; }
button { cursor: pointer; font: inherit; border: none; border-radius: 6px; padding: 0.5rem 1rem; transition: opacity 0.15s; }
button:disabled { opacity: 0.5; cursor: default; }
input { font: inherit; border: 1px solid #d6d3d1; border-radius: 6px; padding: 0.4rem 0.6rem; width: 100%; }
input[type=checkbox] { width: auto; }

/* ── Layout ─────────────────────────────────────── */
.app { min-height: 100vh; display: flex; flex-direction: column; }
.app-header { background: #fff; border-bottom: 1px solid #e7e5e4; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 2rem; }
.app-header h1 { font-size: 1.1rem; font-weight: 600; }
.app-main { flex: 1; padding: 1.5rem; max-width: 900px; margin: 0 auto; width: 100%; }
.page { display: flex; flex-direction: column; gap: 1.5rem; }

/* ── Nav ─────────────────────────────────────────── */
.nav { display: flex; gap: 0.25rem; }
.nav-link { padding: 0.35rem 0.8rem; border-radius: 6px; text-decoration: none; color: #78716c; font-size: 0.9rem; }
.nav-link:hover { background: #f5f5f4; color: #1c1917; }
.nav-link.active { background: #e7e5e4; color: #1c1917; font-weight: 500; }

/* ── Error banner ────────────────────────────────── */
.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 8px; padding: 0.75rem 1rem; }

/* ── Weather strip ───────────────────────────────── */
.weather-strip { background: #fff; border: 1px solid #e7e5e4; border-radius: 8px; padding: 0.75rem 1rem; display: flex; gap: 1.5rem; align-items: center; font-size: 0.9rem; color: #57534e; }
.weather-note { color: #16a34a; font-weight: 500; }

/* ── Zone cards ──────────────────────────────────── */
.zones { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
.zone-card { background: #fff; border: 1px solid #e7e5e4; border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }
.zone-card.running { border-color: #86efac; background: #f0fdf4; }
.zone-card-header { display: flex; justify-content: space-between; align-items: center; }
.zone-card-header h2 { font-size: 1rem; font-weight: 600; }
.zone-meta { font-size: 0.82rem; color: #78716c; display: flex; flex-direction: column; gap: 0.2rem; }
.badge { font-size: 0.75rem; font-weight: 500; padding: 0.2rem 0.55rem; border-radius: 999px; }
.badge.open, .badge.status-running { background: #dcfce7; color: #15803d; }
.badge.closed, .badge.status-completed { background: #f5f5f4; color: #78716c; }
.badge.status-interrupted { background: #fef9c3; color: #854d0e; }
.badge.trigger-manual { background: #ede9fe; color: #7c3aed; }
.badge.trigger-scheduled { background: #dbeafe; color: #1d4ed8; }
.btn-run { background: #16a34a; color: #fff; width: 100%; padding: 0.6rem; }
.btn-run:hover:not(:disabled) { opacity: 0.85; }
.btn-stop { background: #dc2626; color: #fff; width: 100%; padding: 0.6rem; }
.btn-stop:hover:not(:disabled) { opacity: 0.85; }

/* ── Schedule page ───────────────────────────────── */
.schedule-panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
.schedule-panel { background: #fff; border: 1px solid #e7e5e4; border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; }
.schedule-panel-header { display: flex; justify-content: space-between; align-items: center; }
.schedule-panel-header h2 { font-size: 1rem; font-weight: 600; }
.schedule-fields { display: flex; flex-direction: column; gap: 0.75rem; }
.schedule-fields label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; color: #57534e; }
.schedule-estimate { font-size: 0.82rem; color: #78716c; }
.toggle { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }

/* ── History page ────────────────────────────────── */
.run-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; border: 1px solid #e7e5e4; }
.run-table th { text-align: left; padding: 0.75rem 1rem; font-size: 0.8rem; font-weight: 600; color: #78716c; border-bottom: 1px solid #e7e5e4; }
.run-table td { padding: 0.7rem 1rem; font-size: 0.88rem; border-bottom: 1px solid #f5f5f4; }
.run-row:hover td { background: #f9f9f8; }
.run-detail td { background: #fafaf9; padding: 0.75rem 1rem; }
.run-detail-grid { display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 1rem; font-size: 0.85rem; color: #57534e; }
.load-more { align-self: center; background: #f5f5f4; color: #57534e; padding: 0.5rem 1.5rem; }
.empty { color: #78716c; font-size: 0.9rem; }

/* ── Settings page ───────────────────────────────── */
.settings-panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
.settings-panel { background: #fff; border: 1px solid #e7e5e4; border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; }
.settings-panel h2 { font-size: 1rem; font-weight: 600; }
.settings-fields { display: flex; flex-direction: column; gap: 0.75rem; }
.settings-fields label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; color: #57534e; }
.field-hint { font-size: 0.75rem; color: #a8a29e; line-height: 1.4; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Settings.jsx frontend/src/App.css
git commit -m "feat: settings page and complete CSS for all tabs"
```

---

## Self-Review

**Spec coverage check:**
- Architecture (SQLite + APScheduler in-process) ✓ Tasks 1, 6, 11
- ZoneConfig table with ET coefficient + application rate ✓ Task 2
- Schedule table with enabled/preferred_time/threshold/max_duration ✓ Task 2
- RunRecord append-only log ✓ Task 2
- Nightly ET sync from Open-Meteo ✓ Tasks 4, 6
- Morning schedule check at preferred_time ✓ Task 6
- ET deficit update formula ✓ Task 3
- Run duration formula ✓ Task 3
- Safety: max_duration cutoff ✓ Task 5 (via scheduler.add_job with run_date + max)
- GET /api/zones ✓ Task 7
- PUT /api/zones/{id}/config ✓ Task 7
- GET/PUT /api/zones/{id}/schedule ✓ Task 8
- POST run-now (ET formula, fallback 5min if deficit=0) ✓ Task 8
- GET /api/runs (paginated, filterable) ✓ Task 9
- GET /api/runs/{id} ✓ Task 9
- GET /api/weather/status ✓ Task 10
- Dashboard with zone cards, weather strip, Run Now / Stop ✓ Tasks 13–14
- Schedule tab ✓ Task 15
- History tab with expandable detail ✓ Task 16
- Settings tab with ET reference ✓ Task 17
- Docker volume ✓ Task 1

**Placeholder scan:** No TBDs found.

**Type consistency:**
- `run_zone(zone_id, duration_seconds, trigger, et_deficit_mm, precipitation_mm, relay, session, scheduler)` — used identically in Task 5 (implementation), Task 6 (scheduler.py), and Task 8 (schedules router) ✓
- `finish_run(run_id, zone_id)` — defined Task 5, registered in APScheduler Task 5 ✓
- `stop_zone(zone_id, relay, session, scheduler)` — defined Task 5, used Task 8 ✓
- `RunRecord.status` values: `"running"`, `"completed"`, `"interrupted"` — consistent across models, valve_runner, and CSS badge classes ✓
- `ZoneConfig.et_deficit_mm` — read and written in scheduler.py, weather_status.py, schedules.py ✓

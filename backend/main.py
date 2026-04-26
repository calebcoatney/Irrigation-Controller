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

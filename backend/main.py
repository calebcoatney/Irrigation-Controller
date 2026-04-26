from fastapi import FastAPI, HTTPException, Depends
from relay import RelayController, RelayError

app = FastAPI()

_relay = RelayController()


def get_relay() -> RelayController:
    return _relay


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

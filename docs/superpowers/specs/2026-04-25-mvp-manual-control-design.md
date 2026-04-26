# Irrigation Controller — MVP Manual Control Design

**Date:** 2026-04-25
**Scope:** MVP — manual open/close of two drip irrigation zones via browser UI. No scheduling, no weather integration.

---

## Hardware Context

- **Server:** Ubuntu home server
- **Relay:** NOYITO 2-Channel USB relay module (CH341 USB-to-serial bridge)
- **Device path:** `/dev/irrigation_relay` (udev symlink → `ttyUSB0`)
- **Protocol:** 9600 baud serial, 4-byte hex commands
- **Valves:** 24VAC solenoids — Zone 1 (front yard), Zone 2 (back yard)
- **Network:** Tailscale private network; no public exposure, no auth required

### Relay Hex Commands

| Action        | Bytes                  |
|---------------|------------------------|
| Valve 1 ON    | `\xA0\x01\x01\xA2`    |
| Valve 1 OFF   | `\xA0\x01\x00\xA1`    |
| Valve 2 ON    | `\xA0\x02\x01\xA3`    |
| Valve 2 OFF   | `\xA0\x02\x00\xA2`    |

---

## Architecture

Three-tier, two-container Docker Compose setup:

```
Browser → Nginx (port 80)
            ├── static files → built React bundle (/dist)
            └── /api/* → FastAPI container (port 8000)
                            └── pyserial → /dev/irrigation_relay
```

**Dev workflow:** FastAPI runs via `uvicorn` in the `irrigation-env` mamba environment on the desktop. React runs via Vite dev server on `:5173`, which proxies `/api` to `:8000`. No Docker required during development.

**Deploy workflow:** `git push` on desktop → `git pull` on server → `docker compose up --build -d`.

**Server filesystem convention:**
- App lives at `/srv/irrigation-controller/app` (repo cloned here)
- Persistent data at `/srv/irrigation-controller/data` (used by future scheduler/DB)

---

## Project Structure

```
irrigation-controller/
├── backend/
│   ├── main.py              # FastAPI app, route definitions
│   ├── relay.py             # RelayController class, serial logic
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # root component, zone cards
│   │   └── main.jsx         # React entry point
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js       # dev proxy: /api → localhost:8000
│   └── Dockerfile           # multi-stage: Node build → Nginx
├── nginx/
│   └── nginx.conf           # serve /dist, proxy /api → backend:8000
├── docker-compose.yml
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-25-mvp-manual-control-design.md
```

---

## Backend

### API Endpoints

| Method | Path                    | Description                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/api/status`           | Returns current state of both valves |
| POST   | `/api/valve/{id}/open`  | Opens valve 1 or 2                   |
| POST   | `/api/valve/{id}/close` | Closes valve 1 or 2                  |

**Response shape (`/api/status`):**
```json
{
  "valve_1": "open" | "closed",
  "valve_2": "open" | "closed"
}
```

All valve command endpoints return the same shape with updated state.

### `relay.py` — RelayController

- Holds a command table mapping (valve_id, action) → bytes
- Tracks valve state in an in-memory dict (resets on restart — acceptable for MVP)
- `open_valve(id)` / `close_valve(id)` write the appropriate bytes to the serial port
- `send_command(bytes)` opens the port, writes, closes — stateless serial access
- Port opens and closes per command (no persistent connection needed at this volume)

### Error Handling

- If `/dev/irrigation_relay` is not found at startup, the app starts normally but valve endpoints return `HTTP 503` with a descriptive message
- Invalid valve IDs (not 1 or 2) return `HTTP 422`
- This allows frontend development on the desktop without relay hardware attached

### `main.py`

- Instantiates one `RelayController` at startup
- Injects it into route handlers
- Exposes the three endpoints above

---

## Frontend

### UI

- Two zone cards (Front Yard, Back Yard), side by side on desktop, stacked on mobile
- Each card displays:
  - Zone name
  - State badge: "Open" (green) / "Closed" (gray)
  - Toggle button: "Open Zone" when closed, "Close Zone" when open
  - Loading spinner on button while API call is in-flight (prevents double-clicks)
- Top-level status banner when backend is unreachable (503 or network error)

### State Management

- Plain React: `useState` + `useEffect`, no external state library
- On mount: `GET /api/status` populates initial valve states
- On toggle: optimistic-free — button spins, awaits response, then updates state from response

### Stack

- React 18 + Vite
- No component library (keeps bundle small, code readable)
- Plain `fetch` for API calls

---

## Docker & Deployment

### `backend/Dockerfile`

- Base: `python:3.12-slim`
- Installs `requirements.txt`
- Entrypoint: `uvicorn main:app --host 0.0.0.0 --port 8000`

### `frontend/Dockerfile`

- Stage 1 (Node): `npm ci && npm run build` → produces `/dist`
- Stage 2 (Nginx): copies `/dist` and `nginx.conf`, exposes port 80

### `nginx/nginx.conf`

- Serves static files from `/dist`
- Proxies `/api/` to `http://backend:8000`

### `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    devices:
      - /dev/irrigation_relay:/dev/irrigation_relay
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

---

## Future Scope (out of MVP)

- Schedule-based watering (will add a DB service to compose)
- Weather API integration for smart watering decisions
- Persistent valve state across restarts

# Irrigation Controller — Sophisticated Dashboard Design

**Date:** 2026-04-26
**Scope:** ET-based scheduling, weather integration, run history, and a tabbed dashboard UI. Builds on the MVP manual control spec (2026-04-25).

---

## Architecture

The existing two-container setup gains one SQLite volume and a scheduler thread. No new containers.

```
Browser → Nginx (port 80)
            ├── static files → built React bundle
            └── /api/* → FastAPI container (port 8000)
                            ├── APScheduler (in-process thread)
                            ├── SQLite DB (/data/irrigation.db)
                            ├── Open-Meteo API (outbound HTTP, no key required)
                            └── pyserial → /dev/irrigation_relay
```

The Docker volume at `/srv/irrigation-controller/data` mounts into the backend container at `/data`. APScheduler uses SQLite as its job store so schedules survive container restarts.

**Safety rule:** every scheduled run has a hard `max_duration` cutoff. The scheduler job closes the valve itself after N minutes regardless of API state, preventing a stuck-open valve.

---

## Data Model

Three SQLite tables managed via SQLModel.

### `zone_config`

One row per zone. Relatively static after initial setup.

| Column | Type | Description |
|--------|------|-------------|
| `zone_id` | int (PK) | 1 or 2 |
| `name` | str | Display name (e.g. "Front Yard") |
| `lat` | float | Latitude for Open-Meteo |
| `lng` | float | Longitude for Open-Meteo |
| `et_coefficient` | float | FAO-56 crop coefficient (e.g. 0.8 for lawn, 0.5 for drip/shrubs) |
| `application_rate_mm_per_min` | float | How much water the system delivers per minute |
| `et_deficit_mm` | float | Running ET deficit — updated nightly |

### `schedules`

One row per zone.

| Column | Type | Description |
|--------|------|-------------|
| `zone_id` | int (FK → zone_config) | |
| `enabled` | bool | Whether automated scheduling is active |
| `preferred_time` | str | HH:MM in server local time — when to check and run if threshold met |
| `et_threshold_mm` | float | Accumulated deficit that triggers a run |
| `max_duration_seconds` | int | Hard safety ceiling on run length |

### `run_records`

Append-only log of all runs.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int (PK) | |
| `zone_id` | int (FK) | |
| `started_at` | datetime | |
| `ended_at` | datetime | Null if interrupted |
| `trigger` | str | `manual` or `scheduled` |
| `et_deficit_mm` | float | Deficit at time of trigger |
| `precipitation_mm` | float | Previous 24h precipitation |
| `duration_seconds` | int | Actual run length |
| `status` | str | `completed` or `interrupted` |

---

## ET Scheduling Logic

Two APScheduler jobs run as background threads inside the FastAPI process.

### Nightly ET Sync (~midnight)

Calls Open-Meteo's daily historical API for each zone's coordinates. Fetches `et0_fao_evapotranspiration` and `precipitation_sum` for yesterday. Updates each zone's running deficit:

```
deficit += (ET × et_coefficient) - precipitation_sum
deficit = max(deficit, 0)   # never go negative
```

Open-Meteo endpoint used: `https://api.open-meteo.com/v1/forecast` with `daily=et0_fao_evapotranspiration,precipitation_sum`.

### Morning Schedule Check (at each zone's `preferred_time`)

For each enabled zone: if `et_deficit_mm >= et_threshold_mm`, calculate run duration:

```
duration_minutes = deficit / application_rate_mm_per_min
duration_seconds = min(duration_minutes × 60, max_duration_seconds)
```

Opens the valve, logs the run record, closes the valve after `duration_seconds`, resets `et_deficit_mm` to zero.

### ET Coefficient Reference

Standard FAO-56 crop coefficients for common use cases:

| Plant type | Typical `et_coefficient` |
|------------|--------------------------|
| Cool-season grass lawn | 0.80 |
| Warm-season grass lawn | 0.65 |
| Established shrubs / drip | 0.50 |
| Vegetable garden | 1.00 |

---

## Backend API

### Existing (unchanged)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Current valve states |
| POST | `/api/valve/{id}/open` | Raw open (manual) |
| POST | `/api/valve/{id}/close` | Raw close (manual) |

### Zone Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/zones` | Both zones with full config |
| PUT | `/api/zones/{id}/config` | Update name, lat/lng, ET coefficient, application rate |

### Schedules

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/zones/{id}/schedule` | Get schedule for a zone |
| PUT | `/api/zones/{id}/schedule` | Update schedule settings |
| POST | `/api/zones/{id}/schedule/run-now` | Manual trigger (logged as `manual`, respects max_duration, auto-closes) |

### Run History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/runs` | Paginated run list, most recent first. Optional `?zone_id=` filter. |
| GET | `/api/runs/{id}` | Full detail for a single run |

### Weather / ET Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/weather/status` | Current deficit per zone, last sync time, today's forecast ET and precipitation |

---

## Frontend

Tabbed single-page app. React Router for navigation. No component library — same lean aesthetic as the current UI. Audience: two people, one of whom prefers simplicity and elegance. Design principle: clean on the surface, detail available on demand.

### Dashboard (default tab)

- Existing zone cards retained
- Each card gains: current ET deficit and next scheduled run time
- Weather strip above the cards: today's forecast ET and precipitation in plain language (e.g. "Expecting 0.3mm rain, ET 4.1mm today")
- "Run Now" button replaces raw open/close toggle — triggers `POST /api/zones/{id}/schedule/run-now`, auto-closes, logs the run. Duration uses the same ET formula as a scheduled run (deficit / application_rate, capped at max_duration). If the deficit is zero, it runs for a configurable fallback duration (default: 5 minutes).

### Schedule Tab

- One panel per zone
- Enable/disable toggle
- Time picker for `preferred_time`
- Numeric inputs for ET threshold (mm) and max duration (minutes)
- Read-only "estimated next run" line — recomputes from current deficit vs. threshold

### History Tab

- Reverse-chronological list of run events
- Each row: zone name, date/time, duration, trigger badge (Manual / Scheduled), status
- Click/tap to expand inline detail: ET deficit at trigger, precipitation, ET coefficient, computed duration rationale
- Default: last 30 runs; "Load more" at bottom

### Settings Tab

- Zone names
- Latitude / longitude (drives Open-Meteo calls)
- ET coefficient per zone (with crop type reference shown inline)
- Application rate per zone (mm/min)

---

## Docker & Deployment Changes

Add a named volume to `docker-compose.yml`:

```yaml
services:
  backend:
    volumes:
      - irrigation-data:/data

volumes:
  irrigation-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /srv/irrigation-controller/data
```

No other container or network changes needed.

---

## Out of Scope

- Push notifications / alerts (e.g. "Zone 1 ran today")
- Soil moisture sensors (hardware addition)
- Multi-user auth (Tailscale private network is the security boundary)
- More than 2 zones

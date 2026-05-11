# Reset Water Debt — Design Spec

**Date:** 2026-05-11

## Summary

Add a "Reset water debt" action to the Schedule tab. Each zone panel gets a water debt display and a button that opens a confirmation modal. On confirm, the backend zeroes `et_deficit_mm` for that zone.

## Backend

**New endpoint** in `backend/routers/zones.py`:

```
POST /api/zones/{zone_id}/reset-deficit
```

- Sets `zone.et_deficit_mm = 0.0`
- Commits and returns the updated `ZoneConfig`
- Returns 404 if zone not found

No new models or migrations needed — `et_deficit_mm` already exists on `ZoneConfig`.

## Frontend

### 1. `ConfirmModal` component (`frontend/src/components/ConfirmModal.jsx`)

A minimal shared modal with a backdrop. Props:

| Prop | Type | Description |
|------|------|-------------|
| `title` | string | Modal heading |
| `message` | string | Body text |
| `confirmLabel` | string | Confirm button text (default "Confirm") |
| `onConfirm` | function | Called when user confirms |
| `onCancel` | function | Called when user cancels or clicks backdrop |

Renders as a fixed backdrop + centered dialog. No external library. Closing on backdrop click and Escape key is nice-to-have but not required for v1.

### 2. Water debt display in `SchedulePanel`

Add above the existing `schedule-estimate` paragraph:

```
Water debt: X.X mm
```

Matches the style of the existing debt display in `ZoneCard`. Sourced from `zone.et_deficit_mm` (live prop).

### 3. Reset button in `SchedulePanel`

- Secondary/muted button below the water debt line: "Reset water debt"
- Click opens `ConfirmModal` with:
  - Title: `"Reset water debt"`
  - Message: `"Reset water debt for {zone.name} to 0 mm?"`
  - Confirm label: `"Reset"`
- On confirm: call `resetDeficit(zone_id)` API function, then re-fetch zones in the parent `Schedule` component

### 4. API client (`frontend/src/api.js`)

Add:

```js
export async function resetDeficit(zoneId) { ... }
```

Calls `POST /api/zones/{zoneId}/reset-deficit`.

### 5. Data flow in `Schedule`

- Pass `onResetDeficit` callback from `Schedule` → `SchedulePanel`
- Callback: calls `resetDeficit(zone_id)`, then re-fetches all zones and updates `zones` state
- `SchedulePanel` reads `deficit` from live `zone` prop, so it updates automatically on re-render

## CSS

- `ConfirmModal`: backdrop (`position: fixed`, semi-transparent), centered dialog card — new styles in `App.css`
- Reset button: secondary/muted style (distinct from the primary Save button and run/stop buttons)

## Testing

Existing backend tests cover zone endpoints. Add one test to `test_zones_api.py`:

- `test_reset_deficit` — seeds a zone with nonzero deficit, calls the endpoint, asserts `et_deficit_mm == 0.0`

No frontend test changes required.

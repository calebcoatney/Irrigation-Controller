# Reset Water Debt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Reset water debt" button to the Schedule tab that zeroes a zone's ET deficit via a confirmation modal, and display water debt in each zone's schedule panel.

**Architecture:** New `POST /api/zones/{zone_id}/reset-deficit` endpoint sets `et_deficit_mm = 0.0`. Frontend adds a `ConfirmModal` component, wires a reset button into `SchedulePanel`, and re-fetches zones after reset so the debt display updates live.

**Tech Stack:** Python/FastAPI/SQLModel (backend), React (frontend), plain CSS (no component libraries)

---

### Task 1: Backend — reset-deficit endpoint + test

**Files:**
- Modify: `backend/routers/zones.py`
- Modify: `backend/tests/test_zones_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_zones_api.py`:

```python
@pytest.fixture(name="client_with_engine")
def client_with_engine_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ZoneConfig(zone_id=1, name="Front Yard", lat=40.0, lng=-105.0, et_deficit_mm=12.5))
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    test_app.dependency_overrides[get_session] = override
    yield TestClient(test_app), engine
    test_app.dependency_overrides.clear()


def test_reset_deficit(client_with_engine):
    tc, engine = client_with_engine
    resp = tc.post("/api/zones/1/reset-deficit")
    assert resp.status_code == 200
    assert resp.json()["et_deficit_mm"] == pytest.approx(0.0)
    with Session(engine) as s:
        zone = s.get(ZoneConfig, 1)
        assert zone.et_deficit_mm == pytest.approx(0.0)


def test_reset_deficit_not_found(client_with_engine):
    tc, _ = client_with_engine
    resp = tc.post("/api/zones/99/reset-deficit")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_zones_api.py::test_reset_deficit tests/test_zones_api.py::test_reset_deficit_not_found -v
```

Expected: FAIL — `404 Not Found` (endpoint doesn't exist yet)

- [ ] **Step 3: Add the endpoint to `backend/routers/zones.py`**

Add after the existing `update_zone_config` route:

```python
@router.post("/api/zones/{zone_id}/reset-deficit")
def reset_deficit(
    zone_id: int,
    session: Session = Depends(get_session),
) -> ZoneConfig:
    zone = session.get(ZoneConfig, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    zone.et_deficit_mm = 0.0
    session.add(zone)
    session.commit()
    session.refresh(zone)
    return zone
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_zones_api.py -v
```

Expected: all pass

- [ ] **Step 5: Run full backend test suite to check for regressions**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/zones.py backend/tests/test_zones_api.py
git commit -m "feat: POST /api/zones/{zone_id}/reset-deficit endpoint"
```

---

### Task 2: Frontend — add `resetDeficit` to api.js

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Add the function**

In `frontend/src/api.js`, add after the `stopZone` export:

```js
export const resetDeficit = (id) =>
  request(`/api/zones/${id}/reset-deficit`, { method: "POST" });
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add resetDeficit api call"
```

---

### Task 3: Frontend — ConfirmModal component + styles

**Files:**
- Create: `frontend/src/components/ConfirmModal.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create `frontend/src/components/ConfirmModal.jsx`**

```jsx
import { useEffect } from "react";

export default function ConfirmModal({ title, message, confirmLabel = "Confirm", onConfirm, onCancel }) {
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onCancel(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel}>Cancel</button>
          <button className="btn-stop" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add modal + reset button styles to `frontend/src/App.css`**

Append to the end of `App.css`:

```css
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; padding: 1.5rem; max-width: 360px; width: 90%; display: flex; flex-direction: column; gap: 1rem; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.modal h3 { font-size: 1rem; font-weight: 600; margin: 0; }
.modal p { font-size: 0.875rem; color: #78716c; margin: 0; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }
.modal-actions .btn-stop { width: auto; padding: 0.4rem 0.9rem; font-size: 0.875rem; }
.btn-reset-debt { background: none; color: #a8a29e; font-size: 0.78rem; padding: 0; border: none; text-decoration: underline; text-underline-offset: 2px; cursor: pointer; align-self: flex-start; }
.btn-reset-debt:hover { color: #dc2626; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ConfirmModal.jsx frontend/src/App.css
git commit -m "feat: ConfirmModal component and modal/reset styles"
```

---

### Task 4: Frontend — water debt display + reset button in SchedulePanel

**Files:**
- Modify: `frontend/src/pages/Schedule.jsx`

- [ ] **Step 1: Update `SchedulePanel` and `Schedule` in `frontend/src/pages/Schedule.jsx`**

Replace the entire file with:

```jsx
import { useState, useEffect } from "react";
import { getZones, getSchedule, updateSchedule, resetDeficit } from "../api";
import ConfirmModal from "../components/ConfirmModal";

function SchedulePanel({ zone, initialSchedule, onResetDeficit }) {
  const [sched, setSched] = useState(initialSchedule);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const deficit = zone.et_deficit_mm;
  const threshold = sched.et_threshold_mm;
  const ratePerMin = zone.application_rate_mm_per_min;

  function estimateDurationMin(d) {
    if (!ratePerMin || ratePerMin <= 0) return null;
    const sec = Math.min(Math.ceil((d / ratePerMin) * 60), sched.max_duration_seconds);
    return Math.ceil(sec / 60);
  }

  let estimate;
  if (!sched.enabled) {
    estimate = "Scheduling disabled";
  } else if (deficit >= threshold) {
    const dur = estimateDurationMin(deficit);
    estimate = dur ? `Ready — will run ~${dur}m at ${sched.preferred_time}` : `Ready — will run at ${sched.preferred_time}`;
  } else {
    const needed = (threshold - deficit).toFixed(1);
    const days = Math.ceil((threshold - deficit) / 4);
    estimate = `Need ${needed}mm more (~${days} day${days !== 1 ? "s" : ""} at typical ET)`;
  }

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

  async function handleConfirmReset() {
    setConfirming(false);
    await onResetDeficit(zone.zone_id);
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
      <div className="zone-meta">
        <span>Water debt: <strong>{deficit.toFixed(1)} mm</strong></span>
        <button className="btn-reset-debt" onClick={() => setConfirming(true)}>
          Reset water debt
        </button>
      </div>
      <p className="schedule-estimate">{estimate}</p>
      <button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : saved ? "Saved" : "Save"}
      </button>
      {confirming && (
        <ConfirmModal
          title="Reset water debt"
          message={`Reset water debt for ${zone.name} to 0 mm?`}
          confirmLabel="Reset"
          onConfirm={handleConfirmReset}
          onCancel={() => setConfirming(false)}
        />
      )}
    </div>
  );
}

function ETExplainer() {
  const [open, setOpen] = useState(false);
  return (
    <div className="explainer">
      <button className="explainer-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} How ET scheduling works
      </button>
      {open && (
        <div className="explainer-body">
          <p>
            <strong>Evapotranspiration (ET)</strong> is the amount of water plants lose to the atmosphere each day — through evaporation from the soil and transpiration through leaves. It's driven by temperature, humidity, wind, and sunlight.
          </p>
          <p>
            Each night, the controller fetches yesterday's ET and rainfall from Open-Meteo (a free weather API) using your zone's coordinates. It then updates a running <strong>water debt</strong>:
          </p>
          <pre className="explainer-formula">debt += (ET × crop coefficient) − rainfall{"\n"}debt = max(debt, 0)   {/* never goes negative */}</pre>
          <p>
            The <strong>crop coefficient</strong> adjusts raw ET for your plant type — grass uses about 80% of reference ET, drip-irrigated shrubs about 50%.
          </p>
          <p>
            When the debt reaches your <strong>threshold</strong>, the controller runs the zone long enough to pay it back:
          </p>
          <pre className="explainer-formula">run time = debt ÷ application rate{"\n"}         (capped at max duration)</pre>
          <p>
            After a run, the debt resets to zero. Rain heavy enough to exceed the day's ET reduces the debt directly, so the system skips watering on rainy days automatically.
          </p>
        </div>
      )}
    </div>
  );
}

export default function Schedule() {
  const [zones, setZones] = useState([]);
  const [schedules, setSchedules] = useState({});
  const [error, setError] = useState(null);

  async function loadData() {
    const zs = await getZones();
    const scheds = await Promise.all(zs.map((z) => getSchedule(z.zone_id)));
    setZones(zs);
    setSchedules(Object.fromEntries(scheds.map((s) => [s.zone_id, s])));
  }

  useEffect(() => {
    loadData().catch(() => setError("Cannot reach backend"));
  }, []);

  async function handleResetDeficit(zoneId) {
    await resetDeficit(zoneId);
    await loadData();
  }

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      <div className="schedule-panels">
        {zones.map((z) =>
          schedules[z.zone_id] ? (
            <SchedulePanel
              key={z.zone_id}
              zone={z}
              initialSchedule={schedules[z.zone_id]}
              onResetDeficit={handleResetDeficit}
            />
          ) : null
        )}
      </div>
      <ETExplainer />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Schedule.jsx
git commit -m "feat: water debt display and reset button on Schedule tab"
```

---

### Task 5: Verify and push

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: all pass

- [ ] **Step 2: Start the frontend dev server and verify manually**

```bash
cd frontend && npm run dev
```

Check:
- Schedule tab shows "Water debt: X.X mm" for each zone
- "Reset water debt" link appears below it
- Clicking opens a modal with zone name in the message
- Cancel closes without changes
- Escape key closes without changes
- Clicking the backdrop closes without changes
- Confirm resets the debt to 0.0 and the display updates immediately

- [ ] **Step 3: Push**

```bash
git push
```

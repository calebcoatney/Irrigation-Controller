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

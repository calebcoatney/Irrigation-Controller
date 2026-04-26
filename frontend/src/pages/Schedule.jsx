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

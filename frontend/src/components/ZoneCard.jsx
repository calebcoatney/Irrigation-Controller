function estimateDurationMin(deficitMm, ratePerMin, maxSec) {
  if (!ratePerMin || ratePerMin <= 0) return null;
  const sec = Math.min(Math.ceil((deficitMm / ratePerMin) * 60), maxSec);
  return Math.ceil(sec / 60);
}

export default function ZoneCard({ zone, schedule, valveState, loading, onRunNow, onStop }) {
  const isRunning = valveState === "open";
  const deficit = zone.et_deficit_mm;
  const threshold = schedule?.et_threshold_mm ?? null;
  const ready = threshold !== null && deficit >= threshold;

  let scheduleStatus = null;
  if (schedule?.enabled) {
    if (ready) {
      const dur = estimateDurationMin(deficit, zone.application_rate_mm_per_min, schedule.max_duration_seconds);
      scheduleStatus = `Ready — ~${dur}m at ${schedule.preferred_time}`;
    } else if (threshold !== null) {
      const needed = (threshold - deficit).toFixed(1);
      scheduleStatus = `${deficit.toFixed(1)} / ${threshold} mm · need ${needed}mm more`;
    }
  }

  return (
    <div className={`zone-card ${isRunning ? "running" : ""}`}>
      <div className="zone-card-header">
        <h2>{zone.name}</h2>
        <span className={`badge ${isRunning ? "open" : "closed"}`}>
          {isRunning ? "Running" : "Idle"}
        </span>
      </div>
      <div className="zone-meta">
        <span title="How much water this zone needs (accumulates nightly from weather data)">
          Water debt: <strong>{deficit.toFixed(1)} mm</strong>
        </span>
        {scheduleStatus && (
          <span className={`schedule-status ${ready ? "schedule-ready" : ""}`}>
            {scheduleStatus}
          </span>
        )}
        {schedule && !schedule.enabled && (
          <span className="schedule-status muted">Scheduling off</span>
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

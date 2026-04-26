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

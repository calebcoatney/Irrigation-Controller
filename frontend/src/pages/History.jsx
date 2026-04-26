import { useState, useEffect } from "react";
import { getRuns, deleteRun, deleteAllRuns } from "../api";

function formatDuration(seconds) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function RunRow({ run, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr className={`run-row ${run.status}`} onClick={() => setExpanded((e) => !e)} style={{ cursor: "pointer" }}>
        <td>Zone {run.zone_id}</td>
        <td>{formatDate(run.started_at)}</td>
        <td>{formatDuration(run.duration_seconds)}</td>
        <td><span className={`badge trigger-${run.trigger}`}>{run.trigger}</span></td>
        <td><span className={`badge status-${run.status}`}>{run.status}</span></td>
        <td>
          <button
            className="btn-delete-row"
            title="Delete this run"
            onClick={(e) => { e.stopPropagation(); onDelete(run.id); }}
          >×</button>
        </td>
      </tr>
      {expanded && (
        <tr className="run-detail">
          <td colSpan={6}>
            <div className="run-detail-grid">
              <span>ET deficit at trigger:</span><strong>{run.et_deficit_mm.toFixed(2)} mm</strong>
              <span>Precipitation (24h):</span><strong>{run.precipitation_mm.toFixed(2)} mm</strong>
              <span>Trigger:</span><strong>{run.trigger}</strong>
              <span>Status:</span><strong>{run.status}</strong>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function History() {
  const [runs, setRuns] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState(null);
  const LIMIT = 30;

  useEffect(() => {
    getRuns({ limit: LIMIT + 1, offset: 0 })
      .then((data) => {
        setHasMore(data.length > LIMIT);
        setRuns(data.slice(0, LIMIT));
        setOffset(LIMIT);
      })
      .catch(() => setError("Cannot reach backend"));
  }, []);

  async function loadMore() {
    const data = await getRuns({ limit: LIMIT + 1, offset });
    setHasMore(data.length > LIMIT);
    setRuns((prev) => [...prev, ...data.slice(0, LIMIT)]);
    setOffset((o) => o + LIMIT);
  }

  async function handleDeleteRun(id) {
    await deleteRun(id);
    setRuns((prev) => prev.filter((r) => r.id !== id));
  }

  async function handleClearAll() {
    if (!window.confirm("Delete all run history?")) return;
    await deleteAllRuns();
    setRuns([]);
    setHasMore(false);
    setOffset(0);
  }

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      {runs.length > 0 && (
        <div className="history-toolbar">
          <button className="btn-clear-all" onClick={handleClearAll}>Clear all</button>
        </div>
      )}
      {runs.length === 0 ? (
        <p className="empty">No runs recorded yet.</p>
      ) : (
        <table className="run-table">
          <thead>
            <tr>
              <th>Zone</th><th>Started</th><th>Duration</th><th>Trigger</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => <RunRow key={r.id} run={r} onDelete={handleDeleteRun} />)}
          </tbody>
        </table>
      )}
      {hasMore && (
        <button className="load-more" onClick={loadMore}>Load more</button>
      )}
    </div>
  );
}

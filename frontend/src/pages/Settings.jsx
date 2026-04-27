import { useState, useEffect } from "react";
import { getZones, updateZoneConfig } from "../api";

const ET_REFERENCE = [
  { label: "Cool-season grass lawn", value: 0.80 },
  { label: "Warm-season grass lawn", value: 0.65 },
  { label: "Established shrubs / drip", value: 0.50 },
  { label: "Vegetable garden", value: 1.00 },
];

function DripCalculator({ onApply }) {
  const [open, setOpen] = useState(false);
  const [gph, setGph] = useState(0.5);
  const [emitterSpacing, setEmitterSpacing] = useState(6);
  const [rowSpacing, setRowSpacing] = useState(10);

  // PR (in/hr) = 231 × GPH / (emitter_spacing_in × row_spacing_in)
  const rateInPerHr = (231 * gph) / (emitterSpacing * rowSpacing);
  const rateMmPerMin = (rateInPerHr * 25.4) / 60;

  if (!open) {
    return (
      <button type="button" className="btn-drip-calc" onClick={() => setOpen(true)}>
        Calculate from drip specs…
      </button>
    );
  }

  return (
    <div className="drip-calc">
      <p className="drip-calc-title">Drip line calculator</p>
      <div className="drip-calc-fields">
        <label>
          Emitter flow rate (GPH)
          <input type="number" step="0.1" min="0.1" value={gph}
            onChange={(e) => setGph(parseFloat(e.target.value))} />
        </label>
        <label>
          Emitter spacing (inches)
          <input type="number" step="1" min="1" value={emitterSpacing}
            onChange={(e) => setEmitterSpacing(parseFloat(e.target.value))} />
        </label>
        <label>
          Row spacing (inches)
          <input type="number" step="1" min="1" value={rowSpacing}
            onChange={(e) => setRowSpacing(parseFloat(e.target.value))} />
        </label>
      </div>
      <div className="drip-calc-result">
        <span>= <strong>{rateMmPerMin.toFixed(2)} mm/min</strong></span>
        <div className="drip-calc-actions">
          <button type="button" className="btn-apply" onClick={() => { onApply(parseFloat(rateMmPerMin.toFixed(2))); setOpen(false); }}>
            Apply
          </button>
          <button type="button" className="btn-cancel" onClick={() => setOpen(false)}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

function ZoneSettings({ initialZone }) {
  const [zone, setZone] = useState(initialZone);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateZoneConfig(zone.zone_id, {
        name: zone.name,
        lat: zone.lat,
        lng: zone.lng,
        et_coefficient: zone.et_coefficient,
        application_rate_mm_per_min: zone.application_rate_mm_per_min,
      });
      setZone(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="settings-panel">
      <h2>Zone {zone.zone_id}</h2>
      <div className="settings-fields">
        <label>
          Name
          <input value={zone.name} onChange={(e) => setZone({ ...zone, name: e.target.value })} />
        </label>
        <label>
          Latitude
          <input type="number" step="0.0001" value={zone.lat}
            onChange={(e) => setZone({ ...zone, lat: parseFloat(e.target.value) })} />
        </label>
        <label>
          Longitude
          <input type="number" step="0.0001" value={zone.lng}
            onChange={(e) => setZone({ ...zone, lng: parseFloat(e.target.value) })} />
        </label>
        <label>
          ET coefficient
          <input type="number" step="0.05" min="0.1" max="1.5" value={zone.et_coefficient}
            onChange={(e) => setZone({ ...zone, et_coefficient: parseFloat(e.target.value) })} />
          <span className="field-hint">
            Reference: {ET_REFERENCE.map((r) => `${r.label} = ${r.value}`).join(" · ")}
          </span>
        </label>
        <label>
          Application rate (mm/min)
          <input type="number" step="0.01" min="0.01" value={zone.application_rate_mm_per_min}
            onChange={(e) => setZone({ ...zone, application_rate_mm_per_min: parseFloat(e.target.value) })} />
        </label>
        <DripCalculator onApply={(rate) => setZone({ ...zone, application_rate_mm_per_min: rate })} />
      </div>
      <button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : saved ? "Saved" : "Save"}
      </button>
    </div>
  );
}

export default function Settings() {
  const [zones, setZones] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    getZones().then(setZones).catch(() => setError("Cannot reach backend"));
  }, []);

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;

  return (
    <div className="page">
      <div className="settings-panels">
        {zones.map((z) => <ZoneSettings key={z.zone_id} initialZone={z} />)}
      </div>
    </div>
  );
}

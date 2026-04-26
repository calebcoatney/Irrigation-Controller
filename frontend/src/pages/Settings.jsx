import { useState, useEffect } from "react";
import { getZones, updateZoneConfig } from "../api";

const ET_REFERENCE = [
  { label: "Cool-season grass lawn", value: 0.80 },
  { label: "Warm-season grass lawn", value: 0.65 },
  { label: "Established shrubs / drip", value: 0.50 },
  { label: "Vegetable garden", value: 1.00 },
];

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
          <input type="number" step="0.1" min="0.1" value={zone.application_rate_mm_per_min}
            onChange={(e) => setZone({ ...zone, application_rate_mm_per_min: parseFloat(e.target.value) })} />
        </label>
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

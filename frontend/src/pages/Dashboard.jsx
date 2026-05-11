import { useState, useEffect } from "react";
import ZoneCard from "../components/ZoneCard";
import WeatherStrip from "../components/WeatherStrip";
import { getStatus, getZones, getSchedule, getWeatherStatus, runNow, stopZone } from "../api";

export default function Dashboard() {
  const [status, setStatus] = useState({ valve_1: "closed", valve_2: "closed" });
  const [zones, setZones] = useState([]);
  const [schedules, setSchedules] = useState({});
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getStatus().then(setStatus),
      getZones().then((zs) => {
        setZones(zs);
        return Promise.all(zs.map((z) => getSchedule(z.zone_id)));
      }).then((scheds) =>
        setSchedules(Object.fromEntries(scheds.map((s) => [s.zone_id, s])))
      ),
      getWeatherStatus().then((ws) => { setForecast(ws.forecast); }),
    ]).catch(() => setError("Cannot reach backend"));
  }, []);

  async function refreshZonesAndStatus() {
    const [s, zs] = await Promise.all([getStatus(), getZones()]);
    setStatus(s);
    setZones(zs);
  }

  async function handleRunNow(id) {
    setLoading((l) => ({ ...l, [id]: true }));
    try {
      await runNow(id);
      await refreshZonesAndStatus();
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((l) => ({ ...l, [id]: false }));
    }
  }

  async function handleStop(id) {
    setLoading((l) => ({ ...l, [id]: true }));
    try {
      await stopZone(id);
      await refreshZonesAndStatus();
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading((l) => ({ ...l, [id]: false }));
    }
  }

  return (
    <div className="page">
      {error && <div className="error-banner">{error}</div>}
      <WeatherStrip
        forecast={forecast}
        locationName={zones[0]?.name}
        hasCoords={zones.length > 0 && (zones[0].lat !== 0 || zones[0].lng !== 0)}
      />
      <div className="zones">
        {zones.map((zone) => (
          <ZoneCard
            key={zone.zone_id}
            zone={zone}
            schedule={schedules[zone.zone_id]}
            valveState={status[`valve_${zone.zone_id}`]}
            loading={loading[zone.zone_id] ?? false}
            onRunNow={handleRunNow}
            onStop={handleStop}
          />
        ))}
      </div>
    </div>
  );
}

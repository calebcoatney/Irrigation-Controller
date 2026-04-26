export default function WeatherStrip({ forecast, locationName, hasCoords }) {
  if (!hasCoords) {
    return (
      <div className="weather-strip weather-unconfigured">
        No location set — enter lat/lng in <strong>Settings</strong> to enable weather &amp; ET tracking
      </div>
    );
  }
  if (!forecast) return null;
  const { et_mm, precip_mm } = forecast;
  return (
    <div className="weather-strip">
      <span className="weather-location">{locationName}</span>
      <span>ET: <strong>{et_mm.toFixed(1)} mm</strong></span>
      <span>Rain: <strong>{precip_mm.toFixed(1)} mm</strong></span>
      {precip_mm >= et_mm && <span className="weather-note">Rain covers ET today</span>}
    </div>
  );
}

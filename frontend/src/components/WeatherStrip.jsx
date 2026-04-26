export default function WeatherStrip({ forecast }) {
  if (!forecast) return null;
  const { et_mm, precip_mm } = forecast;
  return (
    <div className="weather-strip">
      <span>Today — ET: <strong>{et_mm.toFixed(1)} mm</strong></span>
      <span>Rain: <strong>{precip_mm.toFixed(1)} mm</strong></span>
      {precip_mm >= et_mm && <span className="weather-note">Rain covers ET today</span>}
    </div>
  );
}

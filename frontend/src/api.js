const JSON_HEADERS = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const resp = await fetch(path, options);
  const data = await resp.json();
  if (!resp.ok) throw Object.assign(new Error(data.detail || "Request failed"), { status: resp.status });
  return data;
}

export const getStatus = () => request("/api/status");
export const getZones = () => request("/api/zones");
export const updateZoneConfig = (id, body) =>
  request(`/api/zones/${id}/config`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) });
export const getSchedule = (id) => request(`/api/zones/${id}/schedule`);
export const updateSchedule = (id, body) =>
  request(`/api/zones/${id}/schedule`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) });
export const runNow = (id) => request(`/api/zones/${id}/schedule/run-now`, { method: "POST" });
export const stopZone = (id) => request(`/api/zones/${id}/stop`, { method: "POST" });
export const getRuns = (params = {}) =>
  request(`/api/runs?${new URLSearchParams(params)}`);
export const getRun = (id) => request(`/api/runs/${id}`);
export const deleteRun = (id) => request(`/api/runs/${id}`, { method: "DELETE" });
export const deleteAllRuns = () => request("/api/runs", { method: "DELETE" });
export const getWeatherStatus = () => request("/api/weather/status");

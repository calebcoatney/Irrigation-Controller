# MVP Manual Irrigation Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + React web app that lets you manually open and close two drip irrigation zone valves via a browser, containerized with Docker Compose for deployment to a home server.

**Architecture:** Nginx container serves the built React bundle and reverse-proxies `/api/*` to a FastAPI container; FastAPI sends 4-byte hex commands over USB serial to a NOYITO 2-channel relay board at `/dev/irrigation_relay`. Valve state is tracked in memory (resets on restart — acceptable for MVP). On dev desktop, FastAPI runs in a mamba env and Vite proxies `/api` to it; no Docker needed during development.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pyserial, pytest, httpx (backend); React 18, Vite (frontend); Nginx, Docker Compose (deployment); mamba env `irrigation-env` at `~/miniforge3/envs/irrigation-env`.

---

## File Map

| File | Purpose |
|------|---------|
| `backend/relay.py` | `RelayController` class — hex command table, serial writes, in-memory state |
| `backend/main.py` | FastAPI app — 3 endpoints, dependency injection of `RelayController` |
| `backend/requirements.txt` | Python prod + dev deps |
| `backend/pytest.ini` | pytest config: testpaths, pythonpath |
| `backend/Dockerfile` | Python 3.12-slim, installs deps, runs uvicorn |
| `backend/tests/test_relay.py` | Unit tests for `RelayController` (serial mocked) |
| `backend/tests/test_api.py` | API endpoint tests via FastAPI TestClient |
| `frontend/src/App.jsx` | Root component — two zone cards with toggle buttons |
| `frontend/src/App.css` | Minimal responsive styles |
| `frontend/src/main.jsx` | React entry point |
| `frontend/index.html` | Vite HTML shell |
| `frontend/vite.config.js` | Dev proxy: `/api` → `localhost:8000` |
| `frontend/package.json` | Node deps |
| `frontend/Dockerfile` | Multi-stage: Node build → Nginx |
| `nginx/nginx.conf` | Serve `/dist`, proxy `/api/` → `backend:8000` |
| `docker-compose.yml` | Wire services, pass `/dev/irrigation_relay` device |
| `.gitignore` | Ignore `__pycache__`, `node_modules`, `.env`, `dist` |

---

## Task 1: Project Scaffolding + Python Dependencies

**Files:**
- Create: `.gitignore`
- Create: `backend/pytest.ini`
- Create: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/tests frontend/src nginx
touch backend/tests/__init__.py
```

- [ ] **Step 2: Create .gitignore**

Create `.gitignore`:

```
__pycache__/
*.pyc
*.pyo
.env
node_modules/
dist/
.vite/
```

- [ ] **Step 3: Install Python dependencies into the mamba env**

```bash
conda activate irrigation-env
pip install "fastapi==0.115.12" "uvicorn[standard]==0.34.2" "pyserial==3.5" "pytest==8.3.5" "httpx==0.28.1"
```

- [ ] **Step 4: Create backend/requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
pyserial==3.5
pytest==8.3.5
httpx==0.28.1
```

- [ ] **Step 5: Create backend/pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/requirements.txt backend/pytest.ini backend/tests/__init__.py
git commit -m "chore: scaffold project structure and python deps"
```

---

## Task 2: Backend — relay.py (TDD)

**Files:**
- Create: `backend/tests/test_relay.py`
- Create: `backend/relay.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_relay.py`:

```python
from unittest.mock import patch
from relay import RelayController, COMMANDS


def test_initial_state_both_closed():
    ctrl = RelayController(port="/dev/fake")
    assert ctrl.status == {"valve_1": "closed", "valve_2": "closed"}


def test_command_table_has_all_four_commands():
    assert (1, "open") in COMMANDS
    assert (1, "close") in COMMANDS
    assert (2, "open") in COMMANDS
    assert (2, "close") in COMMANDS


def test_open_valve_1_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.open_valve(1)
        mock_ser.write.assert_called_once_with(b'\xA0\x01\x01\xA2')


def test_open_valve_2_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.open_valve(2)
        mock_ser.write.assert_called_once_with(b'\xA0\x02\x01\xA3')


def test_close_valve_1_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.close_valve(1)
        mock_ser.write.assert_called_once_with(b'\xA0\x01\x00\xA1')


def test_close_valve_2_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.close_valve(2)
        mock_ser.write.assert_called_once_with(b'\xA0\x02\x00\xA2')


def test_open_valve_updates_state():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial"):
        ctrl.open_valve(1)
    assert ctrl.status["valve_1"] == "open"
    assert ctrl.status["valve_2"] == "closed"


def test_close_valve_updates_state():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial"):
        ctrl.open_valve(2)
        ctrl.close_valve(2)
    assert ctrl.status["valve_2"] == "closed"


def test_available_false_when_port_missing():
    ctrl = RelayController(port="/dev/nonexistent_irrigation_device")
    assert ctrl.available is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
conda activate irrigation-env
cd backend
pytest tests/test_relay.py -v
```

Expected: `ModuleNotFoundError: No module named 'relay'` (or similar import error).

- [ ] **Step 3: Implement relay.py**

Create `backend/relay.py`:

```python
import os
import serial

COMMANDS: dict[tuple[int, str], bytes] = {
    (1, "open"):  b'\xA0\x01\x01\xA2',
    (1, "close"): b'\xA0\x01\x00\xA1',
    (2, "open"):  b'\xA0\x02\x01\xA3',
    (2, "close"): b'\xA0\x02\x00\xA2',
}

PORT = "/dev/irrigation_relay"
BAUD = 9600


class RelayController:
    def __init__(self, port: str = PORT):
        self.port = port
        self._state: dict[int, str] = {1: "closed", 2: "closed"}

    def _send(self, data: bytes) -> None:
        with serial.Serial(self.port, BAUD, timeout=1) as ser:
            ser.write(data)

    def open_valve(self, valve_id: int) -> None:
        self._send(COMMANDS[(valve_id, "open")])
        self._state[valve_id] = "open"

    def close_valve(self, valve_id: int) -> None:
        self._send(COMMANDS[(valve_id, "close")])
        self._state[valve_id] = "closed"

    @property
    def status(self) -> dict[str, str]:
        return {"valve_1": self._state[1], "valve_2": self._state[2]}

    @property
    def available(self) -> bool:
        return os.path.exists(self.port)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_relay.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/relay.py backend/tests/test_relay.py
git commit -m "feat: relay controller with serial command logic"
```

---

## Task 3: Backend — main.py (TDD)

**Files:**
- Create: `backend/tests/test_api.py`
- Create: `backend/main.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_api.py`:

```python
from unittest.mock import MagicMock, PropertyMock
import pytest
from fastapi.testclient import TestClient
from main import app, get_relay


def make_mock_relay(available: bool = True, state: dict | None = None) -> MagicMock:
    mock = MagicMock()
    type(mock).available = PropertyMock(return_value=available)
    mock.status = state or {"valve_1": "closed", "valve_2": "closed"}
    return mock


@pytest.fixture
def client():
    mock_relay = make_mock_relay()
    app.dependency_overrides[get_relay] = lambda: mock_relay
    yield TestClient(app), mock_relay
    app.dependency_overrides.clear()


@pytest.fixture
def client_unavailable():
    mock_relay = make_mock_relay(available=False)
    app.dependency_overrides[get_relay] = lambda: mock_relay
    yield TestClient(app), mock_relay
    app.dependency_overrides.clear()


def test_status_returns_both_valves(client):
    test_client, _ = client
    response = test_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "valve_1" in data
    assert "valve_2" in data


def test_open_valve_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "open", "valve_2": "closed"}
    response = test_client.post("/api/valve/1/open")
    assert response.status_code == 200
    mock_relay.open_valve.assert_called_once_with(1)
    assert response.json()["valve_1"] == "open"


def test_close_valve_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "closed", "valve_2": "closed"}
    response = test_client.post("/api/valve/1/close")
    assert response.status_code == 200
    mock_relay.close_valve.assert_called_once_with(1)


def test_open_valve_2_calls_controller(client):
    test_client, mock_relay = client
    mock_relay.status = {"valve_1": "closed", "valve_2": "open"}
    response = test_client.post("/api/valve/2/open")
    assert response.status_code == 200
    mock_relay.open_valve.assert_called_once_with(2)


def test_open_valve_503_when_relay_unavailable(client_unavailable):
    test_client, _ = client_unavailable
    response = test_client.post("/api/valve/1/open")
    assert response.status_code == 503
    assert "detail" in response.json()


def test_close_valve_503_when_relay_unavailable(client_unavailable):
    test_client, _ = client_unavailable
    response = test_client.post("/api/valve/1/close")
    assert response.status_code == 503


def test_invalid_valve_id_returns_422(client):
    test_client, _ = client
    response = test_client.post("/api/valve/3/open")
    assert response.status_code == 422


def test_invalid_valve_id_zero_returns_422(client):
    test_client, _ = client
    response = test_client.post("/api/valve/0/close")
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`.

- [ ] **Step 3: Implement main.py**

Create `backend/main.py`:

```python
from fastapi import FastAPI, HTTPException, Depends
from relay import RelayController

app = FastAPI()

_relay = RelayController()


def get_relay() -> RelayController:
    return _relay


@app.get("/api/status")
def get_status(relay: RelayController = Depends(get_relay)):
    return relay.status


@app.post("/api/valve/{valve_id}/open")
def open_valve(valve_id: int, relay: RelayController = Depends(get_relay)):
    if valve_id not in (1, 2):
        raise HTTPException(status_code=422, detail="valve_id must be 1 or 2")
    if not relay.available:
        raise HTTPException(status_code=503, detail="Relay device not found at /dev/irrigation_relay")
    relay.open_valve(valve_id)
    return relay.status


@app.post("/api/valve/{valve_id}/close")
def close_valve(valve_id: int, relay: RelayController = Depends(get_relay)):
    if valve_id not in (1, 2):
        raise HTTPException(status_code=422, detail="valve_id must be 1 or 2")
    if not relay.available:
        raise HTTPException(status_code=503, detail="Relay device not found at /dev/irrigation_relay")
    relay.close_valve(valve_id)
    return relay.status
```

- [ ] **Step 4: Run all backend tests**

```bash
cd backend
pytest tests/ -v
```

Expected: all 17 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_api.py
git commit -m "feat: fastapi endpoints with relay dependency injection"
```

---

## Task 4: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py relay.py ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat: backend dockerfile"
```

---

## Task 5: Frontend Scaffold + Dev Proxy

**Files:**
- Create: `frontend/` (Vite scaffold)
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Scaffold the Vite React project**

Run from the project root (this creates the `frontend/` directory):

```bash
npm create vite@latest frontend -- --template react
```

When prompted, confirm overwriting if asked. Then install deps:

```bash
cd frontend && npm install
```

- [ ] **Step 2: Update vite.config.js to proxy /api to FastAPI**

Replace the contents of `frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Verify the dev server starts**

In one terminal (with `irrigation-env` activated):
```bash
cd backend
uvicorn main:app --reload
```

In another terminal:
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` — the default Vite page should load. Hit `Ctrl+C` to stop both.

- [ ] **Step 4: Commit**

```bash
cd ..  # back to project root
git add frontend/
git commit -m "feat: scaffold vite react frontend with api proxy"
```

---

## Task 6: Frontend — Zone Card UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/main.jsx`

- [ ] **Step 1: Replace frontend/src/App.css with minimal styles**

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: system-ui, sans-serif;
  background: #f3f4f6;
  color: #111827;
}

.app {
  max-width: 600px;
  margin: 48px auto;
  padding: 0 16px;
}

h1 {
  font-size: 1.5rem;
  margin-bottom: 24px;
}

.error-banner {
  background: #fee2e2;
  border: 1px solid #fca5a5;
  color: #991b1b;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 0.9rem;
}

.zones {
  display: flex;
  gap: 16px;
}

.zone-card {
  flex: 1;
  background: white;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.zone-card h2 {
  font-size: 1.05rem;
  font-weight: 600;
}

.badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.badge.open {
  background: #d1fae5;
  color: #065f46;
}

.badge.closed {
  background: #e5e7eb;
  color: #4b5563;
}

button {
  padding: 10px;
  border: none;
  border-radius: 7px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  background: #3b82f6;
  color: white;
  transition: background 0.15s;
  margin-top: auto;
}

button:hover:not(:disabled) {
  background: #2563eb;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 480px) {
  .zones {
    flex-direction: column;
  }
}
```

- [ ] **Step 2: Replace frontend/src/App.jsx with zone card components**

```jsx
import { useState, useEffect } from 'react'
import './App.css'

const ZONES = [
  { id: 1, name: 'Front Yard' },
  { id: 2, name: 'Back Yard' },
]

function ZoneCard({ id, name, state, loading, onToggle }) {
  const isOpen = state === 'open'
  return (
    <div className="zone-card">
      <h2>{name}</h2>
      <span className={`badge ${isOpen ? 'open' : 'closed'}`}>
        {isOpen ? 'Open' : 'Closed'}
      </span>
      <button
        onClick={() => onToggle(id, isOpen ? 'close' : 'open')}
        disabled={loading}
      >
        {loading ? 'Working…' : isOpen ? 'Close Zone' : 'Open Zone'}
      </button>
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState({ valve_1: 'closed', valve_2: 'closed' })
  const [loading, setLoading] = useState({ 1: false, 2: false })
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/status')
      .then((r) => {
        if (!r.ok) throw new Error('Backend unavailable')
        return r.json()
      })
      .then(setStatus)
      .catch(() => setError('Cannot reach backend'))
  }, [])

  async function handleToggle(id, action) {
    setLoading((l) => ({ ...l, [id]: true }))
    try {
      const res = await fetch(`/api/valve/${id}/${action}`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Request failed')
      } else {
        setStatus(data)
        setError(null)
      }
    } catch {
      setError('Cannot reach backend')
    } finally {
      setLoading((l) => ({ ...l, [id]: false }))
    }
  }

  return (
    <div className="app">
      <h1>Irrigation Controller</h1>
      {error && <div className="error-banner">{error}</div>}
      <div className="zones">
        {ZONES.map((zone) => (
          <ZoneCard
            key={zone.id}
            id={zone.id}
            name={zone.name}
            state={status[`valve_${zone.id}`]}
            loading={loading[zone.id]}
            onToggle={handleToggle}
          />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify frontend/src/main.jsx imports App correctly**

Open `frontend/src/main.jsx`. It should already contain this from the Vite scaffold — confirm it looks like this (do not change):

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 4: Test the UI end-to-end**

Start FastAPI (irrigation-env activated):
```bash
cd backend && uvicorn main:app --reload
```

Start Vite dev server:
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Verify:
- Two zone cards appear (Front Yard, Back Yard)
- Both show "Closed" badge
- Without relay hardware, clicking a button shows the error banner with the 503 message
- Button disables while request is in-flight

Stop both servers with `Ctrl+C`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: zone card UI with toggle buttons and error banner"
```

---

## Task 7: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

The frontend Dockerfile is built with the project root as the Docker build context (set in docker-compose.yml in Task 9), so it can reference `nginx/nginx.conf`.

- [ ] **Step 1: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 2: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: multi-stage frontend dockerfile"
```

---

## Task 8: Nginx Config

**Files:**
- Create: `nginx/nginx.conf`

- [ ] **Step 1: Create nginx/nginx.conf**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add nginx/nginx.conf
git commit -m "feat: nginx config for static files and api proxy"
```

---

## Task 9: Docker Compose + End-to-End Smoke Test

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    devices:
      - /dev/irrigation_relay:/dev/irrigation_relay
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

- [ ] **Step 2: Build images locally to verify Dockerfiles are correct**

```bash
docker compose build
```

Expected: both `backend` and `frontend` images build without errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker compose wiring backend and frontend"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push -u origin main
```

- [ ] **Step 5: Deploy to server**

SSH into the server, then:

```bash
mkdir -p /srv/irrigation-controller/app
cd /srv/irrigation-controller/app
git clone https://github.com/calebcoatney/Irrigation-Controller.git .
docker compose up --build -d
```

- [ ] **Step 6: Smoke test on server**

```bash
# Verify containers are running
docker compose ps

# Hit the status endpoint
curl http://localhost/api/status
```

Expected response:
```json
{"valve_1": "closed", "valve_2": "closed"}
```

Open the app in a browser on any Tailscale-connected device: `http://<server-tailscale-ip>`. Verify both zone cards render, and (with relay plugged in) toggle buttons open/close valves.

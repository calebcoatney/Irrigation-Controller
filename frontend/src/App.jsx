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

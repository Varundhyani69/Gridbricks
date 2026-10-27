import { useEffect, useState } from 'react'
import './App.css'

type HealthStatus = 'checking' | 'online' | 'offline'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function App() {
  const [health, setHealth] = useState<HealthStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()

    fetch(`${apiBaseUrl}/api/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`API returned ${response.status}`)
        }
        return response.json() as Promise<{ status: string }>
      })
      .then((result) => {
        setHealth(result.status === 'ok' ? 'online' : 'offline')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setHealth('offline')
      })

    return () => controller.abort()
  }, [])

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Gridbricks home">
          <span className="brand-mark" aria-hidden="true">G</span>
          Gridbricks
        </a>
        <span className="topbar-label">WIND FORECAST ANALYTICS</span>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">UK POWER PROCUREMENT · JANUARY 2026</p>
        <h1 id="page-title">Wind forecast intelligence</h1>
        <p className="intro-copy">
          A decision-time view of national wind forecasts, actual generation, and forecast accuracy.
        </p>
      </section>

      <section className="status-card" aria-live="polite">
        <div>
          <p className="status-label">Analytics service</p>
          <p className="status-description">
            {health === 'checking' && 'Checking the API connection…'}
            {health === 'online' && 'The API is responding and ready for analysis.'}
            {health === 'offline' && 'The API is not reachable. Start the backend to continue.'}
          </p>
        </div>
        <span className={`status-pill status-${health}`}>
          <span className="status-dot" aria-hidden="true" />
          {health}
        </span>
      </section>

      <footer>
        <span>Data scope: Elexon national wind only</span>
        <span>Forecasts are not yet loaded in this scaffold.</span>
      </footer>
    </main>
  )
}

export default App

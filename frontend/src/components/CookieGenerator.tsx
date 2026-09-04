import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'

interface StoredBundleSummary {
  id: number
  bundle_number: number
  checked_at: string
  account_success: boolean
  token_success: boolean
  account: Record<string, any>
}

interface GeneratorState {
  success: boolean
  id: number
  bundle_number: number
  checked_at: string
  account: Record<string, any>
  token: Record<string, any>
  links: Record<string, string>
}

export default function CookieGenerator({ onBack }: { onBack: () => void }) {
  const [items, setItems] = useState<StoredBundleSummary[]>([])
  const [current, setCurrent] = useState<GeneratorState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [usedIds, setUsedIds] = useState<number[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const response = await axios.get('/api/stored-cookies')
        setItems(response.data.items || [])
      } catch {
        setItems([])
      }
    }
    load()
  }, [])

  const remaining = useMemo(
    () => items.filter(item => !usedIds.includes(item.id)),
    [items, usedIds],
  )

  const nextCookie = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await axios.get('/api/stored-cookies/next')
      const next = response.data
      setCurrent(next)
      setUsedIds((prev) => prev.includes(next.id) ? prev : [...prev, next.id])
    } catch (err: any) {
      setCurrent(null)
      setError(err.response?.data?.detail || 'No valid stored cookies are available right now.')
    } finally {
      setLoading(false)
    }
  }

  const moveToNext = async () => {
    if (remaining.length === 0) {
      setCurrent(null)
      setError('No remaining stored cookie bundles. Refresh or re-open admin storage.')
      return
    }
    await nextCookie()
  }

  const accountSummary = current?.account ? current.account : null

  return (
    <main className="admin-page">
      <div className="admin-toolbar">
        <div>
          <span className="eyebrow">Generator</span>
          <h2>Stored Cookie Generator</h2>
          <p>{items.length} stored bundle{items.length === 1 ? '' : 's'} available</p>
        </div>
        <div className="admin-actions">
          <button className="secondary-button" onClick={onBack}>Back to checker</button>
          <button className="secondary-button" onClick={nextCookie} disabled={loading}>Next cookie</button>
        </div>
      </div>

      {error && <p className="admin-error">{error}</p>}

      {!current && !loading && (
        <section className="admin-empty">
          <p>No cookie generator result selected yet.</p>
          <button className="secondary-button" onClick={nextCookie}>Generate from stored cookies</button>
        </section>
      )}

      {current && (
        <section className="stored-card">
          <div className="stored-card-header">
            <div>
              <strong>Stored Bundle #{current.bundle_number}</strong>
              <small>{new Date(current.checked_at).toLocaleString()}</small>
            </div>
            <button className="secondary-button" onClick={moveToNext}>Next cookie</button>
          </div>

          <div className="status-row">
            <span className={current.success ? 'status-ok' : 'status-bad'}>
              {current.success ? 'Working' : 'Not working'}
            </span>
          </div>

          {accountSummary && (
            <div>
              <p><strong>Email:</strong> {String(accountSummary.email || 'Unknown')}</p>
              <p><strong>Plan:</strong> {String(accountSummary.plan || 'Unknown')}</p>
              <p><strong>Country:</strong> {String(accountSummary.country || 'Unknown')}</p>
              <p><strong>Status:</strong> {String(accountSummary.subscription_status || 'Unknown')}</p>
            </div>
          )}

          {current.links && Object.keys(current.links).length > 0 && (
            <div className="status-row" style={{ marginTop: '1rem', flexWrap: 'wrap' }}>
              {Object.entries(current.links).map(([label, url]) => (
                <a key={label} href={url} target="_blank" rel="noreferrer" className="secondary-button">
                  {label === 'tv' ? 'TV Login' : label === 'netflix' ? 'Open in Netflix' : 'Phone Login'}
                </a>
              ))}
            </div>
          )}
        </section>
      )}

      {loading && <p className="admin-empty">Loading the next stored cookie…</p>}
    </main>
  )
}

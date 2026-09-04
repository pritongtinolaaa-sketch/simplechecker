import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import axios from 'axios'

type StoredBundle = {
  id: number
  checked_at: string
  account_success: boolean
  token_success: boolean
  account: Record<string, unknown>
  token: Record<string, unknown>
  cookies: Array<{ name: string; value: string; domain?: string }>
}

export default function AdminCookies({ onBack }: { onBack: () => void }) {
  const [isAdmin, setIsAdmin] = useState(false)
  const [password, setPassword] = useState('')
  const [items, setItems] = useState<StoredBundle[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const loadItems = async () => {
    const response = await axios.get('/api/admin/checked-cookies')
    setItems(response.data.items || [])
  }

  useEffect(() => {
    axios.get('/api/admin/session')
      .then(async ({ data }) => {
        setIsAdmin(data.is_admin)
        if (data.is_admin) await loadItems()
      })
      .catch(() => setError('Unable to verify admin access.'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await axios.post('/api/admin/login', { password })
      setPassword('')
      setIsAdmin(true)
      await loadItems()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed.')
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    await axios.post('/api/admin/logout')
    setIsAdmin(false)
    setItems([])
  }

  const remove = async (id: number) => {
    if (!window.confirm('Delete this stored cookie bundle?')) return
    await axios.delete(`/api/admin/checked-cookies/${id}`)
    setItems(current => current.filter(item => item.id !== id))
  }

  if (loading) return <main className="admin-page"><p>Loading admin storage…</p></main>

  if (!isAdmin) {
    return (
      <main className="admin-page">
        <button className="secondary-button" onClick={onBack}>← Back to checker</button>
        <form className="admin-login" onSubmit={login}>
          <span className="eyebrow">Restricted area</span>
          <h2>Admin cookie storage</h2>
          <p>Enter the admin password to view checked cookie bundles.</p>
          <input
            type="password"
            value={password}
            onChange={event => setPassword(event.target.value)}
            placeholder="Admin password"
            autoComplete="current-password"
            required
          />
          {error && <p className="admin-error">{error}</p>}
          <button type="submit">Sign in</button>
        </form>
      </main>
    )
  }

  return (
    <main className="admin-page">
      <div className="admin-toolbar">
        <div>
          <span className="eyebrow">Admin only</span>
          <h2>Checked cookie storage</h2>
          <p>{items.length} stored bundle{items.length === 1 ? '' : 's'}</p>
        </div>
        <div className="admin-actions">
          <button className="secondary-button" onClick={onBack}>Checker</button>
          <button className="secondary-button" onClick={logout}>Sign out</button>
        </div>
      </div>
      {items.length === 0 ? (
        <section className="admin-empty">No checked cookie bundles have been stored yet.</section>
      ) : (
        <section className="stored-grid">
          {items.map(item => (
            <article className="stored-card" key={item.id}>
              <div className="stored-card-header">
                <div>
                  <strong>Bundle #{item.id}</strong>
                  <small>{new Date(item.checked_at).toLocaleString()}</small>
                </div>
                <button className="danger-button" onClick={() => remove(item.id)}>Delete</button>
              </div>
              <div className="status-row">
                <span className={item.account_success ? 'status-ok' : 'status-bad'}>Account {item.account_success ? 'valid' : 'failed'}</span>
                <span className={item.token_success ? 'status-ok' : 'status-bad'}>Token {item.token_success ? 'valid' : 'failed'}</span>
              </div>
              <p>{String(item.account.email || 'No email')} · {String(item.account.plan || 'Unknown plan')}</p>
              <details>
                <summary>{item.cookies.length} cookies</summary>
                <pre>{JSON.stringify(item.cookies, null, 2)}</pre>
              </details>
            </article>
          ))}
        </section>
      )}
    </main>
  )
}
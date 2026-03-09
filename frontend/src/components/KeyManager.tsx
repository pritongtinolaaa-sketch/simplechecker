import React, { useEffect, useState } from 'react'
import axios from 'axios'

interface KeyItem {
  key: string
  user_name: string
}

interface KeyManagerProps {
  masterKey: string
}

const KeyManager: React.FC<KeyManagerProps> = ({ masterKey }) => {
  const [keys, setKeys] = useState<KeyItem[]>([])
  const [userName, setUserName] = useState('')
  const [customKey, setCustomKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [open, setOpen] = useState(false)

  const loadKeys = async () => {
    try {
      const response = await axios.post('/api/auth/list-keys', { key: masterKey })
      if (response.data.success) {
        setKeys(response.data.keys || [])
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to load keys'
      setError(message)
    }
  }

  useEffect(() => {
    if (open) {
      loadKeys()
    }
  }, [open, masterKey])

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await axios.post('/api/auth/generate-key', {
        master_key: masterKey,
        user_name: userName,
        custom_key: customKey
      })

      if (response.data.success) {
        setSuccess(`Key created for ${response.data.user_name}`)
        setUserName('')
        setCustomKey('')
        await loadKeys()
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to create key'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteKey = async (keyToDelete: string, owner: string) => {
    const confirmed = window.confirm(`Delete key for ${owner}?`)
    if (!confirmed) return

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await axios.post('/api/auth/delete-key', {
        master_key: masterKey,
        key_to_delete: keyToDelete
      })
      setSuccess(`Deleted key for ${owner}`)
      await loadKeys()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to delete key'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="key-manager">
      <div className="key-manager-header">
        <h3>Master Key Management</h3>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setOpen(!open)}
        >
          {open ? 'Hide Key Tools' : 'Manage User Keys'}
        </button>
      </div>

      {open && (
        <div className="key-manager-body">
          <form className="key-manager-form" onSubmit={handleCreateKey}>
            <div className="form-group">
              <label htmlFor="km-user">User Name</label>
              <input
                id="km-user"
                className="key-manager-input"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="e.g., John Doe"
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="km-key">User Key</label>
              <input
                id="km-key"
                className="key-manager-input"
                value={customKey}
                onChange={(e) => setCustomKey(e.target.value)}
                placeholder="e.g., INDAMO"
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !userName.trim() || !customKey.trim()}
            >
              {loading ? 'Saving...' : 'Create Key'}
            </button>
          </form>

          {error && <p className="error-text">{error}</p>}
          {success && <p className="success-text">{success}</p>}

          <div className="key-list-wrap">
            <h4>Existing Keys ({keys.length})</h4>
            {keys.length === 0 && <p>No keys yet.</p>}
            {keys.map((item) => (
              <div className="key-row" key={item.key}>
                <code>{item.key}</code>
                <span>{item.user_name}</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleDeleteKey(item.key, item.user_name)}
                  disabled={loading}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export default KeyManager

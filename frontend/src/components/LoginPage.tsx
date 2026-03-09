import React, { useState } from 'react'
import axios from 'axios'
import './LoginPage.css'

interface LoginPageProps {
  onLoginSuccess: (key: string, isMaster: boolean) => void
}

const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [key, setKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isMasterKey, setIsMasterKey] = useState(false)
  const [generatedKey, setGeneratedKey] = useState<string | null>(null)
  const [userName, setUserName] = useState('')
  const [customKey, setCustomKey] = useState('')
  const [generatedUserName, setGeneratedUserName] = useState<string | null>(null)
  const [showManageKeys, setShowManageKeys] = useState(false)
  const [keysList, setKeysList] = useState<Array<{key: string; user_name: string}>>([])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/auth/login', { key })
      if (response.data.success) {
        const isMaster = response.data.is_master || false
        localStorage.setItem('apiKey', key)
        localStorage.setItem('userName', response.data.user_name || '')
        localStorage.setItem('isMaster', isMaster ? '1' : '0')
        setIsMasterKey(isMaster)
        if (isMaster) {
          fetchKeysList(key)
        }
        onLoginSuccess(key, isMaster)
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Login failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const fetchKeysList = async (masterKey: string) => {
    try {
      const response = await axios.post('/api/auth/list-keys', { key: masterKey })
      if (response.data.success) {
        setKeysList(response.data.keys)
      }
    } catch (err: any) {
      console.error('Failed to load keys list')
    }
  }

  const handleDeleteKey = (keyToDelete: string, userName: string) => {
    if (!window.confirm(`Delete key for "${userName}"?`)) {
      return
    }

    setLoading(true)
    axios.post('/api/auth/delete-key', {
      master_key: key,
      key_to_delete: keyToDelete
    })
      .then(() => {
        setKeysList(keysList.filter(k => k.key !== keyToDelete))
        setLoading(false)
      })
      .catch((err: any) => {
        const errorMessage = err.response?.data?.detail || 'Failed to delete key'
        setError(errorMessage)
        setLoading(false)
      })
  }

  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setGeneratedKey(null)
    setGeneratedUserName(null)

    try {
      const response = await axios.post('/api/auth/generate-key', {
        master_key: key,
        user_name: userName,
        custom_key: customKey
      })
      if (response.data.success) {
        setGeneratedKey(response.data.key)
        setGeneratedUserName(response.data.user_name)
        setCustomKey('')
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Key generation failed'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleCopyKey = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey).then(() => {
        alert('Key copied to clipboard!')
      })
    }
  }

  const handleLoginWithGenerated = async (e: React.FormEvent) => {
    e.preventDefault()
    if (generatedKey) {
      setLoading(true)
      setError('')
      try {
        const response = await axios.post('/api/auth/login', { key: generatedKey })
        if (response.data.success) {
          const isMaster = response.data.is_master || false
          localStorage.setItem('apiKey', generatedKey)
          localStorage.setItem('userName', response.data.user_name || '')
          localStorage.setItem('isMaster', isMaster ? '1' : '0')
          onLoginSuccess(generatedKey, isMaster)
        }
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || err.message || 'Login failed'
        setError(errorMessage)
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-card">
          <h1>🍪 Cookie Checker</h1>
          <p className="subtitle">Authentication Required</p>

          {!generatedKey ? (
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label htmlFor="key">Access Key:</label>
                <input
                  id="key"
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="Enter your access key"
                  disabled={loading}
                  className="key-input"
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <button
                type="submit"
                className="btn btn-login"
                disabled={loading || !key.trim()}
              >
                {loading ? 'Verifying...' : 'Login'}
              </button>

              {isMasterKey && (
                <div className="master-section">
                  <div className="divider">OR</div>
                  
                  <button
                    type="button"
                    onClick={() => setShowManageKeys(!showManageKeys)}
                    className="btn btn-secondary-light"
                  >
                    {showManageKeys ? '▼ Manage Keys' : '▶ Manage Keys'}
                  </button>

                  {showManageKeys && keysList.length > 0 && (
                    <div className="keys-list">
                      <h4>Existing Keys ({keysList.length})</h4>
                      {keysList.map((keyItem) => (
                        <div key={keyItem.key} className="key-item">
                          <div className="key-info">
                            <span className="key-label">Key:</span>
                            <code className="key-value">{keyItem.key}</code>
                            <span className="key-user">User: <strong>{keyItem.user_name}</strong></span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteKey(keyItem.key, keyItem.user_name)}
                            disabled={loading}
                            className="btn btn-delete"
                          >
                            🗑️ Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {showManageKeys && keysList.length === 0 && (
                    <div className="no-keys-message">
                      <p>No keys created yet.</p>
                    </div>
                  )}
                  
                  <div className="generate-form">
                    <p className="generate-note">Create a login key for a user</p>
                    <div className="form-group">
                      <label htmlFor="userName">User Name:</label>
                      <input
                        id="userName"
                        type="text"
                        value={userName}
                        onChange={(e) => setUserName(e.target.value)}
                        placeholder="e.g., John Doe"
                        disabled={loading}
                        className="key-input"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="customKey">Login Key:</label>
                      <input
                        id="customKey"
                        type="text"
                        value={customKey}
                        onChange={(e) => setCustomKey(e.target.value)}
                        placeholder="e.g., INDAMO"
                        disabled={loading}
                        className="key-input"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleGenerateKey}
                      disabled={loading || !userName.trim() || !customKey.trim()}
                      className="btn btn-primary"
                    >
                      {loading ? 'Creating...' : 'Create Key'}
                    </button>
                  </div>
                </div>
              )}
            </form>
          ) : (
            <div className="generated-key-section">
              <div className="success-message">
                ✓ Key generated for <strong>{generatedUserName}</strong>!
              </div>
              
              <div className="key-display">
                <textarea
                  value={generatedKey}
                  readOnly
                  className="generated-key-value"
                  rows={3}
                />
              </div>

              <button
                className="btn btn-primary"
                onClick={handleCopyKey}
              >
                📋 Copy Key
              </button>

              <button
                className="btn btn-secondary"
                onClick={handleLoginWithGenerated}
                disabled={loading}
              >
                Login with this Key
              </button>

              <button
                className="btn btn-outline"
                onClick={() => {
                  setGeneratedKey(null)
                  setGeneratedUserName(null)
                  setError('')
                }}
                disabled={loading}
              >
                Create Another Key
              </button>

              <div className="key-note">
                <p>Share this key "<strong>{generatedKey}</strong>" with the user "<strong>{generatedUserName}</strong>". They will use this key to login and see their name.</p>
              </div>
            </div>
          )}

          <div className="login-info">
            <p><strong>Note:</strong> Use the master key to create custom keys for other users, or use your assigned key to login.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage

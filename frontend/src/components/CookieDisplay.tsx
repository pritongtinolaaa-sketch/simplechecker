import React from 'react'

interface Cookie {
  name: string
  value: string
  domain?: string
  path?: string
  expires?: string
  secure?: boolean
  httponly?: boolean
  samesite?: string
}

interface CookieDisplayProps {
  cookies: Cookie[]
  loading: boolean
  error: string
  parseErrors: string[]
  cookieCount: number
  onDownload: () => void
  onCopy: () => void
}

const CookieDisplay: React.FC<CookieDisplayProps> = ({
  cookies,
  loading,
  error,
  parseErrors,
  cookieCount,
  onDownload,
  onCopy
}) => {
  if (loading) {
    return (
      <div className="cookie-display loading">
        <p>Analyzing cookies...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="cookie-display error">
        <h2>Error</h2>
        <p className="error-message">{error}</p>
      </div>
    )
  }

  if (cookies.length === 0) {
    return (
      <div className="cookie-display empty">
        <h2>Results</h2>
        <p>No cookies parsed yet. Paste your cookies above and click "Check Cookies".</p>
      </div>
    )
  }

  return (
    <div className="cookie-display">
      <div className="display-header">
        <h2>Parsed Cookies</h2>
        <div className="cookie-count">
          <span className="count-badge">{cookieCount}</span> cookies found
        </div>
      </div>

      {parseErrors && parseErrors.length > 0 && (
        <div className="alerts">
          <div className="alert alert-warning">
            <strong>Warnings:</strong>
            <ul>
              {parseErrors.map((err, idx) => (
                <li key={idx}>{err}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="cookies-table-container">
        <table className="cookies-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Value</th>
              <th>Domain</th>
              <th>Path</th>
              <th>Secure</th>
              <th>HttpOnly</th>
            </tr>
          </thead>
          <tbody>
            {cookies.map((cookie, idx) => (
              <tr key={idx} className="cookie-row">
                <td className="cookie-name">
                  <code>{cookie.name}</code>
                </td>
                <td className="cookie-value">
                  <code className="truncate">{cookie.value}</code>
                </td>
                <td className="cookie-domain">{cookie.domain || '-'}</td>
                <td className="cookie-path">{cookie.path || '/'}</td>
                <td className="cookie-secure">
                  <span className={`badge ${cookie.secure ? 'badge-success' : 'badge-default'}`}>
                    {cookie.secure ? '✓' : '✗'}
                  </span>
                </td>
                <td className="cookie-httponly">
                  <span className={`badge ${cookie.httponly ? 'badge-success' : 'badge-default'}`}>
                    {cookie.httponly ? '✓' : '✗'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="display-actions">
        <button className="btn btn-primary" onClick={onCopy}>
          📋 Copy as JSON
        </button>
        <button className="btn btn-primary" onClick={onDownload}>
          ⬇️ Download JSON
        </button>
      </div>

      <div className="json-preview">
        <details>
          <summary>View Raw JSON</summary>
          <pre>
            <code>{JSON.stringify(cookies, null, 2)}</code>
          </pre>
        </details>
      </div>
    </div>
  )
}

export default CookieDisplay

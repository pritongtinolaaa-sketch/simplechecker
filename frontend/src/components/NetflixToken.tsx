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

interface NetflixTokenProps {
  token: string
  cookies: Cookie[]
  error?: string
}

const NetflixToken: React.FC<NetflixTokenProps> = ({ token, cookies, error }) => {
  const handleCopyToken = () => {
    navigator.clipboard.writeText(token).then(() => {
      alert('Netflix token copied to clipboard!')
    })
  }

  const handleDownloadToken = () => {
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(token))
    element.setAttribute('download', 'netflix-token.txt')
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  if (error) {
    return (
      <div className="netflix-token error">
        <h2>🎬 Netflix Token Generation</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  return (
    <div className="netflix-token">
      <h2>🎬 Netflix Token Generated</h2>
      
      <div className="token-section">
        <div className="token-header">
          <h3>Auto-Login Token</h3>
          <span className="badge badge-success">✓ Valid</span>
        </div>
        
        <div className="token-display">
          <div className="token-value-container">
            <textarea 
              className="token-value"
              value={token}
              readOnly
              rows={6}
            />
          </div>
        </div>

        <div className="token-actions">
          <button className="btn btn-primary" onClick={handleCopyToken}>
            📋 Copy Token
          </button>
          <button className="btn btn-primary" onClick={handleDownloadToken}>
            ⬇️ Download Token
          </button>
        </div>

        <div className="token-info">
          <p><strong>Token Type:</strong> Netflix Auto-Login Token (NFTOKEN)</p>
          <p><strong>Use Case:</strong> Mobile and TV app authentication</p>
          <p><strong>Format:</strong> GraphQL Response</p>
        </div>
      </div>

      {cookies.length > 0 && (
        <details className="cookies-summary">
          <summary>View Parsed Cookies ({cookies.length})</summary>
          <table className="cookies-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Value Preview</th>
              </tr>
            </thead>
            <tbody>
              {cookies.map((cookie, idx) => (
                <tr key={idx}>
                  <td className="cookie-name"><code>{cookie.name}</code></td>
                  <td className="cookie-value"><code>{cookie.value.substring(0, 50)}...</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}

export default NetflixToken

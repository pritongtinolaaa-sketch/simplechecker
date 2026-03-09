import React from 'react'

interface NetflixTokenProps {
  token: string
  error?: string
}

const NetflixToken: React.FC<NetflixTokenProps> = ({ token, error }) => {
  const tokenUrl = `https://www.netflix.com/?nftoken=${encodeURIComponent(token)}`

  const handleCopyLink = () => {
    navigator.clipboard.writeText(tokenUrl).then(() => {
      alert('Netflix token link copied to clipboard!')
    })
  }

  if (error) {
    return (
      <div className="netflix-token error">
        <h2>🎬 Netflix Token</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  if (!token) {
    return null
  }

  return (
    <div className="netflix-token">
      <h2>🎬 Netflix Token Link</h2>
      
      <div className="token-section">
        <div className="token-header">
          <h3>Auto-Login Link</h3>
          <span className="badge badge-success">✓ Ready</span>
        </div>
        
        <div className="token-link-container">
          <a 
            href={tokenUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="token-link"
          >
            {tokenUrl}
          </a>
        </div>

        <div className="token-actions">
          <button className="btn btn-primary" onClick={handleCopyLink}>
            📋 Copy Link
          </button>
          <a 
            href={tokenUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            🚀 Open in Netflix
          </a>
        </div>

        <div className="token-info">
          <p><strong>Usage:</strong> Click the link above to automatically log in to Netflix with this account.</p>
          <p><strong>Note:</strong> The token link works on mobile devices and web browsers.</p>
        </div>
      </div>
    </div>
  )
}

export default NetflixToken

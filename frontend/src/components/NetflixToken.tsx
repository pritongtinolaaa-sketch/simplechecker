import React from 'react'

interface NetflixTokenProps {
  token?: string
  error?: string
  tokens?: TokenResult[]
}

interface TokenResult {
  bundle_number: number
  success: boolean
  nftoken?: string
  error?: string
}

const NetflixToken: React.FC<NetflixTokenProps> = ({ token, error, tokens }) => {
  const results = tokens?.length
    ? tokens
    : token
      ? [{ bundle_number: 1, success: true, nftoken: token }]
      : []
  const successfulTokens = results.filter(
    (result): result is TokenResult & { nftoken: string } =>
      result.success && Boolean(result.nftoken)
  )
  const failedCount = results.length - successfulTokens.length

  const handleCopyLink = (tokenUrl: string) => {
    navigator.clipboard.writeText(tokenUrl).then(() => {
      alert('Netflix token link copied to clipboard!')
    })
  }

  if (error && successfulTokens.length === 0) {
    return (
      <div className="netflix-token error">
        <h2>🎬 Netflix Token</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  if (successfulTokens.length === 0) {
    return null
  }

  return (
    <div className="netflix-token">
      <h2>🎬 Netflix Token Links ({successfulTokens.length})</h2>

      {successfulTokens.map((result) => {
        const tokenUrl = `https://netflix.com/?nftoken=${encodeURIComponent(result.nftoken)}`
        const phoneTokenUrl = `https://www.netflix.com/unsupported?nftoken=${encodeURIComponent(result.nftoken)}`

        return (
          <div className="token-section" key={result.bundle_number}>
            <div className="token-header">
              <h3>Cookie Bundle #{result.bundle_number}</h3>
              <span className="badge badge-success">✓ Live</span>
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
              <button className="btn btn-primary" onClick={() => handleCopyLink(tokenUrl)}>
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
              <a
                href={phoneTokenUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primary"
              >
                📱 Open in Phone
              </a>
            </div>

            <div className="token-info">
              <p><strong>Usage:</strong> This link was generated from cookie bundle #{result.bundle_number}.</p>
              <p><strong>Note:</strong> The token link works on mobile devices and web browsers.</p>
            </div>
          </div>
        )
      })}

      {failedCount > 0 && (
        <div className="alert alert-warning">
          <strong>{failedCount} bundle{failedCount === 1 ? '' : 's'}</strong> did not produce a usable token.
        </div>
      )}
    </div>
  )
}

export default NetflixToken

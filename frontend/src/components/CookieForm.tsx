import React, { useState } from 'react'

interface CookieFormProps {
  onSubmit: (cookiesText: string, formatType: string) => void
  onGenerateToken?: (cookiesText: string, formatType: string, usePlaywright: boolean) => void
  loading: boolean
  tokenLoading?: boolean
}

const CookieForm: React.FC<CookieFormProps> = ({ onSubmit, onGenerateToken, loading, tokenLoading = false }) => {
  const [cookiesText, setCookiesText] = useState('')
  const [formatType, setFormatType] = useState('auto')
  const [usePlaywright, setUsePlaywright] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim()) {
      onSubmit(cookiesText, formatType)
    }
  }

  const handleGenerateToken = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim() && onGenerateToken) {
      onGenerateToken(cookiesText, formatType, usePlaywright)
    }
  }

  const handleClear = () => {
    setCookiesText('')
  }

  return (
    <form className="cookie-form" onSubmit={handleSubmit}>
      <h2>Input Cookies</h2>
      
      <div className="form-group">
        <label htmlFor="format">Format Type:</label>
        <select 
          id="format"
          value={formatType} 
          onChange={(e) => setFormatType(e.target.value)}
          disabled={loading || tokenLoading}
        >
          <option value="auto">Auto Detect</option>
          <option value="netscape">Netscape (Browser Dev Tools)</option>
          <option value="json">JSON Array</option>
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="cookies">Paste Cookies:</label>
        <textarea
          id="cookies"
          className="cookies-textarea"
          value={cookiesText}
          onChange={(e) => setCookiesText(e.target.value)}
          placeholder="Paste your cookies here (Netscape format or JSON)..."
          disabled={loading || tokenLoading}
          rows={12}
        />
      </div>

      <div className="form-group checkbox-group">
        <input 
          type="checkbox"
          id="use-playwright"
          checked={usePlaywright}
          onChange={(e) => setUsePlaywright(e.target.checked)}
          disabled={loading || tokenLoading}
        />
        <label htmlFor="use-playwright">Use Playwright to get full cookie header (Netflix)</label>
      </div>

      <div className="form-actions">
        <button 
          type="submit" 
          className="btn btn-primary"
          disabled={loading || tokenLoading || !cookiesText.trim()}
        >
          {loading ? 'Analyzing...' : 'Check Cookies'}
        </button>
        <button 
          type="button"
          onClick={handleGenerateToken}
          className="btn btn-primary btn-netflix"
          disabled={tokenLoading || loading || !cookiesText.trim()}
        >
          {tokenLoading ? 'Generating...' : '🎬 Netflix Token'}
        </button>
        <button 
          type="button" 
          className="btn btn-secondary"
          onClick={handleClear}
          disabled={loading || tokenLoading}
        >
          Clear
        </button>
      </div>

      <div className="format-info">
        <p><strong>Format Info:</strong></p>
        <ul>
          <li><strong>Netscape:</strong> Tab-separated format from browser export</li>
          <li><strong>JSON:</strong> Array of objects with name/value properties</li>
          <li><strong>Auto:</strong> Automatically detect the format</li>
        </ul>
      </div>
    </form>
  )
}

export default CookieForm

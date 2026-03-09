import React, { useState } from 'react'

interface CookieFormProps {
  onSubmit: (cookiesText: string, formatType: string) => void
  loading: boolean
}

const CookieForm: React.FC<CookieFormProps> = ({ 
  onSubmit,
  loading
}) => {
  const [cookiesText, setCookiesText] = useState('')
  const [formatType, setFormatType] = useState('auto')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim()) {
      onSubmit(cookiesText, formatType)
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
          disabled={loading}
        >
          <option value="auto">Auto Detect</option>
          <option value="netscape">Netscape (Browser Dev Tools)</option>
          <option value="json">JSON Array</option>
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="cookies">Paste Netflix Cookies:</label>
        <textarea
          id="cookies"
          className="cookies-textarea"
          value={cookiesText}
          onChange={(e) => setCookiesText(e.target.value)}
          placeholder="Paste your Netflix cookies here (Netscape format or JSON)..."
          disabled={loading}
          rows={12}
        />
      </div>

      <div className="form-actions">
        <button 
          type="submit"
          className="btn btn-primary"
          disabled={loading || !cookiesText.trim()}
        >
          {loading ? 'Processing...' : '🎬 Get Netflix Info'}
        </button>
        <button 
          type="button" 
          className="btn btn-secondary"
          onClick={handleClear}
          disabled={loading}
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

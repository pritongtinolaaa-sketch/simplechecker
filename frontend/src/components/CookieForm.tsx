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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim()) {
      onSubmit(cookiesText, 'auto')
    }
  }

  const handleClear = () => {
    setCookiesText('')
  }

  return (
    <form className="cookie-form" onSubmit={handleSubmit}>
      <h2>Input Cookies</h2>
      
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

    </form>
  )
}

export default CookieForm

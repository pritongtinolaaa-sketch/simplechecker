import React, { useRef, useState } from 'react'
import Icon from './Icon'

interface CookieFormProps {
  onSubmit: (cookiesText: string, formatType: string) => void
  loading: boolean
  progress?: {
    status: string
    totalBundles: number
    completedBundles: number
    totalCookies: number
    completedCookies: number
  }
}

const CookieForm: React.FC<CookieFormProps> = ({ 
  onSubmit,
  loading,
  progress
}) => {
  const [cookiesText, setCookiesText] = useState('')
  const [selectedFileName, setSelectedFileName] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim()) {
      onSubmit(cookiesText, 'auto')
    }
  }

  const handleClear = () => {
    setCookiesText('')
    setSelectedFileName('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const fileText = await file.text()
    setCookiesText(fileText)
    setSelectedFileName(file.name)
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
          onChange={(e) => {
            setCookiesText(e.target.value)
            setSelectedFileName('')
          }}
          placeholder="Paste Netflix cookies, JSON, or a Netflix Account Details export..."
          disabled={loading}
          rows={12}
        />
        <div className="file-upload-row">
          <label className="btn btn-secondary file-upload-button">
            <Icon name="upload" /> Upload .txt File
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,text/plain"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
          {selectedFileName && (
            <span className="file-upload-name" title={selectedFileName}>
              {selectedFileName}
            </span>
          )}
        </div>
      </div>

      <div className="form-actions">
        <button 
          type="submit"
          className="btn btn-primary"
          disabled={loading || !cookiesText.trim()}
        >
          {loading ? 'Processing...' : <><Icon name="film" /> Get Netflix Info</>}
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

      {loading && progress && progress.totalBundles > 0 && (
        <div className="check-progress">
          <div className="check-progress-header">
            <strong>
              {progress.completedBundles < progress.totalBundles
                ? `Checking cookie bundle ${progress.completedBundles + 1} of ${progress.totalBundles}`
                : 'Finishing cookie bundle check'}
            </strong>
            <span>{Math.round((progress.completedBundles / progress.totalBundles) * 100)}%</span>
          </div>
          <div
            className="check-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.totalBundles}
            aria-valuenow={progress.completedBundles}
            aria-label="Cookie bundle checking progress"
          >
            <div
              className="check-progress-fill"
              style={{ width: `${(progress.completedBundles / progress.totalBundles) * 100}%` }}
            />
          </div>
          <div className="check-progress-details">
            <span>
              {progress.completedBundles.toLocaleString()} of {progress.totalBundles.toLocaleString()} bundles checked
            </span>
            <span>
              {progress.completedCookies.toLocaleString()} of {progress.totalCookies.toLocaleString()} cookies checked
            </span>
          </div>
        </div>
      )}

    </form>
  )
}

export default CookieForm

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
  const [selectedFileNames, setSelectedFileNames] = useState<string[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (cookiesText.trim()) {
      onSubmit(cookiesText, 'auto')
    }
  }

  const handleClear = () => {
    setCookiesText('')
    setSelectedFileNames([])
    setIsDragging(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const processFiles = async (files: File[]) => {
    const textFiles = files.filter((file) =>
      file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')
    )
    if (!textFiles.length) return

    const fileTexts = await Promise.all(textFiles.map((file) => file.text()))
    setCookiesText(fileTexts.join('\n\n'))
    setSelectedFileNames(textFiles.map((file) => file.name))
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    await processFiles(Array.from(e.target.files || []))
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setIsDragging(false)
    }
  }

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    await processFiles(Array.from(e.dataTransfer.files))
  }

  return (
    <form className="cookie-form" onSubmit={handleSubmit}>
      <h2>Input Cookies</h2>
      
      <div className="form-group">
        <div className="input-label-row">
          <label htmlFor="cookies">Paste Netflix Cookies:</label>
          <div
            className={`file-upload-row${isDragging ? ' is-dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <label className="btn btn-secondary file-upload-button">
              <Icon name="upload" /> Upload .txt Files
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,text/plain"
                multiple
                onChange={handleFileUpload}
                disabled={loading}
              />
            </label>
            <span className="file-drop-hint">or drop files here</span>
            {selectedFileNames.length > 0 && (
              <span className="file-upload-name" title={selectedFileNames.join(', ')}>
                {selectedFileNames.join(', ')}
              </span>
            )}
          </div>
        </div>
        <textarea
          id="cookies"
          className="cookies-textarea"
          value={cookiesText}
          onChange={(e) => {
            setCookiesText(e.target.value)
            setSelectedFileNames([])
          }}
          placeholder="Paste Netflix cookies, JSON, or a Netflix Account Details export..."
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

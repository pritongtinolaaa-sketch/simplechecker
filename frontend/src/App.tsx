import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css'
import CookieForm from './components/CookieForm'
import CookieDisplay from './components/CookieDisplay'
import NetflixToken from './components/NetflixToken'
import Header from './components/Header'
import LoginPage from './components/LoginPage'

// Configure axios to include API key in all requests
const configureAxios = (apiKey: string) => {
  axios.defaults.headers.common['X-API-Key'] = apiKey
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [userName, setUserName] = useState<string | null>(null)
  const [cookies, setCookies] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [cookieCount, setCookieCount] = useState(0)
  const [netflixToken, setNetflixToken] = useState<string | null>(null)
  const [tokenLoading, setTokenLoading] = useState(false)
  const [tokenError, setTokenError] = useState('')

  // Check if user is already logged in
  useEffect(() => {
    const savedKey = localStorage.getItem('apiKey')
    const savedUserName = localStorage.getItem('userName')
    if (savedKey) {
      setApiKey(savedKey)
      setUserName(savedUserName)
      configureAxios(savedKey)
      setIsAuthenticated(true)
    }
  }, [])

  const handleLoginSuccess = (key: string) => {
    const savedUserName = localStorage.getItem('userName')
    setApiKey(key)
    setUserName(savedUserName)
    configureAxios(key)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
    setApiKey(null)
    setUserName(null)
    localStorage.removeItem('apiKey')
    localStorage.removeItem('userName')
    delete axios.defaults.headers.common['X-API-Key']
    setCookies([])
    setNetflixToken(null)
    setError('')
  }

  const handleCheckCookies = async (cookiesText: string, formatType: string) => {
    setLoading(true)
    setError('')
    setParseErrors([])
    
    try {
      const response = await axios.post('/api/check-cookies', {
        cookies_text: cookiesText,
        format_type: formatType
      })
      
      setCookies(response.data.cookies || [])
      setCookieCount(response.data.count || 0)
      setParseErrors(response.data.errors || [])
      
      if (response.data.success) {
        console.log(`Successfully parsed ${response.data.count} cookies`)
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to parse cookies'
      setError(errorMessage)
      setCookies([])
      setCookieCount(0)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateNetflixToken = async (cookiesText: string, formatType: string, usePlaywright: boolean) => {
    setTokenLoading(true)
    setTokenError('')
    setNetflixToken(null)
    
    try {
      const response = await axios.post('/api/generate-netflix-token', {
        cookies_text: cookiesText,
        format_type: formatType,
        use_playwright: usePlaywright
      })
      
      if (response.data.success && response.data.nftoken) {
        setNetflixToken(response.data.nftoken)
        setCookies(response.data.cookies || [])
        setCookieCount(response.data.cookie_count || 0)
      } else {
        setTokenError(response.data.error || 'Failed to generate Netflix token')
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to generate Netflix token'
      setTokenError(errorMessage)
    } finally {
      setTokenLoading(false)
    }
  }

  const handleDownloadCookies = () => {
    if (cookies.length === 0) return
    
    const jsonStr = JSON.stringify(cookies, null, 2)
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(jsonStr))
    element.setAttribute('download', 'cookies.json')
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const handleCopyCookies = () => {
    if (cookies.length === 0) return
    
    const jsonStr = JSON.stringify(cookies, null, 2)
    navigator.clipboard.writeText(jsonStr).then(() => {
      alert('Cookies copied to clipboard!')
    })
  }

  return (
    <div className="app">
      {!isAuthenticated ? (
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      ) : (
        <>
          <Header onLogout={handleLogout} userName={userName || undefined} />
          <main className="app-container">
            <div className="app-grid">
              <div className="app-section">
                <CookieForm 
                  onSubmit={handleCheckCookies} 
                  onGenerateToken={handleGenerateNetflixToken}
                  loading={loading}
                  tokenLoading={tokenLoading}
                />
              </div>
              
              <div className="app-section">
                {netflixToken ? (
                  <NetflixToken 
                    token={netflixToken}
                    cookies={cookies}
                    error={tokenError}
                  />
                ) : (
                  <CookieDisplay 
                    cookies={cookies} 
                    loading={loading} 
                    error={error}
                    parseErrors={parseErrors}
                    cookieCount={cookieCount}
                    onDownload={handleDownloadCookies}
                    onCopy={handleCopyCookies}
                  />
                )}
              </div>
            </div>
          </main>
        </>
      )}
    </div>
  )
}

export default App

import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css'
import CookieForm from './components/CookieForm'
import CookiesList from './components/CookiesList'
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
  const [loading, setLoading] = useState(false)
  const [cookies, setCookies] = useState([])
  const [netflixToken, setNetflixToken] = useState<string | null>(null)
  const [tokenError, setTokenError] = useState('')
  const [accountInfo, setAccountInfo] = useState<any>(null)
  const [accountInfoError, setAccountInfoError] = useState('')

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
    setAccountInfo(null)
    setNetflixToken(null)
    setCookies([])
    setAccountInfoError('')
    setTokenError('')
    setLoading(false)
  }

  const handleGetNetflixInfo = async (cookiesText: string, formatType: string) => {
    setLoading(true)
    setAccountInfoError('')
    setTokenError('')
    setAccountInfo(null)
    setNetflixToken(null)
    setCookies([])
    
    try {
      // Fetch both account info and Netflix token in parallel
      // Always use playwright for getting Netflix token
      const [accountResponse, tokenResponse] = await Promise.all([
        axios.post('/api/get-account-info', {
          cookies_text: cookiesText,
          format_type: formatType
        }),
        axios.post('/api/generate-netflix-token', {
          cookies_text: cookiesText,
          format_type: formatType,
          use_playwright: true
        })
      ])
      
      // Handle account info response
      if (accountResponse.data.success) {
        setAccountInfo(accountResponse.data)
      } else {
        setAccountInfoError(accountResponse.data.error || 'Failed to extract account information')
      }
      
      // Handle token response and extract cookies
      if (tokenResponse.data.success && tokenResponse.data.nftoken) {
        setNetflixToken(tokenResponse.data.nftoken)
      } else {
        setTokenError(tokenResponse.data.error || 'Failed to generate Netflix token')
      }
      
      // Store parsed cookies
      if (tokenResponse.data.cookies && Array.isArray(tokenResponse.data.cookies)) {
        setCookies(tokenResponse.data.cookies)
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to process request'
      setAccountInfoError(errorMessage)
      setTokenError(errorMessage)
    } finally {
      setLoading(false)
    }
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
                  onSubmit={handleGetNetflixInfo}
                  loading={loading}
                />
              </div>
              
              <div className="app-section">
                <AccountInfo 
                  email={accountInfo?.email}
                  country={accountInfo?.country}
                  plan={accountInfo?.plan}
                  subscriptionStatus={accountInfo?.subscription_status}
                  billingDate={accountInfo?.billing_date}
                  accountCreatedDate={accountInfo?.account_created_date}
                  paymentMethod={accountInfo?.payment_method}
                  streamingQuality={accountInfo?.streaming_quality}
                  profiles={accountInfo?.profiles}
                  error={accountInfoError}
                  loading={loading}
                />
                
                {netflixToken && (
                  <NetflixToken 
                    token={netflixToken}
                    error={tokenError}
                  />
                )}
                
                <CookiesList 
                  cookies={cookies}
                  accountInfo={accountInfo}
                  loading={loading}
                />
              </div>
            </div>
          </main>
        </>
      )}
    </div>
  )
}

export default App

import { useState } from 'react'
import axios from 'axios'
import './App.css'
import CookieForm from './components/CookieForm'
import CookiesList from './components/CookiesList'
import NetflixToken from './components/NetflixToken'
import Header from './components/Header'
import AccountInfo from './components/AccountInfo'

function App() {
  const [loading, setLoading] = useState(false)
  const [cookies, setCookies] = useState([])
  const [tokenResults, setTokenResults] = useState<any[]>([])
  const [tokenError, setTokenError] = useState('')
  const [accountInfo, setAccountInfo] = useState<any>(null)
  const [accountInfoError, setAccountInfoError] = useState('')

  const handleGetNetflixInfo = async (cookiesText: string, formatType: string) => {
    setLoading(true)
    setAccountInfoError('')
    setTokenError('')
    setAccountInfo(null)
    setTokenResults([])
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
      if (accountResponse.data.accounts?.length) {
        setAccountInfo(accountResponse.data)
        if (!accountResponse.data.success) {
          setAccountInfoError(accountResponse.data.error || 'Failed to extract account information')
        }
      } else if (accountResponse.data.success) {
        setAccountInfo(accountResponse.data)
      } else {
        setAccountInfoError(accountResponse.data.error || 'Failed to extract account information')
      }
      
      // Handle token response and extract cookies
      if (tokenResponse.data.tokens?.length) {
        setTokenResults(tokenResponse.data.tokens)
        if (!tokenResponse.data.success) {
          setTokenError(tokenResponse.data.error || 'Failed to generate Netflix token')
        }
      } else if (tokenResponse.data.success && tokenResponse.data.nftoken) {
        setTokenResults([{
          bundle_number: 1,
          success: true,
          nftoken: tokenResponse.data.nftoken
        }])
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
      <Header />
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
              accounts={accountInfo?.accounts}
              accountCount={accountInfo?.account_count}
              bundleCount={accountInfo?.bundle_count}
              checkedCookieCount={accountInfo?.checked_cookie_count}
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

            {tokenResults.length > 0 && (
              <NetflixToken
                tokens={tokenResults}
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
    </div>
  )
}

export default App

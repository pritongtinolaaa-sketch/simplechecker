import { useState } from 'react'
import axios from 'axios'
import './App.css'
import CookieForm from './components/CookieForm'
import CookiesList from './components/CookiesList'
import Header from './components/Header'
import AccountInfo from './components/AccountInfo'
import AdminCookies from './components/AdminCookies'

interface CheckProgress {
  status: string
  totalBundles: number
  completedBundles: number
  totalCookies: number
  completedCookies: number
}

function App() {
  const [page, setPage] = useState(window.location.pathname === '/admin/cookies' ? 'admin' : 'checker')
  const [loading, setLoading] = useState(false)
  const [cookies, setCookies] = useState([])
  const [cookieBundles, setCookieBundles] = useState<any[]>([])
  const [tokenResults, setTokenResults] = useState<any[]>([])
  const [accountInfo, setAccountInfo] = useState<any>(null)
  const [accountInfoError, setAccountInfoError] = useState('')
  const [progress, setProgress] = useState<CheckProgress>({
    status: '',
    totalBundles: 0,
    completedBundles: 0,
    totalCookies: 0,
    completedCookies: 0
  })

  const handleGetNetflixInfo = async (cookiesText: string, formatType: string) => {
    setLoading(true)
    setAccountInfoError('')
    setAccountInfo(null)
    setTokenResults([])
    setCookieBundles([])
    setCookies([])
    setProgress({
      status: 'starting',
      totalBundles: 0,
      completedBundles: 0,
      totalCookies: 0,
      completedCookies: 0
    })
    
    try {
      const startResponse = await axios.post('/api/check-bundles/start', {
          cookies_text: cookiesText,
          format_type: formatType,
      })
      const { job_id: jobId, total_bundles: totalBundles, total_cookies: totalCookies } = startResponse.data
      setProgress({
        status: 'queued',
        totalBundles,
        completedBundles: 0,
        totalCookies,
        completedCookies: 0
      })

      const applyCheckStatus = (data: any) => {
        const bundles = Array.isArray(data.cookie_bundles) ? data.cookie_bundles : []
        const accounts = Array.isArray(data.accounts) ? data.accounts : []
        const tokens = Array.isArray(data.tokens) ? data.tokens : []

        setProgress({
          status: data.status,
          totalBundles: data.total_bundles || totalBundles,
          completedBundles: data.completed_bundles || 0,
          totalCookies: data.total_cookies || totalCookies,
          completedCookies: data.completed_cookies || 0
        })
        setAccountInfo({
          success: data.success,
          accounts,
          account_count: data.total_bundles || totalBundles,
          bundle_count: data.total_bundles || totalBundles,
          checked_cookie_count: data.total_cookies || totalCookies
        })
        setTokenResults(tokens)
        setCookieBundles(bundles)
        setCookies(bundles.flatMap((bundle: any) => bundle.cookies || []))
        if (data.status === 'failed') {
          setAccountInfoError(data.error || 'Failed to process cookie bundles')
        } else {
          setAccountInfoError('')
        }
      }

      let statusData
      do {
        await new Promise(resolve => setTimeout(resolve, 700))
        const statusResponse = await axios.get(`/api/check-bundles/${jobId}`)
        statusData = statusResponse.data
        applyCheckStatus(statusData)
      } while (statusData.status !== 'completed' && statusData.status !== 'failed')

      if (statusData.status === 'failed') {
        setAccountInfoError(statusData.error || 'Failed to process cookie bundles')
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to process request'
      setAccountInfoError(errorMessage)
      setProgress(prev => ({ ...prev, status: 'failed' }))
    } finally {
      setLoading(false)
    }
  }



  return (
    <div className="app">
      <Header />
      <nav className="top-nav">
        <button onClick={() => { window.history.pushState({}, '', '/'); setPage('checker') }}>Checker</button>
        <button onClick={() => { window.history.pushState({}, '', '/admin/cookies'); setPage('admin') }}>Admin storage</button>
      </nav>
      {page === 'admin' ? (
        <AdminCookies onBack={() => { window.history.pushState({}, '', '/'); setPage('checker') }} />
      ) : (
      <main className="app-container">
        <div className="app-grid">
          <div className="app-section">
            <CookieForm
              onSubmit={handleGetNetflixInfo}
              loading={loading}
              progress={progress}
            />
          </div>

          <div className="app-section">
            <AccountInfo
              accounts={accountInfo?.accounts}
              tokenResults={tokenResults}
              cookieBundles={cookieBundles}
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

            <CookiesList
              cookies={cookies}
              cookieBundles={cookieBundles}
              accounts={accountInfo?.accounts}
              tokenResults={tokenResults}
              loading={loading}
            />
          </div>
        </div>
      </main>
      )}
      <footer className="footer">© Schiro 2026</footer>
    </div>
  )
}

export default App

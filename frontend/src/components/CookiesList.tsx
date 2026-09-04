import React, { useEffect, useState } from 'react'
import axios from 'axios'
import Icon from './Icon'

interface Cookie {
  name: string
  value: string
  domain?: string
  path?: string
  expires?: string
  secure?: boolean
  httponly?: boolean
  samesite?: string
}

interface CookieBundle {
  bundle_number: number
  cookies: Cookie[]
}

interface AccountResult {
  bundle_number: number
  cookie_count: number
  success: boolean
  email?: string
  country?: string
  plan?: string
  subscription_status?: string
  billing_date?: string
  account_created_date?: string
  payment_method?: string
  streaming_quality?: string
  profiles?: Array<{ name: string; isKids?: boolean }>
  error?: string
}

interface TokenResult {
  bundle_number: number
  success: boolean
  nftoken?: string
  error?: string
}

interface CookiesListProps {
  cookies: Cookie[]
  cookieBundles?: CookieBundle[]
  accounts?: AccountResult[]
  tokenResults?: TokenResult[]
  loading: boolean
}

const CookiesList: React.FC<CookiesListProps> = ({
  cookies,
  cookieBundles = [],
  accounts = [],
  tokenResults = [],
  loading
}) => {
  const [copiedBundleNumber, setCopiedBundleNumber] = useState<number | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [savingBundleNumber, setSavingBundleNumber] = useState<number | null>(null)
  const [savedBundleNumbers, setSavedBundleNumbers] = useState<number[]>([])
  const validCookies = cookies.filter(cookie => cookie.name && cookie.value)
  const accountByBundle = new Map(accounts.map(account => [account.bundle_number, account]))
  const tokenByBundle = new Map(tokenResults.map(token => [token.bundle_number, token]))

  useEffect(() => {
    axios.get('/api/admin/session')
      .then(({ data }) => setIsAdmin(Boolean(data.is_admin)))
      .catch(() => setIsAdmin(false))
  }, [])
  const liveBundles = cookieBundles.filter((bundle) => {
    const account = accountByBundle.get(bundle.bundle_number)
    const token = tokenByBundle.get(bundle.bundle_number)
    return Boolean(account?.success || token?.success)
  })
  const cookieNameSummary = (bundle: CookieBundle) => {
    const counts = bundle.cookies
      .filter(cookie => cookie.name && cookie.value)
      .reduce<Record<string, number>>((result, cookie) => {
        result[cookie.name] = (result[cookie.name] || 0) + 1
        return result
      }, {})

    return Object.entries(counts)
      .sort(([nameA], [nameB]) => nameA.localeCompare(nameB))
      .map(([name, count]) => `${name} (${count})`)
      .join(', ')
  }

  const handleCopyCookies = async (bundleNumber: number, cookieHeader: string) => {
    try {
      await navigator.clipboard.writeText(cookieHeader)
      setCopiedBundleNumber(bundleNumber)
      window.setTimeout(() => setCopiedBundleNumber(null), 1800)
    } catch {
      alert('Unable to copy cookies to the clipboard.')
    }
  }

  const handleSaveToAdmin = async (bundle: CookieBundle) => {
    if (!isAdmin) return

    const account = accountByBundle.get(bundle.bundle_number) || {}
    const token = tokenByBundle.get(bundle.bundle_number) || {}

    setSavingBundleNumber(bundle.bundle_number)
    try {
      await axios.post('/api/admin/checked-cookies', {
        bundle_number: bundle.bundle_number,
        cookies: bundle.cookies,
        account,
        token,
      })
      setSavedBundleNumbers(current => current.includes(bundle.bundle_number)
        ? current
        : [...current, bundle.bundle_number])
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Unable to save this bundle to admin storage.')
    } finally {
      setSavingBundleNumber(null)
    }
  }

  if (loading) {
    return (
      <div className="cookies-list loading">
        <p>Analyzing cookies...</p>
      </div>
    )
  }

  if (validCookies.length === 0 || liveBundles.length === 0) {
    return null
  }

  return (
    <div className="cookies-list">
      <div className="cookies-header">
        <h3><Icon name="circleCheck" /> Checked Live Cookie Bundles ({liveBundles.length.toLocaleString()})</h3>
      </div>

      <div className="cookies-container">
        {liveBundles.map((bundle) => {
          const bundleCookies = bundle.cookies.filter(cookie => cookie.name && cookie.value)
          const cookieHeader = bundleCookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; ')

          return (
            <details className="cookie-item" key={bundle.bundle_number}>
              <summary className="cookie-item-summary">
                <div className="cookie-number-badge">#{bundle.bundle_number}</div>
                <div className="cookie-main">
                  <div className="cookie-name">
                    <strong>Live Cookie Bundle #{bundle.bundle_number}</strong>
                    <span className="cookie-summary-meta">
                      {bundleCookies.length.toLocaleString()} records
                    </span>
                  </div>
                </div>
              </summary>
              <div className="cookie-expanded">
                <div className="cookie-domain">
                  Records included: <code>{bundleCookies.length.toLocaleString()}</code>
                </div>
                <div className="cookie-domain">
                  Cookie names detected: <code>{cookieNameSummary(bundle)}</code>
                </div>
                <div className="cookie-expanded-header">
                  <div className="cookie-expanded-label">Full cookie bundle</div>
                  <div className="cookie-expanded-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      onClick={() => handleCopyCookies(bundle.bundle_number, cookieHeader)}
                    >
                      <Icon name="copy" />
                      {copiedBundleNumber === bundle.bundle_number ? 'Copied' : 'Copy Cookies'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      disabled={!isAdmin || savingBundleNumber === bundle.bundle_number || savedBundleNumbers.includes(bundle.bundle_number)}
                      onClick={() => handleSaveToAdmin(bundle)}
                      title={isAdmin ? 'Store this live bundle in admin storage' : 'Admin login required'}
                    >
                      <Icon name="circleCheck" />
                      {savingBundleNumber === bundle.bundle_number
                        ? 'Saving…'
                        : savedBundleNumbers.includes(bundle.bundle_number)
                          ? 'Saved'
                          : isAdmin
                            ? 'Save to Admin Storage'
                            : 'Admin login required'}
                    </button>
                  </div>
                </div>
                <pre className="cookie-full-value">{cookieHeader}</pre>
              </div>
            </details>
          )
        })}
      </div>
    </div>
  )
}

export default CookiesList
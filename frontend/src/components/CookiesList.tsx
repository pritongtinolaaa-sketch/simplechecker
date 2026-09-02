import React from 'react'
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
  const validCookies = cookies.filter(cookie => cookie.name && cookie.value)
  const accountByBundle = new Map(accounts.map(account => [account.bundle_number, account]))
  const tokenByBundle = new Map(tokenResults.map(token => [token.bundle_number, token]))
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
            <div className="cookie-item" key={bundle.bundle_number}>
              <div className="cookie-number-badge">#{bundle.bundle_number}</div>
              <div className="cookie-main">
                <div className="cookie-name">
                  <strong>Live Cookie Bundle #{bundle.bundle_number}</strong>
                </div>
                <div className="cookie-value">
                  <code>{cookieHeader.substring(0, 180)}{cookieHeader.length > 180 ? '...' : ''}</code>
                </div>
                <div className="cookie-domain">
                  Records included: <code>{bundleCookies.length.toLocaleString()}</code>
                </div>
                <div className="cookie-domain">
                  Cookie names detected: <code>{cookieNameSummary(bundle)}</code>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default CookiesList
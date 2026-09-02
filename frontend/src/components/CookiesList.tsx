import React from 'react'

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
  accountInfo?: AccountResult
  loading: boolean
}

const CookiesList: React.FC<CookiesListProps> = ({
  cookies,
  cookieBundles = [],
  accounts = [],
  tokenResults = [],
  accountInfo,
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

  const buildTokenLinks = (token?: TokenResult) => {
    if (!token?.success || !token.nftoken) {
      return `Netflix Token Link: ${token?.error || 'Unavailable'}\n`
    }

    const tokenUrl = `https://netflix.com/?nftoken=${encodeURIComponent(token.nftoken)}`
    const phoneTokenUrl = `https://www.netflix.com/unsupported?nftoken=${encodeURIComponent(token.nftoken)}`

    return [
      `Netflix Token Link: ${tokenUrl}`,
      `Open in Netflix: ${tokenUrl}`,
      `Open in Phone: ${phoneTokenUrl}`,
    ].join('\n\n') + '\n'
  }

  const buildAccountInfoBlock = (
    bundleNumber: number,
    account: AccountResult | undefined,
    token: TokenResult | undefined
  ) => {
    const details = account || (bundleNumber === 1 ? accountInfo : undefined)
    let content = `Cookie #${bundleNumber}\n`
    content += 'Account info:\n'

    if (details?.success) {
      content += `Email: ${details.email || 'N/A'}\n`
      content += `Country: ${details.country || 'N/A'}\n`
      content += `Plan: ${details.plan || 'N/A'}\n`
      if (details.streaming_quality) content += `Streaming Quality: ${details.streaming_quality}\n`
      if (details.subscription_status) content += `Subscription Status: ${details.subscription_status}\n`
      if (details.account_created_date) content += `Account Created: ${details.account_created_date}\n`
      if (details.billing_date) content += `Next Billing Date: ${details.billing_date}\n`
      if (details.payment_method) content += `Payment Method: ${details.payment_method}\n`
      if (details.profiles && details.profiles.length > 0) {
        content += `Profiles: ${details.profiles.map(profile => `${profile.name}${profile.isKids ? ' (Kids)' : ''}`).join(', ')}\n`
      }
    } else {
      content += `Status: ${details?.error || 'Live cookie bundle'}\n`
    }

    content += '\n'
    content += buildTokenLinks(token)
    content += '\n'
    return content
  }

  const handleDownloadLiveCookies = () => {
    if (liveBundles.length === 0) return

    const content = liveBundles.map((bundle) => {
      const account = accountByBundle.get(bundle.bundle_number)
      const token = tokenByBundle.get(bundle.bundle_number)
      const cookieHeader = bundle.cookies
        .filter(cookie => cookie.name && cookie.value)
        .map(cookie => `${cookie.name}=${cookie.value}`)
        .join('; ')

      return `${buildAccountInfoBlock(bundle.bundle_number, account, token)}================\n${cookieHeader}\n================\n`
    }).join('\n')

    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content))
    element.setAttribute('download', 'netflix-live-cookies.txt')
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
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
        <h3>✅ Checked Live Cookie Bundles ({liveBundles.length.toLocaleString()})</h3>
        <button
          className="btn btn-secondary btn-small"
          onClick={handleDownloadLiveCookies}
        >
          📥 Download Live Cookies ({liveBundles.length})
        </button>
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
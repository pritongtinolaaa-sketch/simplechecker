import React from 'react'
import Icon from './Icon'
import {
  buildCookieDownloadContent,
  downloadTextFile,
} from '../utils/cookieDownload'

interface Profile {
  name: string
  isKids: boolean
  guid: string
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
  profiles?: Profile[]
  error?: string
}

interface TokenResult {
  bundle_number: number
  success: boolean
  nftoken?: string
  error?: string
}

interface CookieBundle {
  bundle_number: number
  cookies: Array<{
    name: string
    value: string
  }>
}

interface AccountInfoProps {
  accounts?: AccountResult[]
  tokenResults?: TokenResult[]
  cookieBundles?: CookieBundle[]
  accountCount?: number
  bundleCount?: number
  checkedCookieCount?: number
  email?: string
  country?: string
  plan?: string
  subscriptionStatus?: string
  billingDate?: string
  accountCreatedDate?: string
  paymentMethod?: string
  streamingQuality?: string
  profiles?: Profile[]
  error?: string
  loading?: boolean
}

const AccountInfo: React.FC<AccountInfoProps> = ({
  accounts,
  tokenResults,
  cookieBundles = [],
  accountCount,
  bundleCount,
  checkedCookieCount,
  email,
  country,
  plan,
  subscriptionStatus,
  billingDate,
  accountCreatedDate,
  paymentMethod,
  streamingQuality,
  profiles,
  error,
  loading
}) => {
  const hasAccountResults = Boolean(accounts && accounts.length > 0)
  const hasPartialResults = hasAccountResults || Boolean(tokenResults && tokenResults.length > 0)

  if (loading && !hasPartialResults) {
    return (
      <div className="account-info loading">
        <h2><Icon name="chart" /> Account Information</h2>
        <p>Starting cookie bundle checks...</p>
      </div>
    )
  }

  const fallbackAccount: AccountResult = {
    bundle_number: 1,
    cookie_count: checkedCookieCount || 0,
    success: true,
    email,
    country,
    plan,
    subscription_status: subscriptionStatus,
    billing_date: billingDate,
    account_created_date: accountCreatedDate,
    payment_method: paymentMethod,
    streaming_quality: streamingQuality,
    profiles
  }
  const accountResults = hasAccountResults ? accounts || [] : [fallbackAccount]
  const totalAccountCount = accountCount ?? accountResults.length
  const accountByBundle = new Map(
    accountResults.map((account) => [account.bundle_number, account])
  )
  const tokenByBundle = new Map(
    (tokenResults || []).map((tokenResult) => [tokenResult.bundle_number, tokenResult])
  )
  const cookieBundleByNumber = new Map(
    cookieBundles.map((bundle) => [bundle.bundle_number, bundle])
  )
  const isBundleLive = (account: AccountResult) =>
    account.success || Boolean(tokenByBundle.get(account.bundle_number)?.success)
  const liveAccountResults = accountResults.filter(isBundleLive)
  const invalidAccountResults = accountResults.filter(account => !isBundleLive(account))
  const liveCookieBundles = cookieBundles.filter((bundle) => {
    const account = accountByBundle.get(bundle.bundle_number)
    const token = tokenByBundle.get(bundle.bundle_number)
    return Boolean(account?.success || token?.success)
  })

  const downloadBundle = (bundle: CookieBundle) => {
    const account = accountByBundle.get(bundle.bundle_number) ||
      (bundle.bundle_number === 1 ? fallbackAccount : undefined)
    const token = tokenByBundle.get(bundle.bundle_number)
    const content = buildCookieDownloadContent(bundle, account, token)
    downloadTextFile(content, `netflix-live-cookie-${bundle.bundle_number}.txt`)
  }

  const handleDownloadAll = () => {
    if (loading || liveCookieBundles.length === 0) return

    const content = liveCookieBundles
      .map((bundle) => {
        const account = accountByBundle.get(bundle.bundle_number) ||
          (bundle.bundle_number === 1 ? fallbackAccount : undefined)
        const token = tokenByBundle.get(bundle.bundle_number)
        return buildCookieDownloadContent(bundle, account, token)
      })
      .join('\n')

    downloadTextFile(content, 'netflix-live-cookies.txt')
  }

  const renderAccountDetails = (account: AccountResult) => (
    <>
      <div className="info-grid">
        {account.email && (
          <div className="info-item">
            <div className="info-label">Email</div>
            <div className="info-value">{account.email}</div>
          </div>
        )}

        {account.country && (
          <div className="info-item">
            <div className="info-label">Country</div>
            <div className="info-value">{account.country}</div>
          </div>
        )}

        {account.plan && (
          <div className="info-item">
            <div className="info-label">Plan</div>
            <div className="info-value">{account.plan}</div>
          </div>
        )}

        {account.streaming_quality && (
          <div className="info-item">
            <div className="info-label">Streaming Quality</div>
            <div className="info-value">{account.streaming_quality}</div>
          </div>
        )}

        {account.account_created_date && (
          <div className="info-item">
            <div className="info-label">Account Created</div>
            <div className="info-value">{account.account_created_date}</div>
          </div>
        )}

        {account.billing_date && (
          <div className="info-item">
            <div className="info-label">Next Billing Date</div>
            <div className="info-value">{account.billing_date}</div>
          </div>
        )}

        {account.payment_method && (
          <div className="info-item">
            <div className="info-label">Payment Method</div>
            <div className="info-value">{account.payment_method}</div>
          </div>
        )}

        {account.subscription_status && (
          <div className="info-item">
            <div className="info-label">Subscription Status</div>
            <div className="info-value">
              <span className={`status-badge ${account.subscription_status.toLowerCase()}`}>
                {account.subscription_status}
              </span>
            </div>
          </div>
        )}
      </div>

      {account.profiles && account.profiles.length > 0 && (
        <div className="profiles-section">
          <h3>Profiles ({account.profiles.length})</h3>
          <div className="profiles-list">
            {account.profiles.map((profile, idx) => (
              <div key={idx} className="profile-card">
                <div className="profile-icon">
                  <Icon name="user" size={20} />
                </div>
                <div className="profile-info">
                  <div className="profile-name">{profile.name}</div>
                  {profile.isKids && (
                    <span className="profile-badge kids">Kids</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )

  const renderBundleToken = (tokenResult: TokenResult) => {
    if (!tokenResult.success || !tokenResult.nftoken) {
      return (
        <div className="alert alert-warning bundle-token-error">
          <strong>Token unavailable:</strong> {tokenResult.error || 'No usable token was returned'}
        </div>
      )
    }

    const tokenUrl = `https://netflix.com/?nftoken=${encodeURIComponent(tokenResult.nftoken)}`
    const phoneTokenUrl = `https://www.netflix.com/unsupported?nftoken=${encodeURIComponent(tokenResult.nftoken)}`

    const handleCopyToken = () => {
      navigator.clipboard.writeText(tokenUrl).then(() => {
        alert('Netflix token link copied to clipboard!')
      })
    }

    return (
      <div className="bundle-token">
        <div className="bundle-token-header">
          <h4>Netflix Token Link</h4>
          <span className="badge badge-success"><Icon name="check" /> Ready</span>
        </div>
        <div className="token-link-container">
          <a
            href={tokenUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="token-link"
          >
            {tokenUrl}
          </a>
        </div>
        <div className="token-actions">
          <button className="btn btn-primary" onClick={handleCopyToken}>
            <><Icon name="copy" /> Copy Link</>
          </button>
          <a
            href={tokenUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            <><Icon name="external" /> Open in Netflix</>
          </a>
          <a
            href={phoneTokenUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            <><Icon name="phone" /> Open in Phone</>
          </a>
        </div>
      </div>
    )
  }

  const renderAccountResult = (account: AccountResult, collapsible = false) => {
    const bundleIsLive = isBundleLive(account)
    const tokenResult = tokenByBundle.get(account.bundle_number)
    const accountContent = (
      <>
        {account.success ? (
          renderAccountDetails(account)
        ) : bundleIsLive ? (
          <div className="alert alert-warning">
            <strong>Account details unavailable:</strong> {account.error ||
              'The cookies generated a live token, but Netflix did not return account details.'}
          </div>
        ) : (
          <div className="alert alert-error">
            <strong>Error:</strong> {tokenResult?.error || account.error || 'Cookies may be expired or invalid'}
          </div>
        )}

        {tokenResult && renderBundleToken(tokenResult)}
      </>
    )
    const downloadButton = bundleIsLive && cookieBundleByNumber.has(account.bundle_number) && (
      <button
        className="btn btn-secondary btn-small bundle-download-btn"
        onClick={(event) => {
          event.stopPropagation()
          downloadBundle(cookieBundleByNumber.get(account.bundle_number)!)
        }}
        title={`Download Cookie Bundle #${account.bundle_number}`}
      >
        <><Icon name="download" /> Download</>
      </button>
    )

    if (collapsible) {
      return (
        <details
          key={account.bundle_number}
          className={`account-result account-result-collapsible ${bundleIsLive ? '' : 'failed'}`}
        >
          <summary className="account-result-header">
            <div className="account-result-summary-main">
              <h3>Cookie Bundle #{account.bundle_number}</h3>
            </div>
            <div className="account-result-actions">
              <span className={`badge ${bundleIsLive ? 'badge-success' : 'badge-default'}`}>
                {bundleIsLive ? <><Icon name="check" /> Live</> : 'Expired / Invalid'}
              </span>
              {downloadButton}
            </div>
            <div className="account-result-summary-fields">
              {account.email && (
                <span><strong>Email</strong>{account.email}</span>
              )}
              {account.country && (
                <span><strong>Country</strong>{account.country}</span>
              )}
              {account.plan && (
                <span><strong>Plan</strong>{account.plan}</span>
              )}
            </div>
          </summary>
          <div className="account-result-content">
            {accountContent}
          </div>
        </details>
      )
    }

    return (
      <div
        key={account.bundle_number}
        className={`account-result ${bundleIsLive ? '' : 'failed'}`}
      >
        <div className="account-result-header">
          <h3>Cookie Bundle #{account.bundle_number}</h3>
          <div className="account-result-actions">
            <span className={`badge ${bundleIsLive ? 'badge-success' : 'badge-default'}`}>
              {bundleIsLive ? <><Icon name="check" /> Live</> : 'Expired / Invalid'}
            </span>
            {downloadButton}
          </div>
        </div>

        {accountContent}
      </div>
    )
  }

  if (error && !hasAccountResults) {
    return (
      <div className="account-info error">
        <h2><Icon name="chart" /> Account Information</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  if (!hasAccountResults && !email && !country && !plan && !billingDate && !paymentMethod) {
    return (
      <div className="account-info empty">
        <h2><Icon name="chart" /> Account Information</h2>
        <p>Click "Get Netflix Info" to extract account details from cookies.</p>
      </div>
    )
  }

  return (
    <div className="account-info">
      <div className="info-header">
        <h2>
          <Icon name="chart" /> Live Account Information
          {hasAccountResults && ` (${liveAccountResults.length}/${totalAccountCount})`}
        </h2>
        <div className="info-header-actions">
          <span className={`badge ${loading ? 'badge-checking' : 'badge-success'}`}>
            {hasAccountResults
              ? `${liveAccountResults.length} Live${loading ? ' · Checking…' : ''}`
              : <><Icon name="check" /> Retrieved</>}
          </span>
          <button
            className="btn btn-secondary btn-small download-all-btn"
            onClick={handleDownloadAll}
            disabled={loading || liveCookieBundles.length === 0}
            title={loading ? 'Available when checking is complete' : 'Download all live cookies'}
          >
            <><Icon name="download" /> Download All{liveCookieBundles.length > 0 ? ` (${liveCookieBundles.length})` : ''}</>
          </button>
        </div>
      </div>

      {hasAccountResults && (
        <p className="account-summary">
          Checked {bundleCount?.toLocaleString() || totalAccountCount.toLocaleString()} cookie bundles
          {checkedCookieCount ? ` containing ${checkedCookieCount.toLocaleString()} cookies` : ''}.
          {loading && ' Live results appear here as each bundle finishes.'}
        </p>
      )}

      {liveAccountResults.length > 0 && (
        <section className="account-group live-account-group">
          <div className="account-group-header">
            <h3>Working / Live Cookies ({liveAccountResults.length})</h3>
            <span>Click a bundle to expand</span>
          </div>
          <div className="account-results">
            {liveAccountResults.map((account) => renderAccountResult(account, true))}
          </div>
        </section>
      )}

      {invalidAccountResults.length > 0 && (
        <details className="account-group invalid-account-group">
          <summary className="account-group-header">
            <h3>Expired / Invalid Cookies ({invalidAccountResults.length})</h3>
            <span>Not working</span>
          </summary>
          <div className="account-results">
            {invalidAccountResults.map((account) => renderAccountResult(account))}
          </div>
        </details>
      )}
    </div>
  )
}

export default AccountInfo

import React from 'react'

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

interface AccountInfoProps {
  accounts?: AccountResult[]
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
  if (loading) {
    return (
      <div className="account-info loading">
        <h2>📊 Account Information</h2>
        <p>Loading account details...</p>
      </div>
    )
  }

  const hasAccountResults = Boolean(accounts && accounts.length > 0)
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
  const successfulAccountCount = accountResults.filter(account => account.success).length
  const totalAccountCount = accountCount ?? accountResults.length

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
                  {profile.isKids ? '👶' : '👤'}
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

  if (error && !hasAccountResults) {
    return (
      <div className="account-info error">
        <h2>📊 Account Information</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  if (!hasAccountResults && !email && !country && !plan && !billingDate && !paymentMethod) {
    return (
      <div className="account-info empty">
        <h2>📊 Account Information</h2>
        <p>Click "Get Netflix Info" to extract account details from cookies.</p>
      </div>
    )
  }

  return (
    <div className="account-info">
      <div className="info-header">
        <h2>
          📊 Live Account Information
          {hasAccountResults && ` (${successfulAccountCount}/${totalAccountCount})`}
        </h2>
        <span className="badge badge-success">
          {hasAccountResults ? `${successfulAccountCount} Retrieved` : '✓ Retrieved'}
        </span>
      </div>

      {hasAccountResults && (
        <p className="account-summary">
          Checked {bundleCount?.toLocaleString() || totalAccountCount.toLocaleString()} cookie bundles
          {checkedCookieCount ? ` containing ${checkedCookieCount.toLocaleString()} cookies` : ''}.
        </p>
      )}

      <div className="account-results">
        {accountResults.map((account) => (
          <div
            key={account.bundle_number}
            className={`account-result ${account.success ? '' : 'failed'}`}
          >
            <div className="account-result-header">
              <h3>Cookie Bundle #{account.bundle_number}</h3>
              <span className={`badge ${account.success ? 'badge-success' : 'badge-default'}`}>
                {account.success ? '✓ Live' : 'Unavailable'}
              </span>
            </div>

            {account.success ? (
              renderAccountDetails(account)
            ) : (
              <div className="alert alert-error">
                <strong>Error:</strong> {account.error || 'Could not extract account information'}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default AccountInfo

import React from 'react'

interface Profile {
  name: string
  isKids: boolean
  guid: string
}

interface AccountInfoProps {
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

  if (error) {
    return (
      <div className="account-info error">
        <h2>📊 Account Information</h2>
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      </div>
    )
  }

  if (!email && !country && !plan && !billingDate && !paymentMethod) {
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
        <h2>📊 Account Information</h2>
        <span className="badge badge-success">✓ Retrieved</span>
      </div>

      <div className="info-grid">
        {email && (
          <div className="info-item">
            <div className="info-label">Email</div>
            <div className="info-value">{email}</div>
          </div>
        )}

        {country && (
          <div className="info-item">
            <div className="info-label">Country</div>
            <div className="info-value">{country}</div>
          </div>
        )}

        {plan && (
          <div className="info-item">
            <div className="info-label">Plan</div>
            <div className="info-value">{plan}</div>
          </div>
        )}

        {streamingQuality && (
          <div className="info-item">
            <div className="info-label">Streaming Quality</div>
            <div className="info-value">{streamingQuality}</div>
          </div>
        )}

        {accountCreatedDate && (
          <div className="info-item">
            <div className="info-label">Account Created</div>
            <div className="info-value">{accountCreatedDate}</div>
          </div>
        )}

        {billingDate && (
          <div className="info-item">
            <div className="info-label">Next Billing Date</div>
            <div className="info-value">{billingDate}</div>
          </div>
        )}

        {paymentMethod && (
          <div className="info-item">
            <div className="info-label">Payment Method</div>
            <div className="info-value">{paymentMethod}</div>
          </div>
        )}

        {subscriptionStatus && (
          <div className="info-item">
            <div className="info-label">Subscription Status</div>
            <div className="info-value">
              <span className={`status-badge ${subscriptionStatus.toLowerCase()}`}>
                {subscriptionStatus}
              </span>
            </div>
          </div>
        )}
      </div>

      {profiles && profiles.length > 0 && (
        <div className="profiles-section">
          <h3>Profiles ({profiles.length})</h3>
          <div className="profiles-list">
            {profiles.map((profile, idx) => (
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
    </div>
  )
}

export default AccountInfo

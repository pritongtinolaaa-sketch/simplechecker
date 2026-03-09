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

interface CookiesListProps {
  cookies: Cookie[]
  accountInfo?: {
    email?: string
    country?: string
    plan?: string
    subscription_status?: string
    billing_date?: string
    account_created_date?: string
    payment_method?: string
    streaming_quality?: string
    profiles?: any[]
  }
  loading: boolean
}

const CookiesList: React.FC<CookiesListProps> = ({ cookies, accountInfo, loading }) => {
  // Filter out invalid cookies (empty name or value)
  const validCookies = cookies.filter(cookie => cookie.name && cookie.value)

  const formatAccountInfo = (info: any): string => {
    let output = 'ACCOUNT INFORMATION CHECKED ON THAT COOKIE\n'
    output += '==========================\n\n'
    
    if (info.email) output += `Email: ${info.email}\n`
    if (info.country) output += `Country: ${info.country}\n`
    if (info.plan) output += `Plan: ${info.plan}\n`
    if (info.streaming_quality) output += `Streaming Quality: ${info.streaming_quality}\n`
    if (info.subscription_status) output += `Subscription Status: ${info.subscription_status}\n`
    if (info.account_created_date) output += `Account Created: ${info.account_created_date}\n`
    if (info.billing_date) output += `Next Billing Date: ${info.billing_date}\n`
    if (info.payment_method) output += `Payment Method: ${info.payment_method}\n`
    if (info.profiles && info.profiles.length > 0) {
      output += `\nProfiles (${info.profiles.length}):\n`
      info.profiles.forEach((profile: any) => {
        output += `  - ${profile.name}${profile.isKids ? ' (Kids)' : ''}\n`
      })
    }
    
    return output
  }

  const wrapText = (text: string, maxLength: number = 100): string => {
    const words = text.split(' ')
    let lines: string[] = []
    let currentLine = ''
    
    words.forEach(word => {
      if ((currentLine + word).length > maxLength && currentLine) {
        lines.push(currentLine.trim())
        currentLine = word
      } else {
        currentLine += (currentLine ? ' ' : '') + word
      }
    })
    
    if (currentLine) {
      lines.push(currentLine.trim())
    }
    
    return lines.join('\n')
  }

  const handleDownloadCookie = (cookie: Cookie, cookieNumber: number) => {
    let content = ''
    
    if (accountInfo) {
      content += `-Cookie #${cookieNumber}-\n`
      content += `Email: ${accountInfo.email || 'N/A'}\n`
      content += `Country: ${accountInfo.country || 'N/A'}\n`
      content += `Plan: ${accountInfo.plan || 'N/A'}\n`
      if (accountInfo.streaming_quality) content += `Streaming Quality: ${accountInfo.streaming_quality}\n`
      if (accountInfo.subscription_status) content += `Subscription Status: ${accountInfo.subscription_status}\n`
      if (accountInfo.account_created_date) content += `Account Created: ${accountInfo.account_created_date}\n`
      if (accountInfo.billing_date) content += `Next Billing Date: ${accountInfo.billing_date}\n`
      if (accountInfo.payment_method) content += `Payment Method: ${accountInfo.payment_method}\n`
      if (accountInfo.profiles && accountInfo.profiles.length > 0) {
        content += `Profiles: ${accountInfo.profiles.map((p: any) => p.name).join(', ')}\n`
      }
    }
    
    content += '\n==========================\n'
    content += wrapText(`${cookie.name}=${cookie.value}`) + '\n'
    
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content))
    element.setAttribute('download', `cookie-${cookieNumber}-${cookie.name}.txt`)
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const handleDownloadAll = () => {
    if (validCookies.length === 0) return
    
    let content = ''
    
    if (accountInfo) {
      content += `-Cookie #1-\n`
      content += `Email: ${accountInfo.email || 'N/A'}\n`
      content += `Country: ${accountInfo.country || 'N/A'}\n`
      content += `Plan: ${accountInfo.plan || 'N/A'}\n`
      if (accountInfo.streaming_quality) content += `Streaming Quality: ${accountInfo.streaming_quality}\n`
      if (accountInfo.subscription_status) content += `Subscription Status: ${accountInfo.subscription_status}\n`
      if (accountInfo.account_created_date) content += `Account Created: ${accountInfo.account_created_date}\n`
      if (accountInfo.billing_date) content += `Next Billing Date: ${accountInfo.billing_date}\n`
      if (accountInfo.payment_method) content += `Payment Method: ${accountInfo.payment_method}\n`
      if (accountInfo.profiles && accountInfo.profiles.length > 0) {
        content += `Profiles: ${accountInfo.profiles.map((p: any) => p.name).join(', ')}\n`
      }
    }
    
    content += '\n==========================\n'
    const cookieString = validCookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; ')
    content += wrapText(cookieString) + '\n'
    
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content))
    element.setAttribute('download', 'netflix-info-all-cookies.txt')
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

  if (validCookies.length === 0) {
    return null
  }

  return (
    <div className="cookies-list">
      <div className="cookies-header">
        <h3>✅ Checked Cookies ({validCookies.length})</h3>
        <button 
          className="btn btn-secondary btn-small"
          onClick={handleDownloadAll}
        >
          📥 Download All Cookies
        </button>
      </div>

      <div className="cookies-container">
        {validCookies.map((cookie, idx) => {
          const cookieNumber = idx + 1
          return (
            <div key={idx} className="cookie-item">
              <div className="cookie-number-badge">#{cookieNumber}</div>
              <div className="cookie-main">
                <div className="cookie-name">
                  <strong>{cookie.name}</strong>
                </div>
                <div className="cookie-value">
                  <code>{cookie.value.substring(0, 80)}{cookie.value.length > 80 ? '...' : ''}</code>
                </div>
                {cookie.domain && (
                  <div className="cookie-domain">
                    Domain: <code>{cookie.domain}</code>
                  </div>
                )}
              </div>
              <button
                className="btn btn-primary btn-small"
                onClick={() => handleDownloadCookie(cookie, cookieNumber)}
              >
                ⬇️ Download
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default CookiesList

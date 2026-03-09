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
  const fullCookieHeader = validCookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; ')

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

  const buildAccountInfoBlock = (cookieNumber: number) => {
    let content = `-Cookie #${cookieNumber}-\n`
    content += `Email: ${accountInfo?.email || 'N/A'}\n`
    content += `Country: ${accountInfo?.country || 'N/A'}\n`
    content += `Plan: ${accountInfo?.plan || 'N/A'}\n`
    if (accountInfo?.streaming_quality) content += `Streaming Quality: ${accountInfo.streaming_quality}\n`
    if (accountInfo?.subscription_status) content += `Subscription Status: ${accountInfo.subscription_status}\n`
    if (accountInfo?.account_created_date) content += `Account Created: ${accountInfo.account_created_date}\n`
    if (accountInfo?.billing_date) content += `Next Billing Date: ${accountInfo.billing_date}\n`
    if (accountInfo?.payment_method) content += `Payment Method: ${accountInfo.payment_method}\n`
    if (accountInfo?.profiles && accountInfo.profiles.length > 0) {
      content += `Profiles: ${accountInfo.profiles.map((p: any) => p.name).join(', ')}\n`
    }
    return content
  }

  const handleDownloadCookiePackage = (cookieNumber: number) => {
    let content = ''

    content += buildAccountInfoBlock(cookieNumber)
    content += '\n==========================\n'
    content += wrapText(fullCookieHeader) + '\n'
    
    const element = document.createElement('a')
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content))
    element.setAttribute('download', `cookie-${cookieNumber}.txt`)
    element.style.display = 'none'
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const handleDownloadAll = () => {
    if (validCookies.length === 0) return
    
    let content = ''

    content += buildAccountInfoBlock(1)
    content += '\n==========================\n'
    content += wrapText(fullCookieHeader) + '\n'
    
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
        <h3>✅ Checked Cookies (1)</h3>
        <button 
          className="btn btn-secondary btn-small"
          onClick={handleDownloadAll}
        >
          📥 Download All Cookies
        </button>
      </div>

      <div className="cookies-container">
        <div className="cookie-item">
          <div className="cookie-number-badge">#1</div>
          <div className="cookie-main">
            <div className="cookie-name">
              <strong>Full Cookie Header</strong>
            </div>
            <div className="cookie-value">
              <code>{fullCookieHeader.substring(0, 180)}{fullCookieHeader.length > 180 ? '...' : ''}</code>
            </div>
            <div className="cookie-domain">
              Keys included: <code>{validCookies.length}</code>
            </div>
          </div>
          <button
            className="btn btn-primary btn-small"
            onClick={() => handleDownloadCookiePackage(1)}
          >
            ⬇️ Download
          </button>
        </div>
      </div>
    </div>
  )
}

export default CookiesList

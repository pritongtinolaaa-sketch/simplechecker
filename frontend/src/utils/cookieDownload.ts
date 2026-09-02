export interface DownloadCookie {
  name: string
  value: string
}

export interface DownloadProfile {
  name: string
  isKids?: boolean
}

export interface DownloadAccount {
  bundle_number?: number
  success?: boolean
  email?: string
  country?: string
  plan?: string
  subscription_status?: string
  billing_date?: string
  account_created_date?: string
  payment_method?: string
  streaming_quality?: string
  profiles?: DownloadProfile[]
  error?: string
}

export interface DownloadBundle {
  bundle_number: number
  cookies: DownloadCookie[]
}

export const buildCookieDownloadContent = (
  bundle: DownloadBundle,
  account?: DownloadAccount,
  accountInfo?: DownloadAccount
) => {
  const details = account || (bundle.bundle_number === 1 ? accountInfo : undefined)
  let content = `Cookie #${bundle.bundle_number}\n\n`
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

  const cookieHeader = bundle.cookies
    .filter(cookie => cookie.name && cookie.value)
    .map(cookie => `${cookie.name}=${cookie.value}`)
    .join('; ')

  return `${content}================\n${cookieHeader}\n================\n`
}

export const downloadTextFile = (content: string, filename: string) => {
  const element = document.createElement('a')
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content))
  element.setAttribute('download', filename)
  element.style.display = 'none'
  document.body.appendChild(element)
  element.click()
  document.body.removeChild(element)
}
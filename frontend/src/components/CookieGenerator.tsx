import { useEffect, useState } from 'react'
import axios from 'axios'
import Icon from './Icon'
import { formatPhtDateTime } from '../utils/date'

const GENERATOR_MAX_GENERATIONS = 5
const GENERATOR_RESET_MESSAGE = 'Resets daily at 12:00 AM PHT'
const GENERATOR_LIMIT_MESSAGE = 'Daily generation limit reached. Resets at 12:00 AM PHT.'
const DEFAULT_GENERATOR_MAINTENANCE_MESSAGE = 'Under maintenance. Please come back later.'

const getManilaDate = () => {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Manila',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return `${values.year}-${values.month}-${values.day}`
}

export interface GeneratorState {
  success: boolean
  id: number
  storage_position: number
  bundle_number: number
  checked_at: string
  account: Record<string, any>
  token: Record<string, any>
  links: Record<string, string>
  generation_count?: number | null
  generation_limit?: number | null
  generation_date?: string | null
}

type GeneratorStatus = {
  enabled: boolean
  message: string
}

type StoredHealth = {
  last_checked_at: string | null
  is_checking: boolean
}

export default function CookieGenerator({
  isAdmin = false,
  adminStatusReady = true,
  current: initialCurrent = null,
  onCurrentChange,
}: {
  isAdmin?: boolean
  adminStatusReady?: boolean
  current?: GeneratorState | null
  onCurrentChange?: (current: GeneratorState | null) => void
}) {
  const [loading, setLoading] = useState(!initialCurrent)
  const [error, setError] = useState('')
  const [generationCount, setGenerationCount] = useState<number | null>(
    initialCurrent?.generation_count ?? null,
  )
  const [generationDate, setGenerationDate] = useState<string | null>(
    initialCurrent?.generation_date ?? null,
  )
  const [generatorStatus, setGeneratorStatus] = useState<GeneratorStatus | null>(null)
  const [generatorStatusError, setGeneratorStatusError] = useState('')
  const [storedHealth, setStoredHealth] = useState<StoredHealth>({
    last_checked_at: null,
    is_checking: false,
  })
  const current = initialCurrent
  const generatorDisabled = generatorStatus?.enabled === false
  const generatorReady = generatorStatus?.enabled === true
  const generationLimitReached =
    !isAdmin &&
    generationCount !== null &&
    generationCount >= GENERATOR_MAX_GENERATIONS

  useEffect(() => {
    let active = true

    const loadGeneratorStatus = async () => {
      try {
        const response = await axios.get('/api/generator/status')
        if (!active) return
        setGeneratorStatus({
          enabled: Boolean(response.data.enabled),
          message:
            typeof response.data.message === 'string' && response.data.message.trim()
              ? response.data.message
              : DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,
        })
        setGeneratorStatusError('')
      } catch {
        if (!active) return
        setGeneratorStatus(null)
        setGeneratorStatusError('Unable to verify generator status. Please try again later.')
        setLoading(false)
      }
    }

    loadGeneratorStatus()
    const timer = window.setInterval(loadGeneratorStatus, 30_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    let active = true

    const loadStoredHealth = async () => {
      try {
        const response = await axios.get('/api/stored-cookies/health')
        if (!active) return
        setStoredHealth({
          last_checked_at:
            typeof response.data.last_checked_at === 'string'
              ? response.data.last_checked_at
              : null,
          is_checking: Boolean(response.data.is_checking),
        })
      } catch {
        // The generator can still work if health metadata is temporarily unavailable.
      }
    }

    loadStoredHealth()
    const timer = window.setInterval(loadStoredHealth, 60_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const loadStoredBundles = async () => {
    try {
      const response = await axios.get('/api/stored-cookies')
      return response.data.items || []
    } catch {
      return []
    }
  }

  const nextCookie = async () => {
    if (!adminStatusReady || !generatorReady || (!isAdmin && generationLimitReached)) {
      if (generationLimitReached) {
        setError(GENERATOR_LIMIT_MESSAGE)
      }
      return
    }

    setLoading(true)
    setError('')

    try {
      const bundles = await loadStoredBundles()
      if (bundles.length === 0) {
        onCurrentChange?.(null)
        setError('No stored cookie bundles are available yet.')
        return
      }

      const response = await axios.get('/api/stored-cookies/next')
      const next = response.data
      if (typeof next.generation_count === 'number') {
        setGenerationCount(next.generation_count)
      }
      if (typeof next.generation_date === 'string') {
        setGenerationDate(next.generation_date)
      }
      onCurrentChange?.(next)
    } catch (err: any) {
      if (err.response?.status === 429) {
        setGenerationCount(GENERATOR_MAX_GENERATIONS)
        setGenerationDate(getManilaDate())
        setError(
          err.response?.data?.detail ||
            GENERATOR_LIMIT_MESSAGE,
        )
      } else if (err.response?.status === 503) {
        const message =
          err.response?.data?.detail || DEFAULT_GENERATOR_MAINTENANCE_MESSAGE
        setGeneratorStatus({ enabled: false, message })
        setLoading(false)
      } else {
        onCurrentChange?.(null)
        setError(err.response?.data?.detail || 'No valid stored cookies are available right now.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!adminStatusReady || !generatorReady) return
    if (generatorDisabled) {
      setLoading(false)
      return
    }
    if (initialCurrent) {
      setLoading(false)
      return
    }
    nextCookie()
  }, [initialCurrent, adminStatusReady, generatorReady, generatorDisabled])

  useEffect(() => {
    if (isAdmin || !generationDate) return

    const resetIfNewManilaDay = () => {
      if (generationDate !== getManilaDate()) {
        setGenerationCount(0)
        setGenerationDate(getManilaDate())
      }
    }

    resetIfNewManilaDay()
    const timer = window.setInterval(resetIfNewManilaDay, 30_000)
    return () => window.clearInterval(timer)
  }, [generationDate, isAdmin])

  const moveToNext = async () => {
    if (generationLimitReached) {
      setError(GENERATOR_LIMIT_MESSAGE)
      return
    }
    const bundles = await loadStoredBundles()
    if (bundles.length === 0) {
      onCurrentChange?.(null)
      setError('No remaining stored cookie bundles. Refresh or re-open admin storage.')
      return
    }
    await nextCookie()
  }

  const accountSummary = current?.account ? current.account : null
  const hasAccountFields = accountSummary && typeof accountSummary === 'object' && Object.keys(accountSummary).length > 0
  const accountFields = accountSummary
    ? [
        ['Email', accountSummary.email],
        ['Plan', accountSummary.plan],
        ['Country', accountSummary.country],
        ['Subscription', accountSummary.subscription_status || accountSummary.status],
        ['Billing date', accountSummary.billing_date],
        ['Account created', accountSummary.account_created_date],
        ['Payment method', accountSummary.payment_method],
        ['Streaming quality', accountSummary.streaming_quality],
      ].filter(([, value]) => value !== undefined && value !== null && value !== '')
    : []
  const profiles = Array.isArray(accountSummary?.profiles) ? accountSummary.profiles : []
  const tokenReady = Boolean(current?.token?.success || current?.token?.nftoken)

  return (
    <main className="admin-page generator-page">
      <div className="admin-toolbar">
        <div>
          <span className="eyebrow">Generator</span>
          <h2>Stored Cookie Generator</h2>
        </div>
        <div className="admin-actions generator-actions">
          <button
            className="btn btn-primary generator-button"
            onClick={nextCookie}
            disabled={loading || !adminStatusReady || !generatorReady || generationLimitReached}
          >
            <span>{generationLimitReached ? 'Generation limit reached' : 'Next cookie'}</span>
            {!generationLimitReached && <Icon name="arrowRight" size={17} />}
          </button>
        </div>
      </div>

      {error && <p className="admin-error">{error}</p>}
      {generatorStatusError && <p className="admin-error">{generatorStatusError}</p>}

      {generatorDisabled ? (
        <section className="generator-maintenance-card" role="status" aria-live="polite">
          <span className="eyebrow">Generator unavailable</span>
          <h3>{generatorStatus?.message || DEFAULT_GENERATOR_MAINTENANCE_MESSAGE}</h3>
        </section>
      ) : (
        <>
          {!isAdmin && adminStatusReady && generationCount !== null && (
            <p className={`generator-limit-note${generationLimitReached ? ' is-limit-reached' : ''}`}>
              Generations used: {generationCount}/{GENERATOR_MAX_GENERATIONS} · {GENERATOR_RESET_MESSAGE}
            </p>
          )}
          <p className="generator-health-note">
            Last checked:{' '}
            {storedHealth.last_checked_at
              ? formatPhtDateTime(storedHealth.last_checked_at)
              : storedHealth.is_checking
                ? 'Checking now…'
                : 'Pending first hourly check'}
            {' · Health checks run hourly'}
          </p>

          {!current && !loading && (
            <section className="admin-empty">
              <p>
                {generationLimitReached
                  ? GENERATOR_LIMIT_MESSAGE
                  : 'No cookie generator result selected yet.'}
              </p>
              <button
                className="btn btn-primary generator-button generator-generate-button"
                onClick={nextCookie}
                disabled={!adminStatusReady || !generatorReady || generationLimitReached}
              >
                <Icon name="cookie" size={17} />
                {generationLimitReached
                  ? 'Generation limit reached'
                  : 'Generate from stored cookies'}
              </button>
            </section>
          )}

          {current && (
            <section className="stored-card generator-result-card">
          <div className="generator-result-header">
            <div className="generator-result-title">
              <span className="eyebrow">Generator result</span>
              <strong>Stored Cookie #{current.storage_position}</strong>
              <small>{formatPhtDateTime(current.checked_at)}</small>
            </div>
            <div className="generator-result-meta">
              <span className={`generator-status ${current.success ? 'is-live' : 'is-invalid'}`}>
                <span className="generator-status-dot" />
                {current.success ? 'Working' : 'Not working'}
              </span>
              {tokenReady && <span className="generator-token-status">Token ready</span>}
            </div>
          </div>

          {accountSummary?.error && (
            <p className="generator-refresh-note">
              <strong>Refresh note:</strong> {String(accountSummary.error)}
            </p>
          )}

          {hasAccountFields && accountFields.length > 0 && (
            <div className="generator-account-section">
              <div className="generator-section-heading">
                <span>Account snapshot</span>
                <span className="generator-section-line" />
              </div>
              <div className="info-grid generator-info-grid">
                {accountFields.map(([label, value]) => (
                  <div className="info-item" key={String(label)}>
                    <div className="info-label">{String(label)}</div>
                    <div className="info-value">{String(value)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {profiles.length > 0 && (
            <div className="generator-profiles">
              <span className="generator-profiles-label">Profiles</span>
              {profiles.map((profile: any, index: number) => (
                <span className="generator-profile-pill" key={`${String(profile.name || 'Profile')}-${index}`}>
                  {String(profile.name || 'Profile')}
                </span>
              ))}
            </div>
          )}

          {current.links && Object.keys(current.links).length > 0 && (
            <div className="generator-result-footer">
              <div className="generator-link-actions">
                <span className="generator-actions-label">Quick actions</span>
                {Object.entries(current.links).map(([label, url]) => (
                  <a key={label} href={url} target="_blank" rel="noreferrer" className="btn btn-secondary generator-button generator-link-button">
                    {label === 'tv' && <Icon name="film" size={17} />}
                    {label === 'netflix' && <Icon name="external" size={17} />}
                    {label === 'phone' && <Icon name="phone" size={17} />}
                    <span>{label === 'tv' ? 'TV login' : label === 'netflix' ? 'Open Netflix (PC)' : 'Phone login'}</span>
                  </a>
                ))}
              </div>
              <button
                className="btn btn-primary generator-button generator-next-button"
                onClick={moveToNext}
                disabled={loading || !adminStatusReady || generationLimitReached}
              >
                <span>{generationLimitReached ? 'Generation limit reached' : 'Next cookie'}</span>
                {!generationLimitReached && <Icon name="arrowRight" size={17} />}
              </button>
            </div>
          )}
            </section>
          )}

          {loading && (
            <section className="generator-loading-state" role="status" aria-live="polite">
              <div className="generator-loading-header">
                <strong>Loading stored cookie</strong>
                <span>Working…</span>
              </div>
              <div
                className="generator-loading-track"
                role="progressbar"
                aria-label="Loading stored cookie"
                aria-valuetext="Generating account details and login links"
              >
                <div className="generator-loading-fill" />
              </div>
              <p>Generating account details and login links…</p>
            </section>
          )}
        </>
      )}
    </main>
  )
}

const PHT_TIME_ZONE = 'Asia/Manila'

function parseApiDate(value: string): Date {
  const normalized = value.trim()
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  return new Date(hasTimezone ? normalized : `${normalized}Z`)
}

export function formatPhtDateTime(value: string | Date): string {
  const date = value instanceof Date ? value : parseApiDate(value)

  if (Number.isNaN(date.getTime())) {
    return 'Unknown time'
  }

  const formatted = new Intl.DateTimeFormat('en-PH', {
    timeZone: PHT_TIME_ZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date)

  return `${formatted} PHT`
}
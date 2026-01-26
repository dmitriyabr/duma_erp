export const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'short',
    timeStyle: 'short',
    hour12: false,
  }).format(date)
}

export const formatDate = (value?: string | null) => {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'short',
  }).format(date)
}

export const formatMoney = (value?: number | null) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

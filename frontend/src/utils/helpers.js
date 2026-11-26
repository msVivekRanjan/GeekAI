import { format, parseISO, formatDistanceToNow } from 'date-fns'

export function formatDate(dateStr) {
  if (!dateStr) return '—'
  try {
    return format(parseISO(dateStr), 'MMM d, yyyy h:mm a')
  } catch {
    return dateStr
  }
}

export function formatShortDate(dateStr) {
  if (!dateStr) return '—'
  try {
    return format(parseISO(dateStr), 'MMM d, yyyy')
  } catch {
    return dateStr
  }
}

export function timeAgo(dateStr) {
  if (!dateStr) return '—'
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true })
  } catch {
    return dateStr
  }
}

export function getCategoryColor(category) {
  const colors = {
    STUDENT: 'bg-blue-100 text-blue-800',
    RESEARCHER: 'bg-purple-100 text-purple-800',
    PROFESSIONAL: 'bg-amber-100 text-amber-800',
    SPEAKER: 'bg-emerald-100 text-emerald-800',
    OTHER: 'bg-gray-100 text-gray-800',
  }
  return colors[category] || colors.OTHER
}

export function getMethodBadge(method) {
  const badges = {
    QR: 'bg-green-100 text-green-800',
    MANUAL: 'bg-yellow-100 text-yellow-800',
  }
  return badges[method] || 'bg-gray-100 text-gray-800'
}

export function truncate(str, len = 30) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

export function resolveMediaUrl(url) {
  if (!url) return null
  if (
    url.startsWith('http://') ||
    url.startsWith('https://') ||
    url.startsWith('data:')
  ) {
    return url
  }
  const path = url.startsWith('/') ? url : `/${url}`
  const apiOrigin = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
  if (apiOrigin && (path.startsWith('/api/') || path.startsWith('/uploads/'))) {
    return `${apiOrigin}${path}`
  }
  return path
}

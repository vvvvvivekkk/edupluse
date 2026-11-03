// Thin wrapper around fetch: adds the bearer token and turns API errors into readable messages.
const TOKEN_KEY = 'edupulse_token'
const USER_KEY = 'edupulse_user'

export function getSession() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const user = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    return token && user ? { token, user } : null
  } catch {
    return null
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function errorMessage(detail) {
  if (!detail) return 'Something went wrong'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg?.replace('Value error, ', '') || JSON.stringify(d)).join('; ')
  return JSON.stringify(detail)
}

export async function api(path, { method = 'GET', body } = {}) {
  const s = getSession()
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData // file upload: browser sets the boundary
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(s ? { Authorization: `Bearer ${s.token}` } : {}),
    },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })
  if (res.status === 401 && s) {
    clearSession()
    window.location.href = '/login'
    return
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorMessage(data?.detail) || `Request failed (${res.status})`)
  return data
}

export const STATE_LABEL = { normal: 'Normal', attention_needed: 'Attention Needed', high_support_need: 'High Support Need', not_assessed: 'Not assessed' }
export const CATEGORY_LABEL = { positive: 'Positive', partial: 'Partial', no_improvement: 'No Improvement' }
export const INTERVENTION_LABEL = {
  targeted_material: 'Targeted Learning Material',
  targeted_practice: 'Targeted Practice Questions',
  study_plan: 'Personalized Study Plan',
  faculty_support: 'Faculty Support',
}
export const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const fmtDateTime = (s) => (s ? new Date(s).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—')
export const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v)}%`)

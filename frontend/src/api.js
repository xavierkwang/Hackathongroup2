import { authHeaders } from './auth'

const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(data.error || data.message || res.statusText, res.status)
  return data
}

const SLACK_TEAM = import.meta.env.VITE_SLACK_TEAM_ID

export function slackLink(person) {
  if (!person.slackUserId) return null
  return SLACK_TEAM
    ? `https://app.slack.com/client/${SLACK_TEAM}/${person.slackUserId}`
    : `https://slack.com/app_redirect?channel=${person.slackUserId}`
}

export function fmtDate(iso) {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-SG', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function fmtRange(start, end, portion = 'full') {
  const half = portion === 'am' ? ' (AM)' : portion === 'pm' ? ' (PM)' : ''
  return start === end ? fmtDate(start) + half : `${fmtDate(start)} → ${fmtDate(end)}`
}

export function initials(name = '') {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
}

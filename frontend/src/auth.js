// Two auth modes:
//  - local:   pick a seeded demo user (sent as X-Demo-User). Per browser tab, so two
//             windows can be two different people for the live demo.
//  - cognito: Cognito Hosted UI, authorization-code + PKCE. Federate your corporate
//             SSO (SAML / OIDC) into the user pool and this code doesn't change.

const env = import.meta.env
export const AUTH_MODE = env.VITE_AUTH_MODE || 'local'
const DOMAIN = (env.VITE_COGNITO_DOMAIN || '').replace(/\/$/, '')
const CLIENT_ID = env.VITE_COGNITO_CLIENT_ID || ''
const REDIRECT = window.location.origin + '/'
const TOKEN_KEY = 'beacon.idToken'
const DEMO_KEY = 'beacon.demoUser'
export const DEFAULT_DEMO_USER = 'aisha.rahman@example.com'

export function getDemoUser() {
  try {
    return sessionStorage.getItem(DEMO_KEY) || DEFAULT_DEMO_USER
  } catch {
    return DEFAULT_DEMO_USER
  }
}

export function setDemoUser(email) {
  try { sessionStorage.setItem(DEMO_KEY, email) } catch { /* private mode */ }
}

export function authHeaders() {
  if (AUTH_MODE === 'local') return { 'X-Demo-User': getDemoUser() }
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function getToken() {
  try {
    const raw = sessionStorage.getItem(TOKEN_KEY)
    if (!raw) return null
    const { token, exp } = JSON.parse(raw)
    return Date.now() < exp ? token : null
  } catch {
    return null
  }
}

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

export async function login() {
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(48)))
  const challenge = b64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)))
  const state = b64url(crypto.getRandomValues(new Uint8Array(16)))
  sessionStorage.setItem('beacon.pkce', JSON.stringify({ verifier, state }))
  const params = new URLSearchParams({
    response_type: 'code', client_id: CLIENT_ID, redirect_uri: REDIRECT,
    scope: 'openid email profile', code_challenge_method: 'S256', code_challenge: challenge, state,
  })
  window.location.assign(`${DOMAIN}/oauth2/authorize?${params}`)
}

/** Call once on load. Exchanges ?code=… for tokens if we just came back from the Hosted UI. */
export async function handleRedirect() {
  if (AUTH_MODE !== 'cognito') return
  const url = new URL(window.location.href)
  const code = url.searchParams.get('code')
  if (!code) return
  const saved = JSON.parse(sessionStorage.getItem('beacon.pkce') || '{}')
  window.history.replaceState({}, '', '/')
  if (!saved.verifier || saved.state !== url.searchParams.get('state')) return
  const res = await fetch(`${DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code', client_id: CLIENT_ID, code,
      redirect_uri: REDIRECT, code_verifier: saved.verifier,
    }),
  })
  sessionStorage.removeItem('beacon.pkce')
  if (!res.ok) return
  const data = await res.json()
  sessionStorage.setItem(TOKEN_KEY, JSON.stringify({
    token: data.id_token, exp: Date.now() + (data.expires_in - 60) * 1000,
  }))
}

export function logout() {
  sessionStorage.removeItem(TOKEN_KEY)
  if (AUTH_MODE === 'cognito') {
    const params = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: REDIRECT })
    window.location.assign(`${DOMAIN}/logout?${params}`)
  }
}

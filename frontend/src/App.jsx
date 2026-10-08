import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { AUTH_MODE, getDemoUser, getToken, login, logout, setDemoUser } from './auth'
import ChatSearch from './components/ChatSearch'
import FloorPlan from './components/FloorPlan'
import LeavePage from './components/LeavePage'
import TeamLeave from './components/TeamLeave'
import Admin from './components/Admin'
import Directory from './components/Directory'

const TABS = [
  { id: 'ask', label: 'Ask Beacon' },
  { id: 'directory', label: 'Directory' },
  { id: 'leave', label: 'My leave' },
  { id: 'team', label: 'Team leave', roles: ['lead', 'hr', 'admin'] },
  { id: 'admin', label: 'Admin', roles: ['admin'] },
]

export default function App() {
  const [me, setMe] = useState(null)
  const [authError, setAuthError] = useState(null)
  const [people, setPeople] = useState([])
  const [floors, setFloors] = useState([])
  const [tab, setTab] = useState('ask')
  const [selectedId, setSelectedId] = useState(null)
  const [demoUser, setDemo] = useState(getDemoUser())

  const refreshPeople = useCallback(async () => {
    try {
      const data = await api('/api/people')
      setPeople(data.people)
    } catch { /* shown elsewhere */ }
  }, [])

  useEffect(() => {
    fetch('/floors.json').then((r) => r.json()).then((d) => setFloors(d.floors)).catch(() => setFloors([]))
  }, [])

  useEffect(() => {
    if (AUTH_MODE === 'cognito' && !getToken()) {
      setAuthError('signin')
      return
    }
    setMe(null)
    api('/api/me')
      .then((m) => { setMe(m); setAuthError(null) })
      .catch((e) => setAuthError(e.status === 401 ? 'signin' : e.message))
    refreshPeople()
    const t = setInterval(refreshPeople, 30000)
    return () => clearInterval(t)
  }, [demoUser, refreshPeople])

  if (authError === 'signin' && AUTH_MODE === 'cognito') {
    return (
      <div className="signin">
        <div className="signin-card">
          <img src="/beacon.svg" alt="" width="56" height="56" />
          <h1>WOW Beacon</h1>
          <p>Find who owns what, where they sit, and whether they're in.</p>
          <button className="btn primary" onClick={login}>Sign in with company SSO</button>
        </div>
      </div>
    )
  }

  const roles = me?.roles || []
  const visibleTabs = TABS.filter((t) => !t.roles || t.roles.some((r) => roles.includes(r)))
  const selected = people.find((c) => c.person.id === selectedId)

  const switchDemo = (email) => {
    setDemoUser(email)
    setDemo(email)
    setTab('ask')
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/beacon.svg" alt="" width="30" height="30" />
          <div>
            <div className="brand-name">WOW Beacon</div>
            <div className="brand-tag">Who owns what · People finder</div>
          </div>
        </div>
        <nav className="tabs" aria-label="Sections">
          {visibleTabs.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="who">
          {AUTH_MODE === 'local' ? (
            <label className="demo-picker">
              <span>Demo as</span>
              <select value={demoUser} onChange={(e) => switchDemo(e.target.value)}>
                {(people.length ? people.map((c) => c.person) : [{ email: demoUser, name: demoUser }]).map((p) => (
                  <option key={p.email} value={p.email}>{p.name}{p.email === demoUser && roles.length ? ` (${roles.join(', ')})` : ''}</option>
                ))}
              </select>
            </label>
          ) : (
            <>
              <span className="me-name">{me?.person?.name || me?.email}</span>
              {roles.map((r) => <span key={r} className="role-pill">{r}</span>)}
              <button className="btn ghost small" onClick={logout}>Sign out</button>
            </>
          )}
        </div>
      </header>

      {authError && authError !== 'signin' && <div className="banner error">{authError}</div>}
      {me && !me.person && (
        <div className="banner">Your email ({me.email}) isn't in the directory yet. Search works, but ask an admin to add you before entering leave.</div>
      )}

      <main className="main">
        {/* Kept mounted so the conversation survives switching tabs */}
        <div className="ask-layout" hidden={tab !== 'ask'}>
          <ChatSearch key={demoUser} selectedId={selectedId} onSelect={setSelectedId} />
          <aside className="map-panel">
            <FloorPlan floors={floors} people={people} selected={selected} onSelect={setSelectedId} />
          </aside>
        </div>
        {tab === 'directory' && (
          <Directory people={people} onShow={(id) => { setSelectedId(id); setTab('ask') }} />
        )}
        {tab === 'leave' && <LeavePage me={me} onSaved={refreshPeople} />}
        {tab === 'team' && <TeamLeave me={me} onSaved={refreshPeople} />}
        {tab === 'admin' && <Admin onSaved={refreshPeople} />}
      </main>
    </div>
  )
}

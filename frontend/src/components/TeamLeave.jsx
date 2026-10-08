import { useEffect, useMemo, useState } from 'react'
import { api, fmtRange } from '../api'
import LeaveComposer from './LeaveComposer'

export default function TeamLeave({ me, onSaved }) {
  const roles = me?.roles || []
  const isHr = roles.includes('hr') || roles.includes('admin')
  const [teams, setTeams] = useState([])
  const [team, setTeam] = useState(me?.person?.team || '')
  const [mode, setMode] = useState('team')
  const [picked, setPicked] = useState(new Set())
  const [result, setResult] = useState(null)

  useEffect(() => {
    api('/api/teams').then((r) => setTeams(r.teams)).catch(() => setTeams([]))
  }, [])

  const allowed = useMemo(
    () => (isHr ? teams : teams.filter((t) => t.team === me?.person?.team)),
    [teams, isHr, me],
  )
  useEffect(() => {
    if (!allowed.find((t) => t.team === team) && allowed[0]) setTeam(allowed[0].team)
  }, [allowed, team])

  const members = allowed.find((t) => t.team === team)?.members || []
  const toggle = (id) => setPicked((s) => {
    const n = new Set(s)
    n.has(id) ? n.delete(id) : n.add(id)
    return n
  })

  async function save(draft) {
    const body = mode === 'team' ? { team, ...draft } : { personIds: [...picked], ...draft }
    const res = await api('/api/leave/team', { method: 'POST', body })
    setResult({ ...res, range: fmtRange(draft.start, draft.end, draft.portion) })
    setPicked(new Set())
    onSaved?.()
  }

  const nameOf = (id) => members.find((m) => m.id === id)?.name || id

  return (
    <div className="page">
      <section className="panel">
        <h2>Update leave for your team</h2>
        <p className="muted">
          {isHr ? 'As HR you can update any team.' : `As a lead you can update ${me?.person?.team}.`} Changes show on everyone's cards straight away.
        </p>

        <div className="row">
          <label className="field">Team
            <select value={team} onChange={(e) => { setTeam(e.target.value); setPicked(new Set()) }} disabled={!isHr}>
              {allowed.map((t) => <option key={t.team} value={t.team}>{t.team} ({t.members.length})</option>)}
            </select>
          </label>
          <div className="segmented" role="radiogroup" aria-label="Who">
            <button role="radio" aria-checked={mode === 'team'} className={mode === 'team' ? 'on' : ''} onClick={() => setMode('team')}>Whole team</button>
            <button role="radio" aria-checked={mode === 'people'} className={mode === 'people' ? 'on' : ''} onClick={() => setMode('people')}>Choose people</button>
          </div>
        </div>

        {mode === 'people' && (
          <div className="pick-grid">
            {members.map((m) => (
              <label key={m.id} className={`pick ${picked.has(m.id) ? 'on' : ''}`}>
                <input type="checkbox" checked={picked.has(m.id)} onChange={() => toggle(m.id)} /> {m.name}
              </label>
            ))}
          </div>
        )}

        <LeaveComposer
          onConfirm={save}
          disabled={mode === 'people' && picked.size === 0}
          confirmLabel={mode === 'team' ? `Mark all of ${team} on leave` : `Mark ${picked.size} on leave`}
        />

        {result && (
          <div className="banner ok" role="status">
            {result.created.length} marked on leave for {result.range}.
            {result.skipped.length > 0 && ` Skipped ${result.skipped.map((s) => s.name || nameOf(s.id)).join(', ')} (already on leave).`}
          </div>
        )}
      </section>
    </div>
  )
}

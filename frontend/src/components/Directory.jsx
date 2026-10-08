import { useMemo, useState } from 'react'
import { slackLink } from '../api'
import { Badge } from './PersonCard'

const STATUS_LABEL = { available: 'Available', busy: 'In a meeting', on_leave: 'On leave', weekend: 'Weekend' }

export default function Directory({ people, onShow }) {
  const [q, setQ] = useState('')
  const [team, setTeam] = useState('')
  const [project, setProject] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState({ key: 'name', dir: 1 })

  const teams = useMemo(() => [...new Set(people.map((c) => c.person.team).filter(Boolean))].sort(), [people])
  const projects = useMemo(() => [...new Set(people.flatMap((c) => c.person.projects || []))].sort(), [people])

  const counts = useMemo(() => {
    const c = {}
    for (const p of people) c[p.availability?.status] = (c[p.availability?.status] || 0) + 1
    return c
  }, [people])

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const val = (c, key) => {
      const p = c.person
      if (key === 'status') return c.availability?.status || ''
      if (key === 'projects') return (p.projects || []).join(', ')
      return String(p[key] || '')
    }
    return people
      .filter((c) => {
        const p = c.person
        if (team && p.team !== team) return false
        if (project && !(p.projects || []).includes(project)) return false
        if (status && c.availability?.status !== status) return false
        if (!needle) return true
        return [p.name, p.role, p.team, p.desk, p.zone, p.floor, p.email, ...(p.projects || []), ...(p.skills || [])]
          .join(' ').toLowerCase().includes(needle)
      })
      .sort((a, b) => val(a, sort.key).localeCompare(val(b, sort.key)) * sort.dir)
  }, [people, q, team, project, status, sort])

  const th = (key, label) => (
    <th>
      <button className="th-btn" onClick={() => setSort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }))}>
        {label} {sort.key === key ? (sort.dir === 1 ? '▲' : '▼') : ''}
      </button>
    </th>
  )

  function exportCsv() {
    const cols = ['name', 'role', 'team', 'projects', 'owns', 'floor', 'desk', 'zone', 'email', 'slackHandle', 'status']
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
    const lines = rows.map((c) => cols.map((k) => {
      if (k === 'status') return esc(c.availability?.label)
      const v = c.person[k]
      return esc(Array.isArray(v) ? v.join('; ') : v)
    }).join(','))
    const blob = new Blob([[cols.join(','), ...lines].join('\n')], { type: 'text/csv' })
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'beacon-directory.csv' })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="directory">
      <div className="dir-head">
        <div>
          <h2>Directory</h2>
          <p className="muted">
            {people.length} people · <span className="ok-text">{counts.available || 0} available</span> ·{' '}
            <span className="warn-text">{counts.busy || 0} in a meeting</span> ·{' '}
            <span className="bad-text">{counts.on_leave || 0} on leave</span>
          </p>
        </div>
        <button className="btn small" onClick={exportCsv} disabled={!rows.length}>⬇️ Export CSV</button>
      </div>

      <div className="dir-filters">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by name, role, skill, desk…" aria-label="Filter" />
        <select value={team} onChange={(e) => setTeam(e.target.value)} aria-label="Team">
          <option value="">All teams</option>
          {teams.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project">
          <option value="">All projects</option>
          {projects.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Availability">
          <option value="">Any availability</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table className="dir-table">
          <thead>
            <tr>
              {th('name', 'Name')}
              {th('role', 'Role')}
              {th('team', 'Team')}
              {th('projects', 'Projects')}
              {th('floor', 'Floor')}
              {th('desk', 'Desk')}
              {th('zone', 'Zone')}
              {th('status', 'Availability')}
              <th>Contact</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const p = c.person
              const slack = slackLink(p)
              return (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong></td>
                  <td>{p.role}</td>
                  <td>{p.team}</td>
                  <td>
                    {(p.projects || []).map((proj) => (
                      <span key={proj} className={`chip ${(p.owns || []).includes(proj) ? 'owner' : ''}`}>
                        {proj}{(p.owns || []).includes(proj) ? ' · owner' : ''}
                      </span>
                    ))}
                  </td>
                  <td>{p.floor}</td>
                  <td>
                    <button className="link-btn" onClick={() => onShow(p.id)} title="Show on floor plan">📍 {p.desk}</button>
                  </td>
                  <td>{p.zone}</td>
                  <td><Badge availability={c.availability} /></td>
                  <td className="nowrap">
                    {slack && <a href={slack} target="_blank" rel="noreferrer" title={`Slack ${p.slackHandle}`}>💬</a>}{' '}
                    {p.email && <a href={`mailto:${p.email}`} title={p.email}>✉️</a>}
                  </td>
                </tr>
              )
            })}
            {!rows.length && (
              <tr><td colSpan={9} className="muted center">No one matches those filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

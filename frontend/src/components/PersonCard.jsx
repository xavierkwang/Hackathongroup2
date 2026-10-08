import { fmtDate, fmtRange, initials, slackLink } from '../api'

export function Badge({ availability }) {
  if (!availability) return null
  return (
    <span className={`badge ${availability.status}`}>
      <span aria-hidden="true">{availability.emoji}</span> {availability.label}
    </span>
  )
}

export default function PersonCard({ card, selected, onSelect, compact = false }) {
  const { person: p, availability: a } = card
  const slack = slackLink(p)
  return (
    <article
      className={`card ${selected ? 'selected' : ''} ${a?.status || ''}`}
      onClick={() => onSelect?.(p.id)}
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' ? onSelect?.(p.id) : null)}
      aria-label={`${p.name}, ${p.role}`}
    >
      <div className="card-head">
        <div className="avatar" aria-hidden="true">{initials(p.name)}</div>
        <div className="card-title">
          <div className="name">{p.name}</div>
          <div className="role">{p.role} · {p.team}</div>
        </div>
        <Badge availability={a} />
      </div>

      <div className="chips">
        {(p.projects || []).map((proj) => (
          <span key={proj} className={`chip ${(p.owns || []).includes(proj) ? 'owner' : ''}`}>
            {proj}{(p.owns || []).includes(proj) ? ' · owner' : ''}
          </span>
        ))}
      </div>

      <dl className="facts">
        <div><dt>Floor</dt><dd>{p.floor || '—'}</dd></div>
        <div><dt>Desk</dt><dd>{p.desk || '—'}</dd></div>
        <div><dt>Zone</dt><dd>{p.zone || '—'}</dd></div>
      </dl>

      {a?.note && <div className="note">🗓️ {a.note}</div>}
      {!compact && a?.upcoming?.length > 0 && a.status !== 'on_leave' && !a.note && (
        <div className="note">🗓️ Next leave {fmtRange(a.upcoming[0].start, a.upcoming[0].end, a.upcoming[0].portion)}</div>
      )}
      {a?.status === 'on_leave' && a.upcoming?.length > 0 && (
        <div className="note">Also away {fmtDate(a.upcoming[0].start)}</div>
      )}

      <div className="actions" onClick={(e) => e.stopPropagation()}>
        {slack && (
          <a className="btn small" href={slack} target="_blank" rel="noreferrer">
            💬 Slack {p.slackHandle}
          </a>
        )}
        {p.email && <a className="btn small ghost" href={`mailto:${p.email}`}>✉️ Email</a>}
        <button className="btn small ghost" onClick={() => onSelect?.(p.id)}>📍 Show desk</button>
      </div>
    </article>
  )
}

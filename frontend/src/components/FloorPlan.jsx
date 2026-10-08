import { useEffect, useMemo, useState } from 'react'
import { Badge } from './PersonCard'

const DESK_W = 52
const DESK_H = 34
const STATUS_COLOR = { available: 'var(--ok)', busy: 'var(--warn)', on_leave: 'var(--bad)', weekend: 'var(--muted)' }

export default function FloorPlan({ floors, people, selected, onSelect }) {
  const [floorId, setFloorId] = useState(null)
  const [hover, setHover] = useState(null)

  const target = selected?.person
  useEffect(() => {
    if (target?.floor) setFloorId(target.floor)
  }, [target?.id, target?.floor])

  const floor = floors.find((f) => f.id === floorId) || floors[0]
  const byDesk = useMemo(() => {
    const m = {}
    for (const c of people) if (c.person.desk) m[`${c.person.floor}/${c.person.desk}`] = c
    return m
  }, [people])

  if (!floor) return <div className="floor-empty">Loading floor plans…</div>

  const pinDesk = target && target.floor === floor.id ? floor.desks.find((d) => d.id === target.desk) : null
  const hoverCard = hover ? byDesk[`${floor.id}/${hover}`] : null

  return (
    <div className="floorplan">
      <div className="floor-head">
        <div className="floor-tabs" role="tablist">
          {floors.map((f) => (
            <button key={f.id} role="tab" aria-selected={f.id === floor.id}
              className={`tab small ${f.id === floor.id ? 'active' : ''}`} onClick={() => setFloorId(f.id)}>
              {f.name}
            </button>
          ))}
        </div>
        {target ? (
          <div className="floor-target">
            <strong>{target.name}</strong> · {target.floor} · Desk {target.desk} · {target.zone}
          </div>
        ) : (
          <div className="floor-target muted">Ask a question or click a desk</div>
        )}
      </div>

      <svg viewBox={`0 0 ${floor.width} ${floor.height}`} className="floor-svg" role="img"
        aria-label={`${floor.name} floor plan${pinDesk ? `, ${target.name} at desk ${target.desk}` : ''}`}>
        <rect x="10" y="10" width={floor.width - 20} height={floor.height - 20} rx="18" className="floor-outline" />
        {floor.zones.map((z) => {
          const hot = target && target.floor === floor.id && target.zone === z.id
          return (
            <g key={z.id}>
              <rect x={z.x} y={z.y} width={z.w} height={z.h} rx="12"
                fill={z.color} fillOpacity={hot ? 0.22 : z.amenity ? 0.05 : 0.09}
                stroke={z.color} strokeOpacity={hot ? 1 : 0.35} strokeWidth={hot ? 3 : 1.5}
                strokeDasharray={z.amenity ? '6 6' : undefined} className={hot ? 'zone-hot' : ''} />
              <text x={z.x + 14} y={z.y + z.h - 14} className="zone-label" fill={z.color}>{z.id}</text>
            </g>
          )
        })}
        {floor.desks.map((d) => {
          const occ = byDesk[`${floor.id}/${d.id}`]
          const isPin = pinDesk?.id === d.id
          return (
            <g key={d.id} className={`desk ${occ ? 'occupied' : ''} ${isPin ? 'pinned' : ''}`}
              onMouseEnter={() => setHover(d.id)} onMouseLeave={() => setHover(null)}
              onClick={() => occ && onSelect(occ.person.id)} style={{ cursor: occ ? 'pointer' : 'default' }}>
              <rect x={d.x - DESK_W / 2} y={d.y - DESK_H / 2} width={DESK_W} height={DESK_H} rx="6" />
              <text x={d.x} y={d.y + 4} textAnchor="middle" className="desk-label">{d.id.split('-').slice(1).join('-')}</text>
              {occ && <circle cx={d.x + DESK_W / 2 - 6} cy={d.y - DESK_H / 2 + 6} r="5"
                fill={STATUS_COLOR[occ.availability?.status] || 'var(--muted)'} stroke="var(--surface)" strokeWidth="1.5" />}
            </g>
          )
        })}
        {pinDesk && (
          <g className="pin" transform={`translate(${pinDesk.x}, ${pinDesk.y - DESK_H / 2})`}>
            <circle r="26" cy="0" className="pin-pulse" />
            <path d="M0 0 C-14 -18 -16 -26 -16 -32 A16 16 0 1 1 16 -32 C16 -26 14 -18 0 0Z" className="pin-body" />
            <circle cy="-32" r="6" fill="#fff" />
          </g>
        )}
      </svg>

      <div className="floor-foot">
        {hoverCard ? (
          <span><strong>{hoverCard.person.name}</strong> · {hoverCard.person.role} <Badge availability={hoverCard.availability} /></span>
        ) : (
          <span className="legend">
            <i style={{ background: 'var(--ok)' }} /> Available
            <i style={{ background: 'var(--warn)' }} /> In a meeting
            <i style={{ background: 'var(--bad)' }} /> On leave
          </span>
        )}
      </div>
    </div>
  )
}

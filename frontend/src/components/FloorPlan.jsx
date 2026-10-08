import { useEffect, useMemo, useState } from 'react'
import { Badge } from './PersonCard'

const DESK_W = 52
const DESK_H = 34
const STATUS_COLOR = { available: 'var(--ok)', busy: 'var(--warn)', on_leave: 'var(--bad)', weekend: 'var(--muted)' }

export default function FloorPlan({ floors, people, selected, onSelect, rooms = [], selectedRoom, onSelectRoom, initialFloor = null }) {
  const [floorId, setFloorId] = useState(initialFloor)
  const [hover, setHover] = useState(null)

  const target = selected?.person
  useEffect(() => {
    if (target?.floor) setFloorId(target.floor)
  }, [target?.id, target?.floor])
  useEffect(() => {
    if (selectedRoom?.floor) setFloorId(selectedRoom.floor)
  }, [selectedRoom?.id, selectedRoom?.floor])
  const roomsById = useMemo(() => Object.fromEntries(rooms.map((r) => [r.id, r])), [rooms])

  const floor = floors.find((f) => f.id === floorId) || floors[0]
  const byDesk = useMemo(() => {
    const m = {}
    for (const c of people) if (c.person.desk) m[`${c.person.floor}/${c.person.desk}`] = c
    return m
  }, [people])

  if (!floor) return <div className="floor-empty">Loading floor plans…</div>

  const pinDesk = !selectedRoom && target && target.floor === floor.id ? floor.desks.find((d) => d.id === target.desk) : null
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
        {selectedRoom ? (
          <div className="floor-target">
            <strong>{selectedRoom.name}</strong> · {selectedRoom.floor} · {selectedRoom.capacity} seats · {selectedRoom.label}
          </div>
        ) : target ? (
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
          if (z.type === 'room') {
            const room = roomsById[z.roomId]
            const hot = selectedRoom?.id === z.roomId
            const color = room?.status === 'occupied' ? 'var(--bad)' : room?.status === 'free' ? 'var(--ok)' : z.color
            return (
              <g key={z.id} className="room-zone" onClick={() => onSelectRoom?.(z.roomId)}
                style={{ cursor: onSelectRoom ? 'pointer' : 'default' }}>
                <rect x={z.x} y={z.y} width={z.w} height={z.h} rx="12"
                  fill={color} fillOpacity={hot ? 0.24 : 0.12} stroke={color}
                  strokeOpacity={hot ? 1 : 0.6} strokeWidth={hot ? 4 : 2} className={hot ? 'zone-hot' : ''} />
                <foreignObject x={z.x + 10} y={z.y + 10} width={z.w - 20} height={z.h - 20}>
                  <div xmlns="http://www.w3.org/1999/xhtml" className="room-label">
                    <div className="room-name">🚪 {z.id}</div>
                    {room && <div className="room-meta">{room.capacity} seats</div>}
                    {room && <div className="room-status" style={{ color }}>{room.label}</div>}
                    {room?.current && <div className="room-meta">“{room.current.title}”</div>}
                  </div>
                </foreignObject>
              </g>
            )
          }
          const hot = !selectedRoom && target && target.floor === floor.id && target.zone === z.id
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
        ) : floor.zones.some((z) => z.type === 'room') ? (
          <span className="legend">
            <i style={{ background: 'var(--ok)' }} /> Room free
            <i style={{ background: 'var(--bad)' }} /> Room booked now
            {onSelectRoom && <span className="muted">· click a room for details</span>}
          </span>
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

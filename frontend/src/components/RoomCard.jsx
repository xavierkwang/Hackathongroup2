export function RoomBadge({ room }) {
  const cls = room.status === 'occupied' ? 'on_leave' : room.status === 'free' ? 'available' : 'weekend'
  const emoji = room.status === 'occupied' ? '🔴' : room.status === 'free' ? '🟢' : '📅'
  return <span className={`badge ${cls}`}>{emoji} {room.label}</span>
}

function Booking({ b, now }) {
  return (
    <li className={now ? 'now' : ''}>
      <span className="b-time">{b.start}–{b.end}</span>
      <span className="b-title">{b.title}</span>
      <span className="b-who">{b.bookedBy.name}{b.attendees.length ? ` +${b.attendees.length}` : ''}</span>
    </li>
  )
}

export default function RoomCard({ room, selected, onSelect }) {
  return (
    <article className={`card room-card ${selected ? 'selected' : ''} ${room.status}`}
      onClick={() => onSelect?.(room.id)} tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' ? onSelect?.(room.id) : null)} aria-label={`${room.name} meeting room`}>
      <div className="card-head">
        <div className="avatar room-avatar" aria-hidden="true">🚪</div>
        <div className="card-title">
          <div className="name">{room.name}</div>
          <div className="role">{room.floor} · {room.capacity} seats · {room.equipment.join(', ')}</div>
        </div>
        <RoomBadge room={room} />
      </div>
      {room.bookings.length > 0 ? (
        <ul className="booking-list">
          {room.bookings.map((b) => <Booking key={b.id} b={b} now={room.current?.id === b.id} />)}
        </ul>
      ) : (
        <p className="muted small">No bookings today.</p>
      )}
    </article>
  )
}

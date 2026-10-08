import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import FloorPlan from './FloorPlan'
import { RoomBadge } from './RoomCard'

const DAY_START = 8 * 60 // 08:00
const DAY_END = 19 * 60 // 19:00
const HOURS = Array.from({ length: (DAY_END - DAY_START) / 60 + 1 }, (_, i) => DAY_START / 60 + i)

const toMin = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m }
const pct = (min) => `${((Math.min(Math.max(min, DAY_START), DAY_END) - DAY_START) / (DAY_END - DAY_START)) * 100}%`
const iso = (d) => d.toISOString().slice(0, 10)
const addDays = (isoDate, n) => { const d = new Date(isoDate + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return iso(d) }

export default function RoomsPage({ floors, people }) {
  const [date, setDate] = useState(null) // null = today (server's clock)
  const [data, setData] = useState(null)
  const [selectedRoomId, setSelectedRoomId] = useState('st-john')
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const res = await api(`/api/rooms${date ? `?date=${date}` : ''}`)
      setData(res)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [date])

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])

  if (error) return <div className="banner error">{error}</div>
  if (!data) return <div className="muted">Loading rooms…</div>

  const today = data.now.slice(0, 10)
  const isToday = data.date === today
  const nowMin = isToday ? Number(data.now.slice(11, 13)) * 60 + Number(data.now.slice(14, 16)) : null
  const dayLabel = new Date(data.date + 'T00:00:00').toLocaleDateString('en-SG', { weekday: 'long', day: 'numeric', month: 'short' })
  const selectedRoom = data.rooms.find((r) => r.id === selectedRoomId)
  const free = data.rooms.filter((r) => r.status === 'free').length

  return (
    <div className="rooms-layout">
      <section className="panel rooms-panel">
        <div className="dir-head">
          <div>
            <h2>Meeting rooms · Level 9</h2>
            <p className="muted">
              {dayLabel}{isToday ? ` · ${free} of ${data.rooms.length} free now` : ''}
            </p>
          </div>
          <div className="day-nav">
            <button className="btn small ghost" onClick={() => setDate(addDays(data.date, -1))} aria-label="Previous day">◀</button>
            <button className="btn small" onClick={() => setDate(null)} disabled={isToday}>Today</button>
            <button className="btn small ghost" onClick={() => setDate(addDays(data.date, 1))} aria-label="Next day">▶</button>
          </div>
        </div>

        <div className="timeline" role="table" aria-label="Room bookings timeline">
          <div className="tl-row tl-hours" role="row">
            <div className="tl-room" />
            <div className="tl-track">
              {HOURS.map((h) => (
                <span key={h} className="tl-hour" style={{ left: pct(h * 60) }}>{h <= 12 ? h : h - 12}{h < 12 ? 'am' : 'pm'}</span>
              ))}
            </div>
          </div>
          {data.rooms.map((room) => (
            <div key={room.id} role="row" className={`tl-row ${room.id === selectedRoomId ? 'selected' : ''}`}>
              <button className="tl-room" onClick={() => { setSelectedRoomId(room.id); setBooking(null) }}>
                <strong>{room.name}</strong>
                <span className="muted small">{room.capacity} seats</span>
                {isToday && <span className={`dot ${room.status}`} aria-label={room.status} />}
              </button>
              <div className="tl-track">
                {HOURS.map((h) => <span key={h} className="tl-grid" style={{ left: pct(h * 60) }} />)}
                {room.bookings.map((b) => {
                  const live = isToday && nowMin >= toMin(b.start) && nowMin < toMin(b.end)
                  const past = isToday && nowMin >= toMin(b.end)
                  return (
                    <button key={b.id}
                      className={`tl-booking ${toMin(b.end) - toMin(b.start) <= 30 ? 'short' : ''} ${live ? 'live' : ''} ${past ? 'past' : ''} ${booking?.id === b.id ? 'active' : ''}`}
                      style={{ left: pct(toMin(b.start)), width: `calc(${pct(toMin(b.end))} - ${pct(toMin(b.start))})` }}
                      onClick={() => { setSelectedRoomId(room.id); setBooking(b) }}
                      title={`${b.start}–${b.end} · ${b.title} · ${b.bookedBy.name}`}>
                      <span className="tl-b-title">{b.title}</span>
                      <span className="tl-b-who">{b.bookedBy.name}</span>
                    </button>
                  )
                })}
                {isToday && nowMin >= DAY_START && nowMin <= DAY_END && (
                  <span className="tl-now" style={{ left: pct(nowMin) }} aria-hidden="true" />
                )}
              </div>
            </div>
          ))}
        </div>

        {booking ? (
          <div className="booking-detail">
            <div className="preview-head">
              <div>
                <div className="preview-title">{booking.title}</div>
                <div className="muted">
                  {data.rooms.find((r) => r.id === booking.room)?.name} · {booking.start}–{booking.end}
                </div>
              </div>
              <button className="btn small ghost" onClick={() => setBooking(null)}>Close</button>
            </div>
            <p><strong>Booked by</strong> {booking.bookedBy.name}{booking.bookedBy.team ? ` (${booking.bookedBy.team})` : ''}</p>
            {booking.attendees.length > 0 && (
              <p><strong>Attendees</strong> {booking.attendees.map((a) => a.name).join(', ')}</p>
            )}
          </div>
        ) : selectedRoom && (
          <div className="booking-detail">
            <div className="preview-head">
              <div>
                <div className="preview-title">{selectedRoom.name}</div>
                <div className="muted">{selectedRoom.floor} · {selectedRoom.capacity} seats · {selectedRoom.equipment.join(', ')}</div>
              </div>
              <RoomBadge room={selectedRoom} />
            </div>
            <p className="muted small">Click a booking on the timeline to see who booked it and who's attending.</p>
          </div>
        )}
      </section>

      <aside className="map-panel">
        <FloorPlan floors={floors} people={people} rooms={data.rooms} selectedRoom={selectedRoom}
          onSelect={() => {}} onSelectRoom={(id) => { setSelectedRoomId(id); setBooking(null) }} initialFloor="L9" />
      </aside>
    </div>
  )
}

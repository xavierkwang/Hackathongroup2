import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import PersonCard from './PersonCard'
import RoomCard from './RoomCard'

const SUGGESTIONS = ['FE dev for ACE', 'Who owns Pathfinder?', 'Who booked St John?', 'Any free meeting room?', 'Where does Priya sit?']

const WELCOME = {
  role: 'bot',
  text: "Hi! Ask me who to talk to about a project, a role or a team. I'll tell you who it is, where they sit, and whether they're in today.",
}

export default function ChatSearch({ selectedId, onSelect, selectedRoomId, onSelectRoom }) {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages])

  async function ask(query) {
    const q = query.trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const res = await api('/api/search', { method: 'POST', body: { query: q } })
      setMessages((m) => [...m, { role: 'bot', text: res.answer, results: res.results, rooms: res.rooms, source: res.source, ms: res.ms }])
      if (res.rooms?.length) onSelectRoom?.(res.rooms[0].id)
      else if (res.results[0]) onSelect(res.results[0].person.id)
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', text: `Sorry, that didn't work: ${e.message}`, error: true }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="chat" aria-label="Ask Beacon">
      <div className="chat-log" role="log" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.error ? 'error' : ''}`}>
            {m.role === 'bot' && <div className="bot-dot" aria-hidden="true" />}
            <div className="msg-body">
              <p>{m.text}</p>
              {m.rooms?.length > 0 && (
                <div className="results">
                  {m.rooms.map((r) => (
                    <RoomCard key={r.id} room={r} selected={r.id === selectedRoomId} onSelect={onSelectRoom} />
                  ))}
                </div>
              )}
              {m.results?.length > 0 && <Results results={m.results} selectedId={selectedId} onSelect={onSelect} />}
              {m.source && (
                <div className="meta">
                  {m.source === 'ai' ? '✨ Understood by AI' : m.source === 'rooms' ? '🚪 Room bookings' : '⚡ Keyword match'} · {m.ms} ms
                </div>
              )}
              {i === 0 && (
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} className="chip-btn" onClick={() => ask(s)} disabled={busy}>{s}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="msg bot"><div className="bot-dot" /><div className="msg-body typing"><span /><span /><span /></div></div>}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder='e.g. "who developed MCC?" or "is Kusu free?"'
          aria-label="Ask Beacon"
          maxLength={300}
          autoFocus
        />
        <button className="btn primary" disabled={busy || !input.trim()}>Ask</button>
      </form>
    </section>
  )
}

function Results({ results, selectedId, onSelect }) {
  const [showAll, setShowAll] = useState(false)
  const shown = showAll ? results : results.slice(0, 2)
  return (
    <div className="results">
      {shown.map((r) => (
        <PersonCard key={r.person.id} card={r} selected={r.person.id === selectedId} onSelect={onSelect} />
      ))}
      {results.length > 2 && (
        <button className="link-btn" onClick={() => setShowAll((s) => !s)}>
          {showAll ? 'Show fewer' : `Show ${results.length - 2} more`}
        </button>
      )}
    </div>
  )
}

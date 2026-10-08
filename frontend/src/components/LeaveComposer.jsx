import { useState } from 'react'
import { api, fmtRange } from '../api'

const EXAMPLES = ['MC today', 'off 21 to 25 Oct', 'half day tomorrow afternoon', 'leave next Friday']

function workingDays(start, end) {
  if (!start || !end || end < start) return 0
  let n = 0
  for (let d = new Date(start + 'T00:00:00'); d <= new Date(end + 'T00:00:00'); d.setDate(d.getDate() + 1)) {
    if (d.getDay() !== 0 && d.getDay() !== 6) n++
  }
  return n
}

/**
 * Type leave in plain language → see a preview → confirm.
 * The AI (or date parser) only fills in the preview; nothing is saved until Confirm.
 */
export default function LeaveComposer({ onConfirm, confirmLabel = 'Confirm leave', disabled }) {
  const [text, setText] = useState('')
  const [draft, setDraft] = useState(null) // {start, end, portion, source}
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  async function understand(t = text) {
    if (!t.trim()) return
    setText(t)
    setBusy(true)
    setMessage(null)
    try {
      const res = await api('/api/leave/parse', { method: 'POST', body: { text: t } })
      if (res.ok) {
        setDraft({ start: res.start, end: res.end, portion: res.portion, source: res.source })
      } else {
        setDraft({ start: '', end: '', portion: 'full', source: 'manual' })
        setMessage(res.message)
      }
    } catch (e) {
      setDraft({ start: '', end: '', portion: 'full', source: 'manual' })
      setMessage(`Couldn't read that (${e.message}). Please pick the dates.`)
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    setBusy(true)
    setMessage(null)
    try {
      await onConfirm({ start: draft.start, end: draft.end, portion: draft.start === draft.end ? draft.portion : 'full' })
      setDraft(null)
      setText('')
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  const set = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value, source: 'manual' }))
  const valid = draft?.start && draft?.end && draft.end >= draft.start
  const single = draft?.start && draft.start === draft.end
  const days = !valid ? 0 : single && draft.portion !== 'full' ? 0.5 : workingDays(draft.start, draft.end)

  return (
    <div className="composer-box">
      <form className="leave-input" onSubmit={(e) => { e.preventDefault(); understand() }}>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={300}
          placeholder='Type it like you would say it, e.g. "off 21 to 25 Oct"' aria-label="Describe the leave" />
        <button className="btn primary" disabled={busy || !text.trim() || disabled}>Preview</button>
      </form>
      <div className="suggestions">
        {EXAMPLES.map((ex) => <button key={ex} className="chip-btn" onClick={() => understand(ex)} disabled={busy || disabled}>{ex}</button>)}
        <button className="link-btn" onClick={() => setDraft({ start: '', end: '', portion: 'full', source: 'manual' })}>
          or pick dates
        </button>
      </div>

      {message && <div className="banner">{message}</div>}

      {draft && (
        <div className="preview">
          <div className="preview-head">
            <div>
              <div className="preview-title">{valid ? fmtRange(draft.start, draft.end, single ? draft.portion : 'full') : 'Pick the dates'}</div>
              {valid && <div className="muted">{days} working day{days === 1 ? '' : 's'}</div>}
            </div>
            <span className="source-tag">
              {draft.source === 'ai' ? '✨ Read by AI' : draft.source === 'rules' ? '⚡ Read by date parser' : '✍️ Manual'}
            </span>
          </div>
          <div className="preview-fields">
            <label>From<input type="date" value={draft.start} onChange={set('start')} /></label>
            <label>To<input type="date" value={draft.end} min={draft.start} onChange={set('end')} /></label>
            <label>Portion
              <select value={single ? draft.portion : 'full'} onChange={set('portion')} disabled={!single}>
                <option value="full">Full day</option>
                <option value="am">Morning (AM)</option>
                <option value="pm">Afternoon (PM)</option>
              </select>
            </label>
          </div>
          <p className="muted small">Only the dates are saved. Beacon never stores the reason for leave.</p>
          <div className="actions">
            <button className="btn primary" disabled={!valid || busy || disabled} onClick={confirm}>{confirmLabel}</button>
            <button className="btn ghost" onClick={() => { setDraft(null); setMessage(null) }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}

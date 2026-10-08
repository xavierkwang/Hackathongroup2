import { useCallback, useEffect, useState } from 'react'
import { api, fmtRange } from '../api'
import LeaveComposer from './LeaveComposer'

export function LeaveList({ items, onDelete, emptyText = 'No upcoming leave.' }) {
  if (!items.length) return <p className="muted">{emptyText}</p>
  return (
    <ul className="leave-list">
      {items.map((lv) => (
        <li key={lv.leaveId}>
          <span>{fmtRange(lv.start, lv.end, lv.portion)}</span>
          {onDelete && <button className="btn small ghost" onClick={() => onDelete(lv)}>Remove</button>}
        </li>
      ))}
    </ul>
  )
}

export default function LeavePage({ me, onSaved }) {
  const [items, setItems] = useState([])
  const [toast, setToast] = useState(null)
  const personId = me?.person?.id

  const load = useCallback(async () => {
    if (!personId) return
    const res = await api(`/api/leave?personId=${personId}`)
    setItems(res.leave)
  }, [personId])

  useEffect(() => { load() }, [load])

  async function save(draft) {
    const res = await api('/api/leave', { method: 'POST', body: { ...draft, personId } })
    if (res.skipped.length) throw new Error('You already have leave on some of those dates.')
    setToast(`Saved: ${fmtRange(draft.start, draft.end, draft.portion)}. Your card now shows it to everyone.`)
    await load()
    onSaved?.()
  }

  async function remove(lv) {
    await api(`/api/leave/${lv.personId}/${lv.leaveId}`, { method: 'DELETE' })
    await load()
    onSaved?.()
  }

  if (!me) return null
  if (!personId) return <div className="page"><div className="banner">Ask an admin to add you to the directory first.</div></div>

  return (
    <div className="page">
      <section className="panel">
        <h2>Tell people you're away</h2>
        <p className="muted">Write it however you like. You'll see a preview before anything is saved.</p>
        <LeaveComposer onConfirm={save} />
        {toast && <div className="banner ok" role="status">{toast}</div>}
      </section>
      <section className="panel">
        <h2>Your upcoming leave</h2>
        <LeaveList items={items} onDelete={remove} />
      </section>
    </div>
  )
}

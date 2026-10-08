import { useState } from 'react'
import { api } from '../api'

const TEMPLATE = 'id,name,email,role,team,projects,owns,skills,floor,desk,zone,slackHandle,slackUserId,accessRole\n'

export default function Admin({ onSaved }) {
  const [csv, setCsv] = useState('')
  const [replace, setReplace] = useState(false)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onFile(e) {
    const file = e.target.files?.[0]
    if (file) setCsv(await file.text())
  }

  async function upload() {
    setBusy(true)
    setMsg(null)
    try {
      const res = await api('/api/admin/people', { method: 'POST', body: { csv, replace } })
      setMsg({ ok: true, text: `Imported ${res.imported} people${res.replaced ? ' (directory replaced)' : ''}.` })
      onSaved?.()
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const rows = csv.trim() ? csv.trim().split('\n').length - 1 : 0
  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`

  return (
    <div className="page">
      <section className="panel">
        <h2>Update the directory</h2>
        <p className="muted">
          Upload the people CSV (export it from your Google Sheet). Lists like projects and skills are separated with
          <code> ; </code>. The <code>desk</code> column must match a desk ID on the floor plan
          (<code>frontend/public/floors.json</code>). <a href={templateHref} download="beacon-people-template.csv">Download a blank template</a>.
        </p>
        <input type="file" accept=".csv,text/csv" onChange={onFile} />
        <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={10} placeholder="…or paste CSV here" spellCheck={false} />
        <label className="check">
          <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
          Replace the whole directory (removes anyone not in this file)
        </label>
        <div className="actions">
          <button className="btn primary" disabled={!rows || busy} onClick={upload}>Import {rows || ''} row{rows === 1 ? '' : 's'}</button>
        </div>
        {msg && <div className={`banner ${msg.ok ? 'ok' : 'error'}`}>{msg.text}</div>}
      </section>
    </div>
  )
}

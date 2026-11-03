import { useState } from 'react'
import { api } from '../api.js'

export const TEMPLATE_CSV = [
  'roll_number,record_type,assessment_title,topic,raw_score,max_score,period_start,period_end,sessions_attended,sessions_total,assignment,status,questions_attempted,questions_correct',
  'EP26001,assessment_result,Quiz 5: Object-Oriented Basics,Object-Oriented Basics,14,20,,,,,,,,',
  'EP26001,attendance,,,,,2026-10-20,2026-10-26,4,5,,,,',
  'EP26001,assignment,,,,,,,,,Assignment 5: Object-Oriented Basics,submitted,,',
  'EP26001,practice,,Loops,,,,,,,,,10,7',
].join('\n') + '\n'

const TYPE_LABEL = { assessment_result: 'assessment results', attendance: 'attendance', assignment: 'assignment statuses', practice: 'practice activities' }

// Bulk entry of academic records (brief §10 stage 1: "enters or imports"). The file is always checked
// first (dry run); import is only offered when every row is valid, and the server stores all rows or none.
export default function ImportRecords({ onImported }) {
  const [file, setFile] = useState(null)
  const [check, setCheck] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  async function send(dryRun) {
    const form = new FormData()
    form.append('file', file)
    return api(`/academic-records/import?dry_run=${dryRun}`, { method: 'POST', body: form })
  }
  async function validate() {
    setBusy(true); setMsg(null); setCheck(null)
    try { setCheck(await send(true)) } catch (e) { setMsg({ ok: false, text: e.message }) } finally { setBusy(false) }
  }
  async function doImport() {
    setBusy(true); setMsg(null)
    try {
      const r = await send(false)
      setMsg({ ok: true, text: `Imported ${r.imported} records for ${r.students} student(s). States will be re-estimated before the next selection.` })
      setCheck(null); setFile(null)
      onImported?.()
    } catch (e) { setMsg({ ok: false, text: e.message }) } finally { setBusy(false) }
  }
  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE_CSV)}`

  return (
    <div className="import">
      <p className="small muted">
        One record per row; the student is identified by roll number. <code>topic</code> and <code>assignment</code> take the name/title.
        Every row is validated; if any row is invalid nothing is imported. <a href={templateHref} download="edupulse_records_template.csv">Download template</a>
      </p>
      <div className="inline-form">
        <label className="small">CSV file
          <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files[0] || null); setCheck(null); setMsg(null) }} />
        </label>
        <button className="btn" disabled={!file || busy} onClick={validate}>Check file</button>
        <button className="btn primary" disabled={!check || check.errors.length > 0 || check.valid === 0 || busy} onClick={doImport}>
          Import {check && check.errors.length === 0 ? `${check.valid} records` : ''}
        </button>
      </div>
      {check && (
        <div className={`alert ${check.errors.length ? 'error' : 'ok'}`} role="status">
          {check.rows} rows checked: {check.valid} valid, {check.errors.length} with errors.
          {check.valid > 0 && <> Valid rows: {Object.entries(check.by_type).map(([k, v]) => `${v} ${TYPE_LABEL[k] || k}`).join(', ')}.</>}
        </div>
      )}
      {check?.errors.length > 0 && (
        <table className="compact">
          <thead><tr><th>Row</th><th>Problem</th></tr></thead>
          <tbody>{check.errors.map((e) => <tr key={e.row}><td>{e.row}</td><td>{e.error}</td></tr>)}</tbody>
        </table>
      )}
      {msg && <div className={`alert ${msg.ok ? 'ok' : 'error'}`}>{msg.text}</div>}
    </div>
  )
}

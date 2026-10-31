import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, INTERVENTION_LABEL, pct } from '../api.js'
import { Card, ErrorBox, HistoryTable, IndicatorGrid, Loading, ProgressCharts, StateCard, StatusBadge } from '../components/ui.jsx'

const RECORD_FIELDS = {
  assessment_result: [['assessment_title', 'Assessment title', 'text'], ['topic_id', 'Topic', 'topic'], ['raw_score', 'Score', 'number'], ['max_score', 'Out of', 'number']],
  attendance: [['period_start', 'From', 'date'], ['period_end', 'To', 'date'], ['sessions_attended', 'Sessions attended', 'number'], ['sessions_total', 'Total sessions', 'number']],
  assignment: [['assignment_id', 'Assignment', 'assignment'], ['status', 'Status', 'status']],
  practice: [['topic_id', 'Topic', 'topic'], ['questions_attempted', 'Attempted', 'number'], ['questions_correct', 'Correct', 'number']],
}

function RecordForm({ studentId, topics, assignments, onSaved }) {
  const [type, setType] = useState('assessment_result')
  const [vals, setVals] = useState({})
  const [msg, setMsg] = useState(null)
  async function save(e) {
    e.preventDefault()
    setMsg(null)
    const body = { student_id: studentId, record_type: type }
    for (const [k, , kind] of RECORD_FIELDS[type]) {
      const v = vals[k]
      if (v !== undefined && v !== '') body[k] = ['number', 'topic', 'assignment'].includes(kind) ? Number(v) : v
    }
    try {
      await api('/academic-records', { method: 'POST', body })
      setMsg({ ok: true, text: 'Record saved. The state will be re-estimated before the next selection.' })
      setVals({})
      onSaved()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }
  return (
    <form onSubmit={save} className="record-form">
      <label>Record type
        <select value={type} onChange={(e) => { setType(e.target.value); setVals({}) }}>
          <option value="assessment_result">Assessment result</option><option value="attendance">Attendance</option>
          <option value="assignment">Assignment status</option><option value="practice">Practice activity</option>
        </select>
      </label>
      {RECORD_FIELDS[type].map(([k, label, kind]) => (
        <label key={k}>{label}
          {kind === 'topic' ? (
            <select value={vals[k] || ''} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
              <option value="">Select…</option>{topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          ) : kind === 'assignment' ? (
            <select value={vals[k] || ''} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
              <option value="">Select…</option>{assignments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
            </select>
          ) : kind === 'status' ? (
            <select value={vals[k] || ''} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
              <option value="">Select…</option><option value="submitted">Submitted</option><option value="late">Late</option><option value="missing">Missing</option>
            </select>
          ) : (
            <input type={kind} value={vals[k] || ''} min={kind === 'number' ? 0 : undefined} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
          )}
        </label>
      ))}
      <button className="btn">Save record</button>
      {msg && <div className={`alert ${msg.ok ? 'ok' : 'error'}`}>{msg.text}</div>}
    </form>
  )
}

export default function StudentDetail() {
  const { id } = useParams()
  const sid = Number(id)
  const navigate = useNavigate()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [showRecord, setShowRecord] = useState(false)

  async function load() {
    try {
      const [student, progress, history, topics, assignments] = await Promise.all([
        api(`/students/${sid}`), api(`/students/${sid}/progress`), api(`/students/${sid}/interventions`),
        api('/topics'), api('/assignments'),
      ])
      setD({ student, progress, history, topics, assignments })
    } catch (e) {
      setError(e.message)
    }
  }
  useEffect(() => { load() }, [sid])

  async function act(fn) {
    setBusy(true); setError(''); setInfo('')
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const predict = () => act(async () => { await api(`/students/${sid}/predict-state`, { method: 'POST' }); setInfo('State re-estimated.'); await load() })
  const select = () => act(async () => {
    const r = await api('/interventions/select', { method: 'POST', body: { student_id: sid } })
    if (r.assignment_id) navigate(`/interventions/${r.assignment_id}`)
    else { setInfo(r.message); await load() }
  })
  const faculty = () => act(async () => {
    const r = await api('/interventions/assign', { method: 'POST', body: { student_id: sid, intervention: 'faculty_support', note: note || null } })
    navigate(`/interventions/${r.id}`)
  })

  if (!d) return error ? <ErrorBox error={error} /> : <Loading />
  const { student: s, progress, history } = d
  const open = s.open_intervention

  return (
    <>
      <div className="page-head">
        <div>
          <Link to="/faculty" className="small">← Students</Link>
          <h1>{s.name}</h1>
          <p className="muted">{s.roll_number} · {s.program} · Year {s.year} · {s.email}</p>
        </div>
        <div className="actions">
          <button className="btn ghost" disabled={busy} onClick={predict}>Re-estimate state</button>
          <button className="btn primary" disabled={busy || !!open} onClick={select} title={open ? 'Finish the open intervention first' : ''}>Select next intervention</button>
        </div>
      </div>
      <ErrorBox error={error} />
      {info && <div className="alert info">{info}</div>}
      {s.no_improvement_streak >= 2 && (
        <div className="alert warn">{s.no_improvement_streak} consecutive interventions showed no improvement. Faculty support is now eligible; please review.</div>
      )}

      <div className="grid-2">
        <Card title="Estimated academic state"><StateCard state={s.state} stale={s.state_is_stale} /></Card>
        <Card title="Open intervention">
          {open ? (
            <div className="current">
              <div className="current-type">{INTERVENTION_LABEL[open.intervention]}</div>
              <div className="muted">Topic: {open.topic || 'General'} · <StatusBadge status={open.status} /> · pre-score {pct(open.pre_score)}</div>
              <Link className="btn ghost" to={`/interventions/${open.id}`}>View / update</Link>
            </div>
          ) : (
            <div>
              <p className="muted">None open.</p>
              <label className="small">Record faculty support (consultation)
                <input placeholder="Note for the student (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              </label>
              <button className="btn" disabled={busy} onClick={faculty}>Record faculty support</button>
            </div>
          )}
        </Card>
      </div>

      <Card title="Academic indicators"><IndicatorGrid indicators={s.indicators} /></Card>

      <Card title="By topic">
        <div className="table-wrap">
          <table><thead><tr><th>Topic</th><th>Latest score</th><th>Practice accuracy</th></tr></thead>
            <tbody>{s.per_topic.map((t) => <tr key={t.topic_id}><td>{t.topic}</td><td>{pct(t.latest_score)}</td><td>{pct(t.practice_accuracy_pct)}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>

      <Card title="Add academic record" actions={<button className="btn ghost small" onClick={() => setShowRecord(!showRecord)}>{showRecord ? 'Hide' : 'Show form'}</button>}>
        {showRecord ? <RecordForm studentId={sid} topics={d.topics} assignments={d.assignments} onSaved={load} /> : <p className="muted small">Enter assessment, attendance, assignment or practice data. Missing or out-of-range values are rejected.</p>}
      </Card>

      <Card title="Historical progress"><ProgressCharts progress={progress} /></Card>
      <Card title="Intervention history" actions={<Link to={`/students/${sid}/history`}>Full history</Link>}><HistoryTable rows={history} /></Card>
    </>
  )
}

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, INTERVENTION_LABEL } from '../api.js'
import { useAuth } from '../App.jsx'
import { Card, ErrorBox, HistoryTable, IndicatorGrid, Loading, ProgressCharts, StateCard, StatusBadge } from '../components/ui.jsx'

export default function StudentDashboard() {
  const { session } = useAuth()
  const sid = session.user.student_id
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function load() {
    try {
      const [student, progress, history] = await Promise.all([
        api(`/students/${sid}`), api(`/students/${sid}/progress`), api(`/students/${sid}/interventions`),
      ])
      setData({ student, progress, history })
    } catch (e) {
      setError(e.message)
    }
  }
  useEffect(() => { load() }, [])

  async function requestNext() {
    setBusy(true); setError(''); setMessage('')
    try {
      const res = await api('/interventions/select', { method: 'POST', body: { student_id: sid } })
      if (res.assignment_id) navigate(`/interventions/${res.assignment_id}`)
      else { setMessage(res.message); load() }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return error ? <ErrorBox error={error} /> : <Loading />
  const { student, progress, history } = data
  const open = student.open_intervention
  const pending = history.filter((h) => ['assigned', 'accessed', 'completed'].includes(h.status))

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Hi, {student.name.split(' ')[0]}</h1>
          <p className="muted">{student.roll_number} · {student.program} · Year {student.year}</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {message && <div className="alert info">{message}</div>}

      <div className="grid-2">
        <Card title="Current support">
          {open ? (
            <div className="current">
              <div className="current-type">{INTERVENTION_LABEL[open.intervention]}</div>
              <div className="muted">Topic: {open.topic || 'General'} · <StatusBadge status={open.status} /></div>
              {open.reason?.length > 0 && <p className="small">Why: {open.reason.join('; ')}</p>}
              <Link className="btn primary" to={`/interventions/${open.id}`}>
                {open.status === 'completed' ? 'Submit follow-up assessment' : 'Open activity'}
              </Link>
            </div>
          ) : (
            <div className="current">
              <p>No open activity. Ask EduPulse for your next recommendation based on your latest results.</p>
              <button className="btn primary" disabled={busy} onClick={requestNext}>
                {busy ? 'Selecting…' : 'Get my next recommendation'}
              </button>
            </div>
          )}
        </Card>
        <Card title="Academic state">
          <StateCard state={student.state} stale={student.state_is_stale} />
        </Card>
      </div>

      <Card title="My indicators"><IndicatorGrid indicators={student.indicators} /></Card>

      {pending.length > 0 && (
        <Card title="Pending activities">
          <ul className="plain">
            {pending.map((p) => (
              <li key={p.id}><Link to={`/interventions/${p.id}`}>{p.intervention_name}</Link> · {p.topic} · <StatusBadge status={p.status} /></li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Progress"><ProgressCharts progress={progress} /></Card>
      <Card title="Intervention history" actions={<Link to={`/students/${sid}/history`}>Full history</Link>}>
        <HistoryTable rows={history.slice(0, 5)} />
      </Card>
    </>
  )
}

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, INTERVENTION_LABEL } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../components/icons.jsx'
import { Reminders } from '../components/Notifications.jsx'
import {
  Card, Empty, ErrorBox, HistoryTable, IndicatorGrid, Loading, ProgressCharts, StateCard, StateTrend, StatusBadge,
} from '../components/ui.jsx'

export const TYPE_ICON = { study_plan: 'calendar', targeted_material: 'book', targeted_practice: 'target', faculty_support: 'users' }
const STEPS = ['Assigned', 'In progress', 'Follow-up', 'Result']
const STEP_AT = { assigned: 1, accessed: 1, completed: 2, evaluated: 4 }

const HERO = {
  assigned: ['A new activity is waiting for you.', 'Open activity'],
  accessed: ['You have an activity in progress.', 'Continue activity'],
  completed: ['Your follow-up assessment is due.', 'Submit follow-up assessment'],
}

// The open intervention, shown as the student's current plan: where they are in the cycle and what to do next.
function StudyPlan({ open, others }) {
  if (!open) {
    return (
      <>
        <Empty icon="target">
          No open activity. Use <strong>Get my next recommendation</strong> above and EduPulse will pick the support most likely to help,
          based on your latest results.
        </Empty>
        <ul className="how">
          <li><Icon name="activity" size={16} /><span><b>1. Estimate</b>Your records give an estimate of your academic state.</span></li>
          <li><Icon name="zap" size={16} /><span><b>2. Select</b>EduPulse picks one support activity that fits it.</span></li>
          <li><Icon name="file" size={16} /><span><b>3. Follow up</b>Finish the activity, then record a follow-up score.</span></li>
          <li><Icon name="refresh" size={16} /><span><b>4. Adapt</b>The result shapes your next recommendation.</span></li>
        </ul>
      </>
    )
  }
  const r = open.resource
  const days = r?.content?.days
  const qs = r?.content?.questions
  const at = STEP_AT[open.status] ?? 1
  return (
    <>
      <div className="plan-head">
        <span className="plan-icon"><Icon name={TYPE_ICON[open.intervention] || 'layers'} size={22} /></span>
        <div>
          <div className="plan-title">{r?.title || INTERVENTION_LABEL[open.intervention]}</div>
          <div className="muted small">{INTERVENTION_LABEL[open.intervention]} · Topic: {open.topic || 'General'} · <StatusBadge status={open.status} /></div>
        </div>
      </div>
      <div className="steps" aria-label="Progress through this activity">
        {STEPS.map((s, i) => (
          <div key={s} className={`step ${i < at ? 'done' : i === at ? 'current' : ''}`}>
            <span className="step-dot">{i < at ? <Icon name="check" size={14} strokeWidth={3} /> : i + 1}</span>{s}
          </div>
        ))}
      </div>
      {r?.objective && <p><strong>Learning objective:</strong> {r.objective}</p>}
      {days && (
        <ul className="plan-days">
          {days.slice(0, 5).map((d) => <li key={d.day}><span className="day">DAY {d.day}</span>{d.task}</li>)}
        </ul>
      )}
      {qs && <p className="small muted">{qs.length} practice questions on {open.topic}.</p>}
      {open.reason?.length > 0 && <p className="small muted">Why this was chosen: {open.reason.join('; ')}</p>}
      <Link className="btn primary" to={`/interventions/${open.id}`}>
        {open.status === 'completed' ? 'Submit follow-up assessment' : 'Open activity'}<Icon name="arrowRight" size={16} />
      </Link>
      {others.length > 0 && (
        <p className="small muted" style={{ marginTop: 12 }}>
          Also pending: {others.map((p, i) => <span key={p.id}>{i > 0 && ', '}<Link to={`/interventions/${p.id}`}>{p.intervention_name}</Link></span>)}
        </p>
      )}
    </>
  )
}

export default function StudentDashboard() {
  const { session } = useAuth()
  const sid = session.user.student_id
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [notes, setNotes] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function load() {
    try {
      const [student, progress, history] = await Promise.all([
        api(`/students/${sid}`), api(`/students/${sid}/progress`), api(`/students/${sid}/interventions`),
      ])
      setData({ student, progress, history })
      api('/notifications').then((n) => setNotes(n || [])).catch(() => {})
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
  const evaluated = history.filter((h) => h.category)
  const positive = evaluated.filter((h) => h.category === 'positive').length
  const [heroLine, heroCta] = open ? HERO[open.status] || HERO.accessed : ['You are up to date. Ask EduPulse for your next recommendation when you are ready.', null]

  return (
    <>
      <section className="hero">
        <div>
          <h1>Hi, {student.name.split(' ')[0]}</h1>
          <p>{heroLine}</p>
          <div className="hero-meta">
            <span className="hero-chip"><Icon name="cap" size={14} />{student.roll_number}</span>
            <span className="hero-chip"><Icon name="book" size={14} />{student.program} · Year {student.year}</span>
            <span className="hero-chip"><Icon name="award" size={14} />{evaluated.length} completed · {positive} positive</span>
          </div>
        </div>
        <div className="hero-side">
          {open ? (
            <Link className="btn white lg" to={`/interventions/${open.id}`}>{heroCta}<Icon name="arrowRight" size={17} /></Link>
          ) : (
            <button className="btn white lg" disabled={busy} onClick={requestNext}>
              {busy ? <><span className="spinner" aria-hidden />Selecting…</> : <><Icon name="zap" size={17} />Get my next recommendation</>}
            </button>
          )}
          {open && <span className="small">{INTERVENTION_LABEL[open.intervention]} · {open.topic || 'General'}</span>}
        </div>
      </section>
      <ErrorBox error={error} />
      {message && <div className="alert info"><Icon name="alert" size={16} />{message}</div>}

      {notes.some((n) => n.action_required) && (
        <Card title="To do" subtitle="Reminders about your activities" icon="bell"><Reminders items={notes} /></Card>
      )}

      <Card title="Performance summary" subtitle="Calculated from your latest academic records" icon="chart">
        <IndicatorGrid indicators={student.indicators} />
      </Card>

      <div className="grid-2 wide-left">
        <Card title="My study plan" subtitle="Your current support activity" icon="target">
          <StudyPlan open={open} others={pending.filter((p) => p.id !== open?.id)} />
        </Card>
        <Card title="Academic state" subtitle="Random Forest estimate" icon="activity">
          <StateCard state={student.state} stale={student.state_is_stale} />
          <StateTrend states={progress.states} />
        </Card>
      </div>

      <Card title="Progress" subtitle="Assessments over time and the effect of each intervention" icon="trend"><ProgressCharts progress={progress} /></Card>
      <Card title="Recent interventions" icon="clock"
        actions={<Link to={`/students/${sid}/history`}>Full history<Icon name="arrowRight" size={14} /></Link>}>
        <HistoryTable rows={history.slice(0, 5)} />
      </Card>
    </>
  )
}

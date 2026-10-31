import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDateTime, INTERVENTION_LABEL, pct } from '../api.js'
import { useAuth } from '../App.jsx'
import { Card, CategoryBadge, ErrorBox, Loading, StateBadge, StatusBadge } from '../components/ui.jsx'

// Screens 5 (intervention details) and 6 (follow-up assessment / response)
export default function InterventionDetail() {
  const { id } = useParams()
  const { session } = useAuth()
  const role = session.user.role
  const [a, setA] = useState(null)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState({})
  const [score, setScore] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  async function load() {
    try {
      const d = await api(`/interventions/${id}`)
      setA(d)
      if (d.status === 'assigned' && role === 'student') {
        await api(`/interventions/${id}/access`, { method: 'POST' })
        setA({ ...d, status: 'accessed' })
      }
    } catch (e) {
      setError(e.message)
    }
  }
  useEffect(() => { load() }, [id])

  async function complete() {
    setError(''); setBusy(true)
    try {
      const qs = a.resource?.content?.questions
      const body = qs ? { answers: qs.map((_, i) => (answers[i] === undefined ? null : answers[i])) } : {}
      if (qs && body.answers.some((x) => x === null)) throw new Error('Please answer every question before submitting.')
      const res = await api(`/interventions/${id}/complete`, { method: 'POST', body })
      if (res.practice_result) setResult({ practice: res.practice_result })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitFollowUp(e) {
    e.preventDefault()
    setError('')
    const v = Number(score)
    if (score === '' || Number.isNaN(v) || v < 0 || v > 100) {
      setError('Enter the follow-up score as a percentage between 0 and 100.')
      return
    }
    setBusy(true)
    try {
      const res = await api(`/interventions/${id}/response`, { method: 'POST', body: { post_score: v, evaluate: true } })
      setResult((r) => ({ ...r, evaluation: res.evaluation }))
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!a) return error ? <ErrorBox error={error} /> : <Loading />
  const r = a.resource
  const qs = r?.content?.questions
  const days = r?.content?.days
  const canComplete = ['assigned', 'accessed'].includes(a.status) && (a.intervention !== 'faculty_support' || role !== 'student')
  const resp = a.response
  const back = role === 'student' ? '/student' : `/students/${a.student_id}`

  return (
    <>
      <div className="page-head">
        <div>
          <Link to={back} className="small">← Back</Link>
          <h1>{r?.title || INTERVENTION_LABEL[a.intervention]}</h1>
          <p className="muted">{INTERVENTION_LABEL[a.intervention]} · Topic: {a.topic || 'General'} · Assigned {fmtDateTime(a.assigned_at)}</p>
        </div>
        <StatusBadge status={a.status} />
      </div>
      <ErrorBox error={error} />

      <div className="grid-2 wide-left">
        <div>
          <Card title="Activity">
            {r?.objective && <p><strong>Learning objective:</strong> {r.objective}</p>}
            {r?.instructions && <p>{r.instructions}</p>}
            {a.faculty_note && <p><strong>Faculty note:</strong> {a.faculty_note}</p>}
            {r?.url && <p><a className="btn ghost" href={r.url} target="_blank" rel="noreferrer">Open learning material ↗</a></p>}
            {days && (
              <ol className="plan">{days.map((d) => <li key={d.day}><strong>Day {d.day}.</strong> {d.task}</li>)}</ol>
            )}
            {qs && (
              <div className="quiz">
                {qs.map((q, i) => (
                  <fieldset key={i} disabled={!canComplete}>
                    <legend>{i + 1}. {q.q}</legend>
                    {q.options.map((o, j) => (
                      <label key={j} className="option">
                        <input type="radio" name={`q${i}`} checked={answers[i] === j}
                          onChange={() => setAnswers({ ...answers, [i]: j })} /> {o}
                      </label>
                    ))}
                  </fieldset>
                ))}
              </div>
            )}
            {canComplete && (
              <button className="btn primary" disabled={busy} onClick={complete}>
                {qs ? 'Submit practice answers' : a.intervention === 'faculty_support' ? 'Mark consultation held' : 'Mark as completed'}
              </button>
            )}
            {a.intervention === 'faculty_support' && role === 'student' && ['assigned', 'accessed'].includes(a.status) && (
              <p className="small muted">Your faculty member marks this complete after the consultation.</p>
            )}
            {result?.practice && (
              <div className="alert info">Practice result: {result.practice.correct} / {result.practice.attempted} correct. This is recorded as practice activity.</div>
            )}
          </Card>

          {a.status === 'completed' && (
            <Card title="Follow-up assessment">
              <p>Take the follow-up assessment on <strong>{a.topic}</strong> and record the score. It is compared with your
                pre-intervention score of <strong>{pct(a.pre_score)}</strong> on the same topic and scale.</p>
              <form onSubmit={submitFollowUp} className="inline-form">
                <label>Follow-up score (%)
                  <input type="number" min="0" max="100" step="0.5" value={score} onChange={(e) => setScore(e.target.value)} />
                </label>
                <button className="btn primary" disabled={busy}>{busy ? 'Saving…' : 'Submit and evaluate'}</button>
              </form>
            </Card>
          )}

          {resp && (
            <Card title="Response evaluation">
              <div className="eval">
                <div><span className="muted small">Before</span><strong>{pct(resp.evidence?.pre_score ?? a.pre_score)}</strong></div>
                <div><span className="muted small">After</span><strong>{pct(resp.post_indicators?.topic_score)}</strong></div>
                <div><span className="muted small">Learning gain g</span><strong>{resp.learning_gain?.toFixed(2) ?? '—'}</strong></div>
                <div><span className="muted small">Engagement change e</span><strong>{resp.engagement_change === null ? 'n/a' : resp.engagement_change?.toFixed(2)}</strong></div>
                <div><span className="muted small">Reward r</span><strong>{resp.reward?.toFixed(2) ?? '—'}</strong></div>
                <div><span className="muted small">Response</span><CategoryBadge category={resp.category} /></div>
              </div>
              {resp.evidence?.formula && (
                <p className="small muted">r = α·g + (1−α)·e with α = {resp.evidence.alpha_effective}
                  {resp.evidence.alpha_effective === 1 && ' (engagement not comparable in both windows, so r = g)'}.
                  Thresholds: Positive ≥ {resp.evidence.thresholds.positive}, Partial ≥ {resp.evidence.thresholds.partial}.</p>
              )}
              {result?.evaluation && (
                <div className="alert ok">
                  Policy updated v{result.evaluation.policy_update.from_version} → v{result.evaluation.policy_update.to_version}.
                  State reassessed: <StateBadge state={result.evaluation.state_reassessment.state} />
                </div>
              )}
              {role === 'student' && <Link className="btn ghost" to="/student">Back to dashboard</Link>}
            </Card>
          )}
        </div>

        <Card title="Why this was selected">
          <p className="small"><strong>Eligibility:</strong> {(a.reason || []).join('; ') || '—'}</p>
          <p className="small"><strong>Eligible set:</strong> {a.eligible.map((e) => INTERVENTION_LABEL[e]).join(', ')}</p>
          <p className="small"><strong>Method:</strong> {a.selection_method === 'linear_thompson' ? 'Linear Thompson sampling' : 'Recorded by faculty'}</p>
          {role !== 'student' && a.selection_method === 'linear_thompson' && (
            <>
              <h3>Sampled scores</h3>
              <table className="compact">
                <thead><tr><th>Intervention</th><th>Sampled</th><th>Mean</th><th>±SD</th><th>n</th></tr></thead>
                <tbody>
                  {Object.entries(a.sampled_scores).map(([k, v]) => (
                    <tr key={k} className={k === a.intervention ? 'chosen' : ''}>
                      <td>{INTERVENTION_LABEL[k]}</td><td>{v.sampled_score.toFixed(3)}</td>
                      <td>{v.posterior_mean_score.toFixed(3)}</td><td>{v.posterior_sd_score.toFixed(3)}</td><td>{v.n_observations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Context vector</h3>
              <table className="compact">
                <tbody>
                  {a.context.vector_features.map((f, i) => (
                    <tr key={f}><td>{f}</td><td>{a.context.vector[i].toFixed(3)}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted">RNG seed {a.rng_seed} · policy version id {a.policy_version_id}. The decision can be reproduced from these values.</p>
            </>
          )}
        </Card>
      </div>
    </>
  )
}

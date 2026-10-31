import { Link } from 'react-router-dom'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine, Bar, BarChart, Legend,
} from 'recharts'
import { CATEGORY_LABEL, INTERVENTION_LABEL, STATE_LABEL, fmtDate, pct } from '../api.js'

export const COLORS = {
  normal: 'var(--ok)', attention_needed: 'var(--warn)', high_support_need: 'var(--bad)', not_assessed: 'var(--muted)',
  positive: 'var(--ok)', partial: 'var(--warn)', no_improvement: 'var(--bad)',
}
// raw hex for recharts (which cannot read CSS variables in all cases)
export const HEX = {
  normal: '#2f9e6b', attention_needed: '#d99a1e', high_support_need: '#d1495b', not_assessed: '#9aa3b2',
  positive: '#2f9e6b', partial: '#d99a1e', no_improvement: '#d1495b', primary: '#3b5bdb', secondary: '#7c5cd6',
  assigned: '#3b5bdb',
}

export function StateBadge({ state }) {
  if (!state) return <span className="badge muted">Not assessed</span>
  return <span className={`badge ${state}`}>{STATE_LABEL[state] || state}</span>
}

export function CategoryBadge({ category }) {
  if (!category) return <span className="badge muted">Pending</span>
  return <span className={`badge ${category}`}>{CATEGORY_LABEL[category]}</span>
}

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{status}</span>
}

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Loading() {
  return <div className="loading">Loading…</div>
}

export function ErrorBox({ error }) {
  return error ? <div className="alert error" role="alert">{error}</div> : null
}

export function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

const IND_LABELS = {
  latest_score: 'Latest assessment', avg_score: 'Average assessment', attendance_pct: 'Attendance',
  assignment_completion_pct: 'Assignment completion', practice_accuracy_pct: 'Practice accuracy',
  previous_result_pct: 'Previous result',
}

export function IndicatorGrid({ indicators }) {
  return (
    <div className="indicators">
      {Object.entries(IND_LABELS).map(([k, label]) => {
        const v = indicators?.[k]
        return (
          <div key={k} className="indicator">
            <div className="indicator-label">{label}</div>
            <div className="indicator-value">{v === null || v === undefined ? <span className="muted">no data</span> : pct(v)}</div>
            {v !== null && v !== undefined && (
              <div className="meter"><span style={{ width: `${Math.min(100, v)}%` }} /></div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function StateCard({ state, stale }) {
  if (!state) return <p className="muted">No state estimate yet.</p>
  const probs = state.probabilities || {}
  return (
    <div className="state-card">
      <div className="state-row">
        <StateBadge state={state.state} />
        <span className="muted small">model {state.model_version} · {fmtDate(state.created_at)}</span>
        {stale && <span className="badge muted" title="New records since this estimate">update pending</span>}
      </div>
      <div className="probs">
        {['normal', 'attention_needed', 'high_support_need'].map((k) => (
          <div key={k} className="prob">
            <span>{STATE_LABEL[k]}</span>
            <div className="meter"><span style={{ width: `${(probs[k] || 0) * 100}%`, background: HEX[k] }} /></div>
            <span className="small">{Math.round((probs[k] || 0) * 100)}%</span>
          </div>
        ))}
      </div>
      {state.explanation?.concerns?.length > 0 && (
        <ul className="concerns">
          {state.explanation.concerns.map((c) => <li key={c}>{c}</li>)}
        </ul>
      )}
      {state.explanation?.imputed_note && <p className="small muted">{state.explanation.imputed_note}</p>}
      <p className="small muted">This estimate supports academic guidance. It is not a judgment of ability.</p>
    </div>
  )
}

export function ProgressCharts({ progress }) {
  if (!progress) return null
  const scores = progress.assessments.map((a, i) => ({
    n: i + 1, label: `${fmtDate(a.date)}`, score: a.score_pct, title: a.title, kind: a.kind,
  }))
  const iv = progress.interventions.map((i, k) => ({
    name: `#${i.id} ${INTERVENTION_LABEL[i.intervention]?.split(' ')[1] || i.intervention}`, pre: i.pre, post: i.post,
  }))
  return (
    <div className="charts-2">
      <div>
        <h3>Assessment scores over time</h3>
        {scores.length === 0 ? <p className="muted">No assessments yet.</p> : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={scores} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="n" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <ReferenceLine y={60} stroke="#9aa3b2" strokeDasharray="4 4" />
              <Tooltip formatter={(v) => `${v}%`} labelFormatter={(n) => `${scores[n - 1]?.title} (${scores[n - 1]?.label})`} />
              <Line dataKey="score" stroke={HEX.primary} strokeWidth={2} dot={(p) => (
                <circle key={p.key} cx={p.cx} cy={p.cy} r={scores[p.index]?.kind === 'follow_up' ? 6 : 4}
                  fill={scores[p.index]?.kind === 'follow_up' ? HEX.secondary : HEX.primary} />
              )} />
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="small muted">Purple points are follow-up assessments after an intervention.</p>
      </div>
      <div>
        <h3>Before and after each intervention</h3>
        {iv.length === 0 ? <p className="muted">No evaluated interventions yet.</p> : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={iv} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => `${v}%`} />
              <Legend />
              <Bar dataKey="pre" name="Before" fill="#9aa3b2" radius={[4, 4, 0, 0]} />
              <Bar dataKey="post" name="After" fill={HEX.primary} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

export function HistoryTable({ rows }) {
  if (!rows?.length) return <p className="muted">No interventions recorded yet.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th><th>Intervention</th><th>Topic</th><th>Reason / eligibility</th><th>Status</th>
            <th>Before</th><th>After</th><th>Response</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{fmtDate(r.assigned_at)}</td>
              <td><Link to={`/interventions/${r.id}`}>{r.intervention_name}</Link>
                {r.selection_method === 'faculty_manual' && <div className="small muted">recorded by faculty</div>}
              </td>
              <td>{r.topic || '—'}</td>
              <td className="small">{(r.reason || []).join('; ') || '—'}</td>
              <td><StatusBadge status={r.status} /></td>
              <td>{pct(r.pre_score)}</td>
              <td>{pct(r.post_score)}</td>
              <td><CategoryBadge category={r.category} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine, Bar, BarChart, Legend,
} from 'recharts'
import { CATEGORY_LABEL, INTERVENTION_LABEL, STATE_LABEL, fmtDate, pct } from '../api.js'
import { Icon } from './icons.jsx'

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
  return <span className={`badge dot ${state}`}>{STATE_LABEL[state] || state}</span>
}

export function CategoryBadge({ category }) {
  if (!category) return <span className="badge muted">Pending</span>
  return <span className={`badge dot ${category}`}>{CATEGORY_LABEL[category]}</span>
}

const STATUS_LABEL = { assigned: 'assigned', accessed: 'in progress', completed: 'awaiting follow-up', evaluated: 'evaluated', cancelled: 'cancelled' }
export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status] || status}</span>
}

export function Card({ title, subtitle, icon, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && (
            <div className="card-title">
              {icon && <span className="card-icon"><Icon name={icon} size={17} /></span>}
              <div><h2>{title}</h2>{subtitle && <div className="card-sub">{subtitle}</div>}</div>
            </div>
          )}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Loading() {
  return <div className="loading"><span className="pulse" aria-hidden />Loading…</div>
}

export function ErrorBox({ error }) {
  return error ? <div className="alert error" role="alert"><Icon name="alert" size={16} />{error}</div> : null
}

export function Empty({ icon = 'layers', children }) {
  return <div className="empty"><Icon name={icon} size={30} strokeWidth={1.6} /><div>{children}</div></div>
}

// Count-up for numbers. Skipped when the user prefers reduced motion (and in tests, where matchMedia is absent).
const canAnimate = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' &&
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches
export function Num({ value, decimals = 0, suffix = '' }) {
  const [shown, setShown] = useState(() => (canAnimate() && typeof value === 'number' ? 0 : value))
  useEffect(() => {
    if (!canAnimate() || typeof value !== 'number') { setShown(value); return undefined }
    let raf, start
    const step = (t) => {
      start ??= t
      const p = Math.min(1, (t - start) / 900)
      setShown(value * (1 - (1 - p) ** 3))
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <>{typeof shown === 'number' ? shown.toFixed(decimals) : shown}{suffix}</>
}

export function Stat({ label, value, hint, icon, tone = '', suffix = '' }) {
  return (
    <div className={`stat ${tone ? `tone-${tone}` : ''}`}>
      {icon && <span className="stat-icon"><Icon name={icon} size={21} /></span>}
      <div className="stat-body">
        <div className="stat-value">{typeof value === 'number' ? <Num value={value} suffix={suffix} /> : value}</div>
        <div className="stat-label">{label}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </div>
  )
}

export function Meter({ value, className = '', color }) {
  const w = Math.max(0, Math.min(100, value ?? 0))
  return <div className={`meter ${className}`}><span style={{ width: `${w}%`, ...(color ? { background: color } : {}) }} /></div>
}

const AVATAR_TONES = ['', 'tone-1', 'tone-2', 'tone-3', 'tone-4']
export function Avatar({ name = '', size = '' }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
  const tone = AVATAR_TONES[[...name].reduce((h, c) => h + c.charCodeAt(0), 0) % AVATAR_TONES.length]
  return <span className={`avatar ${size} ${tone}`} aria-hidden>{initials || '?'}</span>
}

const IND_ICONS = {
  latest_score: 'file', avg_score: 'chart', attendance_pct: 'calendar', assignment_completion_pct: 'checkCircle',
  practice_accuracy_pct: 'target', previous_result_pct: 'award',
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
            <div className="indicator-top"><span className="indicator-label">{label}</span><Icon name={IND_ICONS[k]} size={16} /></div>
            <div className="indicator-value">{v === null || v === undefined ? <span className="muted">no data</span> : pct(v)}</div>
            {v !== null && v !== undefined ? <Meter value={v} /> : <div className="meter" />}
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
            <Meter value={(probs[k] || 0) * 100} color={HEX[k]} />
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

// Academic-state trend: one step per stored estimate (0 = Normal, 2 = High Support Need).
const LEVEL_LABEL = ['Normal', 'Attention', 'High support']
export function StateTrend({ states }) {
  if (!states || states.length < 2) return null
  const data = states.map((s, i) => ({ n: i + 1, level: s.level, date: fmtDate(s.date), state: s.state }))
  return (
    <div className="state-trend">
      <h3>State over time</h3>
      <ResponsiveContainer width="100%" height={124}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 12 }}>
          <defs>
            <linearGradient id="state-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={HEX.high_support_need} stopOpacity={0.22} />
              <stop offset="100%" stopColor={HEX.normal} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <YAxis domain={[0, 2]} ticks={[0, 1, 2]} interval={0} tickFormatter={(v) => LEVEL_LABEL[v]} width={92} tickLine={false} axisLine={false} />
          <XAxis dataKey="n" hide />
          <Tooltip formatter={(v, n, p) => [STATE_LABEL[p.payload.state], 'State']} labelFormatter={(n) => data[n - 1]?.date} />
          <Area type="stepAfter" dataKey="level" stroke={HEX.secondary} strokeWidth={2} fill="url(#state-fill)" animationDuration={1000} />
        </AreaChart>
      </ResponsiveContainer>
      <div className="trend-caption"><span>{data[0].date}</span><span>{data[data.length - 1].date}</span></div>
    </div>
  )
}

export function ProgressCharts({ progress }) {
  if (!progress) return null
  const scores = progress.assessments.map((a, i) => ({
    n: i + 1, label: `${fmtDate(a.date)}`, score: a.score_pct, title: a.title, kind: a.kind,
  }))
  const iv = progress.interventions.map((i) => ({
    name: `#${i.id} ${INTERVENTION_LABEL[i.intervention]?.split(' ')[1] || i.intervention}`, pre: i.pre, post: i.post,
  }))
  return (
    <div className="charts-2">
      <div>
        <h3>Assessment scores over time</h3>
        {scores.length === 0 ? <Empty icon="chart">No assessments yet.</Empty> : (
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={scores} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="score-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={HEX.primary} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={HEX.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="n" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
              <ReferenceLine y={60} stroke="#b3bad0" strokeDasharray="4 4" />
              <Tooltip formatter={(v) => [`${v}%`, 'Score']} labelFormatter={(n) => `${scores[n - 1]?.title} (${scores[n - 1]?.label})`} />
              <Area type="monotone" dataKey="score" stroke={HEX.primary} strokeWidth={2.5} fill="url(#score-fill)" animationDuration={1100}
                dot={(p) => (
                  <circle key={p.key} cx={p.cx} cy={p.cy} r={scores[p.index]?.kind === 'follow_up' ? 6 : 4}
                    fill={scores[p.index]?.kind === 'follow_up' ? HEX.secondary : '#fff'}
                    stroke={scores[p.index]?.kind === 'follow_up' ? '#fff' : HEX.primary} strokeWidth={2} />
                )} activeDot={{ r: 6 }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
        <p className="small muted">Purple points are follow-up assessments taken after an intervention.</p>
      </div>
      <div>
        <h3>Before and after each intervention</h3>
        {iv.length === 0 ? <Empty icon="activity">No evaluated interventions yet.</Empty> : (
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={iv} margin={{ top: 8, right: 12, left: -16, bottom: 0 }} barGap={4}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v) => `${v}%`} cursor={{ fill: 'rgba(59, 91, 219, 0.06)' }} />
              <Legend iconType="circle" />
              <Bar dataKey="pre" name="Before" fill="#b3bad0" radius={[6, 6, 0, 0]} maxBarSize={28} />
              <Bar dataKey="post" name="After" fill={HEX.primary} radius={[6, 6, 0, 0]} maxBarSize={28} />
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

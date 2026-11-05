import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, CATEGORY_LABEL, fmtDate, pct } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../components/icons.jsx'
import { Card, CategoryBadge, Empty, ErrorBox, HEX, HistoryTable, Loading, Meter, Stat, StatusBadge } from '../components/ui.jsx'

const OPEN = ['assigned', 'accessed', 'completed']

function Change({ pre, post }) {
  if (pre === null || pre === undefined || post === null || post === undefined) return null
  const d = Math.round(post - pre)
  const cls = d > 0 ? 'up' : d < 0 ? 'down' : 'flat'
  return <span className={`gain ${cls}`}>{d > 0 ? '+' : ''}{d} pts</span>
}

// One intervention: what was done, the score before and after, the result, and what EduPulse recommended next.
function TimelineItem({ r, next, index }) {
  const dot = r.category || (OPEN.includes(r.status) ? 'open' : '')
  const icon = r.category === 'positive' ? 'trend' : r.category === 'no_improvement' ? 'alert' : r.category ? 'activity' : 'clock'
  return (
    <li className="tl-item" style={{ animationDelay: `${Math.min(index, 8) * 0.05}s` }}>
      <span className={`tl-dot ${dot}`}><Icon name={icon} size={17} /></span>
      <div className="tl-card">
        <div className="tl-top">
          <div>
            <Link className="tl-title" to={`/interventions/${r.id}`}>{r.intervention_name}</Link>
            <div className="tl-meta">
              {fmtDate(r.assigned_at)} · {r.topic || 'General'}
              {r.selection_method === 'faculty_manual' ? ' · recorded by faculty' : ' · selected by Thompson sampling'}
            </div>
          </div>
          <div className="actions" style={{ alignItems: 'center' }}>
            {r.category ? <CategoryBadge category={r.category} /> : <StatusBadge status={r.status} />}
          </div>
        </div>
        {(r.pre_score !== null && r.pre_score !== undefined) && (
          <div className="tl-scores">
            <div className="ba-wrap">
              <div className="ba"><span>Before</span><div className="meter"><span className="before" style={{ width: `${Math.min(100, r.pre_score)}%` }} /></div><b>{pct(r.pre_score)}</b></div>
              <div className="ba"><span>After</span>{r.post_score === null || r.post_score === undefined
                ? <><div className="meter" /><b className="muted">—</b></>
                : <><Meter value={r.post_score} /><b>{pct(r.post_score)}</b></>}</div>
            </div>
            <Change pre={r.pre_score} post={r.post_score} />
            {r.learning_gain !== null && r.learning_gain !== undefined && <span className="small muted">gain g = {r.learning_gain.toFixed(2)}</span>}
          </div>
        )}
        {r.reason?.length > 0 && <div className="tl-reason"><strong>Why:</strong> {r.reason.join('; ')}</div>}
        {next && (
          <div className="tl-next">
            <Icon name="shuffle" size={15} />
            {next.intervention === r.intervention
              ? <>Next recommendation: continued with <strong>{next.intervention_name}</strong></>
              : <>Next recommendation switched to <strong>{next.intervention_name}</strong></>}
            {next.topic && <span className="muted">· {next.topic}</span>}
          </div>
        )}
      </div>
    </li>
  )
}

export default function History() {
  const { id } = useParams()
  const { session } = useAuth()
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [cat, setCat] = useState('all')
  const [view, setView] = useState('timeline')
  useEffect(() => { api(`/students/${id}/interventions`).then(setRows).catch((e) => setError(e.message)) }, [id])
  if (!rows) return error ? <ErrorBox error={error} /> : <Loading />

  // rows arrive newest first; "next" is the intervention selected after this one
  const nextOf = Object.fromEntries(rows.map((r, i) => [r.id, i > 0 ? rows[i - 1] : null]))
  const shown = rows.filter((r) => cat === 'all' || r.category === cat || (cat === 'pending' && !r.category))
  const counts = rows.reduce((m, r) => ({ ...m, [r.category || 'pending']: (m[r.category || 'pending'] || 0) + 1 }), {})
  const evaluated = rows.filter((r) => r.category)
  const completed = rows.filter((r) => ['completed', 'evaluated'].includes(r.status)).length
  const changes = evaluated.filter((r) => r.pre_score !== null && r.post_score !== null).map((r) => r.post_score - r.pre_score)
  const avgChange = changes.length ? changes.reduce((s, v) => s + v, 0) / changes.length : null
  const chart = [...evaluated].reverse().map((r) => ({ name: `#${r.id}`, pre: r.pre_score, post: r.post_score, title: r.intervention_name }))
  const switched = rows.slice(0, -1).filter((r, i) => r.intervention !== rows[i + 1].intervention).length

  return (
    <>
      <div className="page-head">
        <div>
          <Link className="back-link" to={session.user.role === 'student' ? '/student' : `/students/${id}`}><Icon name="arrowLeft" size={15} />Back</Link>
          <h1>Intervention history</h1>
          <p className="muted">{rows.length} interventions · {Object.entries(counts).map(([k, v]) => `${CATEGORY_LABEL[k] || 'Pending'} ${v}`).join(' · ') || 'none yet'}</p>
        </div>
      </div>

      <div className="stats">
        <Stat icon="layers" label="Interventions" value={rows.length} />
        <Stat icon="checkCircle" tone="ok" label="Activities completed" value={completed} />
        <Stat icon="award" tone="violet" label="Positive results" value={counts.positive || 0} hint={`of ${evaluated.length} evaluated`} />
        <Stat icon="trend" tone={avgChange === null ? '' : avgChange >= 0 ? 'ok' : 'bad'} label="Average score change"
          value={avgChange === null ? '—' : `${avgChange >= 0 ? '+' : ''}${avgChange.toFixed(1)} pts`} hint="after vs before, same topic" />
      </div>

      {chart.length > 0 && (
        <Card title="Before and after" subtitle="Topic score before each intervention and at the follow-up" icon="chart">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chart} margin={{ top: 8, right: 12, left: -16, bottom: 0 }} barGap={4}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v) => `${v}%`} labelFormatter={(n) => chart.find((c) => c.name === n)?.title} cursor={{ fill: 'rgba(59, 91, 219, 0.06)' }} />
              <Legend iconType="circle" />
              <Bar dataKey="pre" name="Before" fill="#b3bad0" radius={[6, 6, 0, 0]} maxBarSize={30} />
              <Bar dataKey="post" name="After" fill={HEX.primary} radius={[6, 6, 0, 0]} maxBarSize={30} />
            </BarChart>
          </ResponsiveContainer>
          {rows.length > 1 && (
            <p className="small muted">The recommendation changed type {switched} time{switched === 1 ? '' : 's'} across {rows.length - 1} follow-on selections, as the policy learned from each result.</p>
          )}
        </Card>
      )}

      <Card title={view === 'timeline' ? 'Timeline' : 'All interventions'} icon={view === 'timeline' ? 'clock' : 'list'} actions={
        <div className="filters">
          <div className="seg" role="group" aria-label="View">
            <button className={view === 'timeline' ? 'active' : ''} aria-pressed={view === 'timeline'} onClick={() => setView('timeline')}><Icon name="clock" size={14} />Timeline</button>
            <button className={view === 'table' ? 'active' : ''} aria-pressed={view === 'table'} onClick={() => setView('table')}><Icon name="list" size={14} />Table</button>
          </div>
          <select aria-label="Filter by response" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="all">All</option><option value="positive">Positive</option><option value="partial">Partial</option>
            <option value="no_improvement">No Improvement</option><option value="pending">Pending</option>
          </select>
        </div>}>
        {view === 'table' ? <HistoryTable rows={shown} /> : shown.length === 0 ? <Empty icon="clock">No interventions recorded yet.</Empty> : (
          <ol className="timeline">
            {shown.map((r, i) => <TimelineItem key={r.id} r={r} next={nextOf[r.id]} index={i} />)}
          </ol>
        )}
      </Card>
    </>
  )
}

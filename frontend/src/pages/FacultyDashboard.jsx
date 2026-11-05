import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, CATEGORY_LABEL, INTERVENTION_LABEL, STATE_LABEL, pct } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../components/icons.jsx'
import { Avatar, Card, Empty, ErrorBox, HEX, Loading, Meter, Num, Stat, StateBadge, StatusBadge } from '../components/ui.jsx'
import ImportRecords from '../components/ImportRecords.jsx'

// Where each intervention is in the cycle; the counts come straight from the stored statuses.
const PIPELINE = [
  ['assigned', 'Assigned', HEX.primary], ['accessed', 'In progress', HEX.secondary],
  ['completed', 'Awaiting follow-up', HEX.partial], ['evaluated', 'Evaluated', HEX.positive],
]
const SEVERITY = { high_support_need: 0, attention_needed: 1, normal: 2 }
const SORTS = {
  attention: (a, b) => (SEVERITY[a.state?.state] ?? 3) - (SEVERITY[b.state?.state] ?? 3) || (b.no_improvement_streak || 0) - (a.no_improvement_streak || 0),
  name: (a, b) => a.name.localeCompare(b.name),
  score: (a, b) => (a.state?.features?.latest_score ?? 999) - (b.state?.features?.latest_score ?? 999),
}

function MeterCell({ value }) {
  if (value === null || value === undefined) return <span className="muted">—</span>
  return <div className="cell-meter"><span className="v">{pct(value)}</span><Meter value={value} /></div>
}

export default function FacultyDashboard() {
  const { session } = useAuth()
  const [students, setStudents] = useState(null)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('attention')
  const [q, setQ] = useState('')
  const [showImport, setShowImport] = useState(false)

  const load = () => Promise.all([api('/students'), api('/dashboard/summary')])
    .then(([s, d]) => { setStudents(s); setSummary(d) })
    .catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const rows = useMemo(() => (students || []).filter((s) =>
    (filter === 'all' || (filter === 'review' ? (s.state?.state === 'high_support_need' || s.no_improvement_streak >= 2) : s.state?.state === filter)) &&
    (!q || `${s.name} ${s.roll_number}`.toLowerCase().includes(q.toLowerCase()))).sort(SORTS[sort]), [students, filter, q, sort])

  if (!students) return error ? <ErrorBox error={error} /> : <Loading />
  const st = summary.intervention_status
  const stateData = Object.entries(summary.state_distribution).map(([k, v]) => ({ name: STATE_LABEL[k] || k, key: k, value: v }))
  const catData = ['positive', 'partial', 'no_improvement'].map((k) => ({ name: CATEGORY_LABEL[k], key: k, value: summary.response_categories[k] || 0 }))
  const typeData = Object.entries(summary.interventions_by_type).map(([k, v]) => ({ name: INTERVENTION_LABEL[k].split(' ').slice(-2).join(' '), value: v }))
  const evaluated = catData.reduce((s, d) => s + d.value, 0)
  const open = (st.assigned || 0) + (st.accessed || 0) + (st.completed || 0)
  const tracked = PIPELINE.reduce((s, [k]) => s + (st[k] || 0), 0)
  const positiveRate = evaluated ? Math.round((100 * (summary.response_categories.positive || 0)) / evaluated) : null

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{session.user.role === 'admin' ? 'All students' : 'My students'}</h1>
          <p className="muted">Academic states, open support and outcomes for the students you are responsible for.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => setShowImport(!showImport)}><Icon name="upload" size={16} />Import records</button>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="stats">
        <Stat icon="users" label="Assigned students" value={summary.student_count} />
        <Stat icon="alert" tone="bad" label="Need review" value={summary.students_needing_review.length} hint="High support need or ≥2 no-improvement results" />
        <Stat icon="zap" tone="warn" label="Open interventions" value={open} />
        <Stat icon="checkCircle" tone="ok" label="Evaluated responses" value={evaluated} />
        <Stat icon="trend" tone="violet" label="Positive responses" value={positiveRate === null ? '—' : positiveRate} suffix="%" hint={evaluated ? `of ${evaluated} evaluated` : 'none evaluated yet'} />
      </div>

      {showImport && (
        <Card title="Import academic records (CSV)" icon="upload" actions={<button className="btn ghost small" onClick={() => setShowImport(false)}>Close</button>}>
          <ImportRecords onImported={load} />
        </Card>
      )}

      <div className="grid-2 wide-left">
        <Card title="Intervention tracking" subtitle="Where every intervention is in the support cycle" icon="layers">
          <div className="pipeline">
            {PIPELINE.map(([k, label, color]) => (
              <div key={k} className="pipe">
                <div className="pipe-n"><Num value={st[k] || 0} /></div>
                <div className="pipe-l"><i style={{ background: color }} />{label}</div>
              </div>
            ))}
          </div>
          {tracked > 0 && (
            <div className="segbar" aria-hidden>
              {PIPELINE.map(([k, , color]) => <span key={k} style={{ width: `${(100 * (st[k] || 0)) / tracked}%`, background: color }} />)}
            </div>
          )}
          <p className="small muted" style={{ marginTop: 8 }}>
            {summary.pending_faculty_support.length
              ? `${summary.pending_faculty_support.length} faculty support consultation(s) still to be held.`
              : 'No faculty support consultations pending.'}
          </p>
        </Card>
        <Card title="State distribution" icon="activity">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={stateData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={3} cornerRadius={6} animationDuration={900}>
                {stateData.map((d) => <Cell key={d.key} fill={HEX[d.key]} stroke="none" />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="legend">{stateData.map((d) => <span key={d.key}><i style={{ background: HEX[d.key] }} />{d.name} ({d.value})</span>)}</div>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Response categories" icon="award">
          {evaluated === 0 ? <Empty icon="award">No responses evaluated yet.</Empty> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={catData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(59, 91, 219, 0.06)' }} />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={56}>{catData.map((d) => <Cell key={d.key} fill={HEX[d.key]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Interventions by type" icon="chart">
          {typeData.length === 0 ? <Empty icon="chart">No interventions yet.</Empty> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={typeData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(59, 91, 219, 0.06)' }} /><Bar dataKey="value" fill={HEX.primary} radius={[8, 8, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {summary.students_needing_review.length > 0 && (
        <Card title="Students who may need additional support" icon="alert" className="attention">
          <ul className="plain">
            {summary.students_needing_review.map((s) => (
              <li key={s.student_id} className="cell-user">
                <Avatar name={s.name} size="sm" />
                <Link to={`/students/${s.student_id}`}>{s.name}</Link> <span className="muted small">{s.roll_number}</span>
                <StateBadge state={s.state} />
                {s.no_improvement_streak >= 2 && <span className="badge no_improvement">{s.no_improvement_streak}× no improvement in a row</span>}
              </li>
            ))}
          </ul>
          <p className="small muted" style={{ marginTop: 10 }}>Consider recording faculty support from the student page. Final decisions remain with faculty.</p>
        </Card>
      )}

      <Card title="Students" subtitle={`${rows.length} of ${students.length} shown`} icon="users" actions={
        <div className="filters">
          <span className="search"><Icon name="search" size={15} />
            <input aria-label="Search students" placeholder="Search name or roll no." value={q} onChange={(e) => setQ(e.target.value)} /></span>
          <select aria-label="Filter by state" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All states</option><option value="review">Needs review</option>
            <option value="high_support_need">High support need</option><option value="attention_needed">Attention needed</option>
            <option value="normal">Normal</option>
          </select>
          <select aria-label="Sort students" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="attention">Most support needed first</option><option value="score">Lowest latest score first</option><option value="name">Name A–Z</option>
          </select>
        </div>}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Student</th><th>State</th><th>Latest score</th><th>Attendance</th><th>Completion</th><th>Open intervention</th><th>Streak</th></tr></thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td><div className="cell-user"><Avatar name={s.name} size="sm" />
                    <div><Link to={`/students/${s.id}`}>{s.name}</Link><div className="small muted">{s.roll_number}</div></div></div></td>
                  <td><StateBadge state={s.state?.state} /></td>
                  <td><MeterCell value={s.state?.features?.latest_score} /></td>
                  <td><MeterCell value={s.state?.features?.attendance_pct} /></td>
                  <td><MeterCell value={s.state?.features?.assignment_completion_pct} /></td>
                  <td>{s.open_intervention ? <><div className="small">{s.open_intervention.intervention_name}</div><StatusBadge status={s.open_intervention.status} /></> : <span className="muted">—</span>}</td>
                  <td>{s.no_improvement_streak ? <span className="badge no_improvement">{s.no_improvement_streak}</span> : ''}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={7} className="muted">No students match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

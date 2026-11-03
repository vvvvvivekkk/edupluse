import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, CATEGORY_LABEL, INTERVENTION_LABEL, STATE_LABEL, pct } from '../api.js'
import { useAuth } from '../App.jsx'
import { Card, ErrorBox, HEX, Loading, Stat, StateBadge, StatusBadge } from '../components/ui.jsx'
import ImportRecords from '../components/ImportRecords.jsx'

export default function FacultyDashboard() {
  const { session } = useAuth()
  const [students, setStudents] = useState(null)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [showImport, setShowImport] = useState(false)

  const load = () => Promise.all([api('/students'), api('/dashboard/summary')])
    .then(([s, d]) => { setStudents(s); setSummary(d) })
    .catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const rows = useMemo(() => (students || []).filter((s) =>
    (filter === 'all' || (filter === 'review' ? (s.state?.state === 'high_support_need' || s.no_improvement_streak >= 2) : s.state?.state === filter)) &&
    (!q || `${s.name} ${s.roll_number}`.toLowerCase().includes(q.toLowerCase()))), [students, filter, q])

  if (!students) return error ? <ErrorBox error={error} /> : <Loading />
  const stateData = Object.entries(summary.state_distribution).map(([k, v]) => ({ name: STATE_LABEL[k] || k, key: k, value: v }))
  const catData = ['positive', 'partial', 'no_improvement'].map((k) => ({ name: CATEGORY_LABEL[k], key: k, value: summary.response_categories[k] || 0 }))
  const typeData = Object.entries(summary.interventions_by_type).map(([k, v]) => ({ name: INTERVENTION_LABEL[k].split(' ').slice(-2).join(' '), value: v }))
  const evaluated = catData.reduce((s, d) => s + d.value, 0)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{session.user.role === 'admin' ? 'All students' : 'My students'}</h1>
          <p className="muted">Academic states, open support and outcomes for the students you are responsible for.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="stats">
        <Stat label="Assigned students" value={summary.student_count} />
        <Stat label="Need review" value={summary.students_needing_review.length} hint="High support need or ≥2 no-improvement results" />
        <Stat label="Open interventions" value={(summary.intervention_status.assigned || 0) + (summary.intervention_status.accessed || 0) + (summary.intervention_status.completed || 0)} />
        <Stat label="Evaluated responses" value={evaluated} />
      </div>

      <div className="grid-3">
        <Card title="State distribution">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={stateData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={2}>
                {stateData.map((d) => <Cell key={d.key} fill={HEX[d.key]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="legend">{stateData.map((d) => <span key={d.key}><i style={{ background: HEX[d.key] }} />{d.name} ({d.value})</span>)}</div>
        </Card>
        <Card title="Response categories">
          {evaluated === 0 ? <p className="muted">No responses evaluated yet.</p> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={catData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>{catData.map((d) => <Cell key={d.key} fill={HEX[d.key]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Interventions by type">
          {typeData.length === 0 ? <p className="muted">No interventions yet.</p> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={typeData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} />
                <Tooltip /><Bar dataKey="value" fill={HEX.primary} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {summary.students_needing_review.length > 0 && (
        <Card title="Students who may need additional support" className="attention">
          <ul className="plain">
            {summary.students_needing_review.map((s) => (
              <li key={s.student_id}>
                <Link to={`/students/${s.student_id}`}>{s.name}</Link> ({s.roll_number}) · <StateBadge state={s.state} />
                {s.no_improvement_streak >= 2 && <span className="badge no_improvement">{s.no_improvement_streak}× no improvement in a row</span>}
              </li>
            ))}
          </ul>
          <p className="small muted">Consider recording faculty support from the student page. Final decisions remain with faculty.</p>
        </Card>
      )}

      <Card title="Students" actions={
        <div className="filters">
          <input placeholder="Search name or roll no." value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All states</option><option value="review">Needs review</option>
            <option value="high_support_need">High support need</option><option value="attention_needed">Attention needed</option>
            <option value="normal">Normal</option>
          </select>
        </div>}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Student</th><th>Roll no.</th><th>State</th><th>Latest score</th><th>Attendance</th><th>Completion</th><th>Open intervention</th><th>Streak</th></tr></thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td><Link to={`/students/${s.id}`}>{s.name}</Link></td>
                  <td>{s.roll_number}</td>
                  <td><StateBadge state={s.state?.state} /></td>
                  <td>{pct(s.state?.features?.latest_score)}</td>
                  <td>{pct(s.state?.features?.attendance_pct)}</td>
                  <td>{pct(s.state?.features?.assignment_completion_pct)}</td>
                  <td>{s.open_intervention ? <>{s.open_intervention.intervention_name} <StatusBadge status={s.open_intervention.status} /></> : <span className="muted">—</span>}</td>
                  <td>{s.no_improvement_streak || ''}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={8} className="muted">No students match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Import academic records (CSV)" actions={<button className="btn ghost small" onClick={() => setShowImport(!showImport)}>{showImport ? 'Hide' : 'Show'}</button>}>
        {showImport ? <ImportRecords onImported={load} /> : <p className="muted small">Bulk-enter assessment results, attendance, assignment statuses and practice activity for your students from a CSV file.</p>}
      </Card>
    </>
  )
}

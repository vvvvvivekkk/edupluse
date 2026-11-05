import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, CATEGORY_LABEL, INTERVENTION_LABEL } from '../api.js'
import { Card, Empty as EmptyBox, ErrorBox, HEX, Loading } from '../components/ui.jsx'

const Empty = ({ text = 'No data recorded yet.' }) => <EmptyBox icon="chart">{text}</EmptyBox>

export default function Analytics() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api('/analytics').then(setD).catch((e) => setError(e.message)) }, [])
  if (!d) return error ? <ErrorBox error={error} /> : <Loading />

  const counts = Object.entries(d.intervention_counts).map(([k, v]) => ({ name: INTERVENTION_LABEL[k], value: v }))
  const cats = ['positive', 'partial', 'no_improvement'].map((k) => ({ key: k, name: CATEGORY_LABEL[k], value: d.response_categories[k] || 0 }))
  const changes = d.score_changes.map((c) => ({ name: `#${c.assignment_id}`, pre: c.pre, post: c.post, change: +(c.post - c.pre).toFixed(1) }))
  const asg = ['submitted', 'late', 'missing'].map((k) => ({ name: k, value: d.assignment_status[k] || 0 }))

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Analytics</h1>
          <p className="muted">All charts are computed from records stored in the system for the students you can access.</p>
        </div>
      </div>
      <div className="grid-2">
        <Card title="Average assessment score over time" icon="trend">
          {d.avg_score_over_time.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={d.avg_score_over_time} margin={{ left: -16, right: 12 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} />
                <Tooltip formatter={(v, n, p) => [`${v}% (n=${p.payload.n})`, 'Average']} />
                <Line type="monotone" dataKey="avg_score" stroke={HEX.primary} strokeWidth={2.5} dot={{ r: 3, fill: "#fff", strokeWidth: 2 }} activeDot={{ r: 6 }} animationDuration={1100} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Assessment-score change per evaluated intervention" icon="activity">
          {changes.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={changes} margin={{ left: -16 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis />
                <Tooltip formatter={(v, n, p) => [`${v} points (${p.payload.pre}% → ${p.payload.post}%)`, 'Change']} />
                <Bar dataKey="change" radius={[4, 4, 0, 0]}>{changes.map((c) => <Cell key={c.name} fill={c.change >= 0 ? HEX.positive : HEX.no_improvement} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No evaluated interventions yet." />}
        </Card>
        <Card title="Assignment completion" icon="checkCircle">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={asg} margin={{ left: -16 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={56}>{asg.map((a) => <Cell key={a.name} fill={a.name === 'missing' ? HEX.no_improvement : a.name === 'late' ? HEX.partial : HEX.positive} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Intervention counts" icon="layers">
          {counts.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={counts} layout="vertical" margin={{ left: 60 }}>
                <CartesianGrid stroke="var(--grid)" horizontal={false} />
                <XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={120} />
                <Tooltip /><Bar dataKey="value" fill={HEX.primary} radius={[0, 8, 8, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Response categories" icon="award">
          {cats.some((c) => c.value) ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={cats} margin={{ left: -16 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={56}>{cats.map((c) => <Cell key={c.key} fill={HEX[c.key]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Intervention outcomes over time" icon="calendar">
          {d.outcomes_over_time.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={d.outcomes_over_time} margin={{ left: -16 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Legend />
                <Bar dataKey="positive" stackId="a" name="Positive" fill={HEX.positive} />
                <Bar dataKey="partial" stackId="a" name="Partial" fill={HEX.partial} />
                <Bar dataKey="no_improvement" stackId="a" name="No Improvement" fill={HEX.no_improvement} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
      </div>
      <Card title="Effectiveness by intervention type" icon="target">
        <p className="small">{d.comparison_note}</p>
        <table className="compact">
          <thead><tr><th>Intervention</th><th>Evaluated outcomes</th><th>Mean reward</th></tr></thead>
          <tbody>
            {d.type_summary.map((t) => (
              <tr key={t.intervention}><td>{INTERVENTION_LABEL[t.intervention]}</td><td>{t.n_evaluated}</td>
                <td>{t.sufficient_data ? t.mean_reward : <span className="muted">insufficient data</span>}</td></tr>
            ))}
            {d.type_summary.length === 0 && <tr><td colSpan={3} className="muted">No evaluated outcomes yet.</td></tr>}
          </tbody>
        </table>
      </Card>
    </>
  )
}

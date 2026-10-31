import { useEffect, useState } from 'react'
import { api, fmtDateTime, INTERVENTION_LABEL } from '../api.js'
import { Card, ErrorBox, Loading, Stat } from '../components/ui.jsx'

const TABS = ['Overview', 'Users', 'Faculty assignments', 'Interventions', 'Configuration', 'Policy', 'Audit log']

function useLoad(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const reload = () => api(path).then(setData).catch((e) => setError(e.message))
  useEffect(() => { reload() }, deps)
  return [data, error, reload]
}

function Msg({ m }) { return m ? <div className={`alert ${m.ok ? 'ok' : 'error'}`}>{m.text}</div> : null }

function Overview() {
  const [d, error] = useLoad('/dashboard/summary')
  if (!d) return error ? <ErrorBox error={error} /> : <Loading />
  const a = d.admin
  return (
    <>
      <div className="stats">
        <Stat label="Registered users" value={a.users_total} />
        <Stat label="Students / Faculty / Admins" value={`${a.users_by_role.student || 0} / ${a.users_by_role.faculty || 0} / ${a.users_by_role.admin || 0}`} />
        <Stat label="Interventions" value={Object.values(d.intervention_status).reduce((s, v) => s + v, 0)} />
        <Stat label="Policy version" value={`v${a.policy_version}`} hint={`${a.policy_updates} updates`} />
      </div>
      <Card title="Recent system activity">
        <table className="compact">
          <thead><tr><th>When</th><th>Action</th><th>Entity</th><th>User</th></tr></thead>
          <tbody>{a.recent_activity.map((r, i) => <tr key={i}><td>{fmtDateTime(r.at)}</td><td>{r.action}</td><td>{r.entity} {r.entity_id}</td><td>{r.user_id ?? 'system'}</td></tr>)}</tbody>
        </table>
      </Card>
    </>
  )
}

function Users() {
  const [users, error, reload] = useLoad('/admin/users')
  const [f, setF] = useState({ role: 'student' })
  const [m, setM] = useState(null)
  async function create(e) {
    e.preventDefault()
    try {
      await api('/admin/users', { method: 'POST', body: { ...f, previous_result_pct: f.previous_result_pct ? Number(f.previous_result_pct) : null } })
      setM({ ok: true, text: 'User created.' }); setF({ role: 'student' }); reload()
    } catch (err) { setM({ ok: false, text: err.message }) }
  }
  async function toggle(u) {
    try { await api(`/admin/users/${u.id}`, { method: 'PATCH', body: { is_active: !u.is_active } }); reload() } catch (err) { setM({ ok: false, text: err.message }) }
  }
  if (!users) return error ? <ErrorBox error={error} /> : <Loading />
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <>
      <Card title="Create user">
        <form className="record-form" onSubmit={create}>
          <label>Full name<input value={f.full_name || ''} onChange={set('full_name')} /></label>
          <label>Email<input type="email" value={f.email || ''} onChange={set('email')} /></label>
          <label>Initial password<input type="password" value={f.password || ''} onChange={set('password')} placeholder="min 8 characters" /></label>
          <label>Role<select value={f.role} onChange={set('role')}><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Admin</option></select></label>
          {f.role === 'student' && <><label>Roll number<input value={f.roll_number || ''} onChange={set('roll_number')} /></label>
            <label>Previous result % (optional)<input type="number" min="0" max="100" value={f.previous_result_pct || ''} onChange={set('previous_result_pct')} /></label></>}
          {f.role === 'faculty' && <label>Department<input value={f.department || ''} onChange={set('department')} /></label>}
          <button className="btn primary">Create</button>
        </form>
        <Msg m={m} />
      </Card>
      <Card title={`Users (${users.length})`}>
        <div className="table-wrap"><table>
          <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Profile id</th><th>Status</th><th /></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td>{u.id}</td><td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td>
              <td>{u.student_id ? `student ${u.student_id}` : u.faculty_id ? `faculty ${u.faculty_id}` : '—'}</td>
              <td>{u.is_active ? 'active' : <span className="muted">deactivated</span>}</td>
              <td><button className="btn ghost small" onClick={() => toggle(u)}>{u.is_active ? 'Deactivate' : 'Activate'}</button></td></tr>
          ))}</tbody>
        </table></div>
      </Card>
    </>
  )
}

function FacultyAssignments() {
  const [rows, error, reload] = useLoad('/admin/faculty-assignments')
  const [users] = useLoad('/admin/users')
  const [f, setF] = useState({})
  const [m, setM] = useState(null)
  if (!rows || !users) return error ? <ErrorBox error={error} /> : <Loading />
  const fac = users.filter((u) => u.faculty_id), stu = users.filter((u) => u.student_id)
  const name = (list, key, id) => list.find((u) => u[key] === id)?.full_name || id
  async function add(e) {
    e.preventDefault()
    try { await api('/admin/faculty-assignments', { method: 'POST', body: { faculty_id: Number(f.faculty_id), student_id: Number(f.student_id) } }); setM({ ok: true, text: 'Assigned.' }); reload() } catch (err) { setM({ ok: false, text: err.message }) }
  }
  return (
    <>
      <Card title="Assign a student to a faculty member">
        <form className="record-form" onSubmit={add}>
          <label>Faculty<select value={f.faculty_id || ''} onChange={(e) => setF({ ...f, faculty_id: e.target.value })}><option value="">Select…</option>{fac.map((u) => <option key={u.id} value={u.faculty_id}>{u.full_name}</option>)}</select></label>
          <label>Student<select value={f.student_id || ''} onChange={(e) => setF({ ...f, student_id: e.target.value })}><option value="">Select…</option>{stu.map((u) => <option key={u.id} value={u.student_id}>{u.full_name}</option>)}</select></label>
          <button className="btn primary">Assign</button>
        </form>
        <Msg m={m} />
      </Card>
      <Card title="Current assignments">
        <table className="compact"><thead><tr><th>Faculty</th><th>Student</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.id}><td>{name(fac, 'faculty_id', r.faculty_id)}</td><td>{name(stu, 'student_id', r.student_id)}</td></tr>)}</tbody></table>
      </Card>
    </>
  )
}

function Interventions() {
  const [types, error, reloadTypes] = useLoad('/interventions/types')
  const [resources, , reloadRes] = useLoad('/admin/resources')
  const [topics] = useLoad('/topics')
  const [f, setF] = useState({ intervention_type: 'targeted_material' })
  const [m, setM] = useState(null)
  if (!types || !resources || !topics) return error ? <ErrorBox error={error} /> : <Loading />
  async function toggleType(t) { await api(`/admin/intervention-types/${t.id}`, { method: 'PATCH', body: { is_active: !t.is_active } }); reloadTypes() }
  async function toggleRes(r) { await api(`/admin/resources/${r.id}`, { method: 'PATCH', body: { is_active: !r.is_active } }); reloadRes() }
  async function add(e) {
    e.preventDefault()
    try {
      await api('/admin/resources', { method: 'POST', body: { ...f, topic_id: f.topic_id ? Number(f.topic_id) : null } })
      setM({ ok: true, text: 'Resource added.' }); setF({ intervention_type: 'targeted_material' }); reloadRes()
    } catch (err) { setM({ ok: false, text: err.message }) }
  }
  const tname = (id) => topics.find((t) => t.id === id)?.name || 'General'
  return (
    <>
      <Card title="Intervention categories">
        <table className="compact"><thead><tr><th>Code</th><th>Name</th><th>Description</th><th>Active</th><th /></tr></thead>
          <tbody>{types.map((t) => <tr key={t.id}><td>{t.code}</td><td>{t.name}</td><td className="small">{t.description}</td><td>{t.is_active ? 'yes' : 'no'}</td>
            <td><button className="btn ghost small" onClick={() => toggleType(t)}>{t.is_active ? 'Disable' : 'Enable'}</button></td></tr>)}</tbody></table>
        <p className="small muted">Disabled categories are removed from every eligible set (exclusion X2).</p>
      </Card>
      <Card title="Add learning resource">
        <form className="record-form" onSubmit={add}>
          <label>Category<select value={f.intervention_type} onChange={(e) => setF({ ...f, intervention_type: e.target.value })}>{types.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}</select></label>
          <label>Topic<select value={f.topic_id || ''} onChange={(e) => setF({ ...f, topic_id: e.target.value })}><option value="">General</option>{topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
          <label>Title<input value={f.title || ''} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
          <label>Objective<input value={f.objective || ''} onChange={(e) => setF({ ...f, objective: e.target.value })} /></label>
          <label>Link (optional)<input value={f.url || ''} onChange={(e) => setF({ ...f, url: e.target.value })} /></label>
          <label>Instructions<input value={f.instructions || ''} onChange={(e) => setF({ ...f, instructions: e.target.value })} /></label>
          <button className="btn primary">Add</button>
        </form>
        <Msg m={m} />
      </Card>
      <Card title={`Learning resources (${resources.length})`}>
        <div className="table-wrap"><table className="compact"><thead><tr><th>Title</th><th>Category</th><th>Topic</th><th>Content</th><th>Active</th><th /></tr></thead>
          <tbody>{resources.map((r) => <tr key={r.id}><td>{r.url ? <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> : r.title}</td>
            <td>{INTERVENTION_LABEL[r.intervention_type]}</td><td>{tname(r.topic_id)}</td>
            <td className="small">{r.content?.questions ? `${r.content.questions.length} questions` : r.content?.days ? `${r.content.days.length}-day plan` : '—'}</td>
            <td>{r.is_active ? 'yes' : 'no'}</td><td><button className="btn ghost small" onClick={() => toggleRes(r)}>{r.is_active ? 'Disable' : 'Enable'}</button></td></tr>)}</tbody></table></div>
      </Card>
    </>
  )
}

const CFG_HELP = {
  reward_alpha: 'α in r = α·g + (1−α)·e (0–1)', positive_threshold: 'r ≥ this → Positive', partial_threshold: 'r ≥ this → Partial',
  lints_lambda: 'Prior precision λ (applies to new policy versions)', lints_v: 'Posterior scale v (applies to new policy versions)',
  low_score_threshold: 'Topic score below this counts as low (%)', weak_mastery_threshold: 'Practice accuracy below this = weak mastery (%)',
  low_attendance_threshold: 'Attendance below this = low engagement (%)', low_completion_threshold: 'Assignment completion below this (%)',
  no_improvement_streak: 'Consecutive No Improvement results that trigger rule R4', engagement_window_days: 'Engagement observation window (days)',
}

function Configuration() {
  const [d, error, reload] = useLoad('/admin/config')
  const [cfg, setCfg] = useState(null)
  const [rules, setRules] = useState('')
  const [m, setM] = useState(null)
  useEffect(() => { if (d) { setCfg(d.policy_config); setRules(JSON.stringify(d.eligibility_rules, null, 2)) } }, [d])
  if (!d || !cfg) return error ? <ErrorBox error={error} /> : <Loading />
  async function saveCfg(e) {
    e.preventDefault()
    try { await api('/admin/config', { method: 'PUT', body: Object.fromEntries(Object.entries(cfg).map(([k, v]) => [k, Number(v)])) }); setM({ ok: true, text: 'Configuration saved (audited).' }); reload() } catch (err) { setM({ ok: false, text: err.message }) }
  }
  async function saveRules() {
    try { await api('/admin/eligibility-rules', { method: 'PUT', body: { rules: JSON.parse(rules) } }); setM({ ok: true, text: 'Eligibility rules saved (audited).' }); reload() } catch (err) { setM({ ok: false, text: err.message.startsWith('Unexpected') ? `Invalid JSON: ${err.message}` : err.message }) }
  }
  return (
    <>
      <Msg m={m} />
      <Card title="Policy and evaluation parameters">
        <form onSubmit={saveCfg} className="cfg-grid">
          {Object.keys(cfg).map((k) => (
            <label key={k}><code>{k}</code><input type="number" step="any" value={cfg[k]} onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })} /><span className="small muted">{CFG_HELP[k]}</span></label>
          ))}
          <div><button className="btn primary">Save parameters</button></div>
        </form>
      </Card>
      <Card title="Eligibility rules (JSON)">
        <p className="small muted">Each rule lists conditions on indicators (state, topic_score, topic_mastery, attendance_pct, assignment_completion_pct, no_improvement_streak) and the interventions it makes eligible. Thresholds can reference parameters above via "ref". Rules are validated before saving.</p>
        <textarea className="code" rows={22} value={rules} onChange={(e) => setRules(e.target.value)} spellCheck={false} />
        <button className="btn primary" onClick={saveRules}>Save rules</button>
      </Card>
    </>
  )
}

function Policy() {
  const [d, error, reload] = useLoad('/admin/policy')
  const [reason, setReason] = useState('')
  const [m, setM] = useState(null)
  if (!d) return error ? <ErrorBox error={error} /> : <Loading />
  async function reinit() {
    if (!window.confirm('Start a new policy version from the prior? Existing versions and history are kept.')) return
    try { const r = await api('/admin/policy/reinitialise', { method: 'POST', body: { reason } }); setM({ ok: true, text: `Created policy v${r.version}.` }); reload() } catch (err) { setM({ ok: false, text: err.message }) }
  }
  return (
    <>
      <Card title={`Linear Thompson sampling policy — v${d.current_version}`}>
        <p className="small">λ = {d.lambda}, v = {d.v}. Posterior mean θ per intervention (expected reward = context · θ):</p>
        <div className="table-wrap"><table className="compact">
          <thead><tr><th>Intervention</th><th>n</th>{d.context_features.map((f) => <th key={f} className="small">{f}</th>)}</tr></thead>
          <tbody>{d.arms.map((a) => <tr key={a.intervention}><td>{INTERVENTION_LABEL[a.intervention] || a.intervention}</td><td>{a.n_observations}</td>
            {d.context_features.map((f) => <td key={f}>{a.posterior_mean_theta[f]}</td>)}</tr>)}</tbody>
        </table></div>
      </Card>
      <div className="grid-2">
        <Card title="Policy-update history">
          {d.updates.length === 0 ? <p className="muted">No updates yet.</p> : (
            <table className="compact"><thead><tr><th>When</th><th>Intervention #</th><th>Reward</th><th>Version</th></tr></thead>
              <tbody>{d.updates.map((u) => <tr key={u.assignment_id}><td>{fmtDateTime(u.created_at)}</td><td>{u.assignment_id}</td><td>{u.reward}</td><td>v{u.from_version} → v{u.to_version}</td></tr>)}</tbody></table>)}
        </Card>
        <Card title="Versions">
          <table className="compact"><thead><tr><th>Version</th><th>Reason</th><th>Created</th></tr></thead>
            <tbody>{d.versions.map((v) => <tr key={v.version}><td>v{v.version}</td><td className="small">{v.reason}</td><td>{fmtDateTime(v.created_at)}</td></tr>)}</tbody></table>
          <div className="inline-form">
            <label className="small">Reason<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. changed λ" /></label>
            <button className="btn ghost" onClick={reinit} disabled={reason.length < 3}>Re-initialise policy</button>
          </div>
          <Msg m={m} />
        </Card>
      </div>
    </>
  )
}

function Audit() {
  const [rows, error] = useLoad('/admin/audit?limit=200')
  if (!rows) return error ? <ErrorBox error={error} /> : <Loading />
  return (
    <Card title="Audit log (latest 200)">
      <div className="table-wrap"><table className="compact">
        <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id}><td>{fmtDateTime(r.created_at)}</td><td>{r.user_id ?? 'system'}</td><td>{r.action}</td><td>{r.entity} {r.entity_id}</td>
          <td className="small mono">{JSON.stringify(r.details).slice(0, 140)}</td></tr>)}</tbody>
      </table></div>
    </Card>
  )
}

export default function Admin() {
  const [tab, setTab] = useState('Overview')
  const View = { Overview, Users, 'Faculty assignments': FacultyAssignments, Interventions, Configuration, Policy, 'Audit log': Audit }[tab]
  return (
    <>
      <div className="page-head"><div><h1>Administration</h1><p className="muted">Users, content, configuration and the adaptive policy. All changes are audited.</p></div></div>
      <div className="tabs" role="tablist">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}
      </div>
      <View />
    </>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDateTime, INTERVENTION_LABEL } from '../api.js'
import { Icon } from '../components/icons.jsx'
import { Avatar, Card, ErrorBox, Loading, Meter, Stat } from '../components/ui.jsx'

const TABS = ['Overview', 'Users', 'Faculty assignments', 'Interventions', 'Configuration', 'Policy', 'Audit log']
const TAB_ICON = {
  Overview: 'home', Users: 'users', 'Faculty assignments': 'link', Interventions: 'book', Configuration: 'sliders',
  Policy: 'cpu', 'Audit log': 'file',
}

function useLoad(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const reload = () => api(path).then(setData).catch((e) => setError(e.message))
  useEffect(() => { reload() }, deps)
  return [data, error, reload]
}

function Msg({ m }) {
  return m ? <div className={`alert ${m.ok ? 'ok' : 'error'}`}><Icon name={m.ok ? 'checkCircle' : 'alert'} size={16} />{m.text}</div> : null
}

function Overview({ go }) {
  const [d, error] = useLoad('/dashboard/summary')
  if (!d) return error ? <ErrorBox error={error} /> : <Loading />
  const a = d.admin
  const roles = [['student', 'Students'], ['faculty', 'Faculty'], ['admin', 'Admins']]
  const states = [['normal', 'Normal'], ['attention_needed', 'Attention'], ['high_support_need', 'High support'], ['not_assessed', 'Not assessed']]
  const stateColor = { normal: 'var(--ok)', attention_needed: 'var(--warn)', high_support_need: 'var(--bad)', not_assessed: '#9aa3b2' }
  return (
    <>
      <div className="stats">
        <Stat icon="users" label="Registered users" value={a.users_total} hint={`${a.users_by_role.student || 0} students · ${a.users_by_role.faculty || 0} faculty · ${a.users_by_role.admin || 0} admins`} />
        <Stat icon="zap" tone="warn" label="Interventions" value={Object.values(d.intervention_status).reduce((s, v) => s + v, 0)} />
        <Stat icon="cpu" tone="violet" label="Policy version" value={`v${a.policy_version}`} hint={`${a.policy_updates} updates`} />
        <Stat icon="file" tone="ok" label="Audit events" value={a.audit_events} />
      </div>
      <div className="grid-2">
        <Card title="Users by role" icon="users" actions={<button className="btn ghost small" onClick={() => go('Users')}>Manage users<Icon name="arrowRight" size={14} /></button>}>
          <div className="bar-list">
            {roles.map(([k, label]) => (
              <div key={k} className="bar-row"><span>{label}</span><Meter value={(100 * (a.users_by_role[k] || 0)) / (a.users_total || 1)} /><b>{a.users_by_role[k] || 0}</b></div>
            ))}
          </div>
        </Card>
        <Card title="Students by academic state" icon="activity" actions={<Link className="btn ghost small" to="/faculty">All students<Icon name="arrowRight" size={14} /></Link>}>
          <div className="bar-list">
            {states.map(([k, label]) => (
              <div key={k} className="bar-row"><span>{label}</span><Meter value={(100 * (d.state_distribution[k] || 0)) / (d.student_count || 1)} color={stateColor[k]} /><b>{d.state_distribution[k] || 0}</b></div>
            ))}
          </div>
        </Card>
      </div>
      <Card title="Recent system activity" icon="clock" actions={<button className="btn ghost small" onClick={() => go('Audit log')}>Full audit log<Icon name="arrowRight" size={14} /></button>}>
        <div className="table-wrap"><table className="compact">
          <thead><tr><th>When</th><th>Action</th><th>Entity</th><th>User</th></tr></thead>
          <tbody>{a.recent_activity.map((r, i) => <tr key={i}><td>{fmtDateTime(r.at)}</td><td><code>{r.action}</code></td><td>{r.entity} {r.entity_id}</td><td>{r.user_id ?? 'system'}</td></tr>)}</tbody>
        </table></div>
      </Card>
    </>
  )
}

// Role assignment. A profile is created when the new role needs one (students need a roll number);
// existing profiles and their history are always kept.
function RoleEditor({ user, onSaved, onError }) {
  const [role, setRole] = useState(user.role)
  const [extra, setExtra] = useState('')
  const needsRoll = role === 'student' && !user.student_id
  const needsDept = role === 'faculty' && !user.faculty_id
  async function apply() {
    try {
      await api(`/admin/users/${user.id}`, { method: 'PATCH', body: { role, ...(needsRoll ? { roll_number: extra } : {}), ...(needsDept && extra ? { department: extra } : {}) } })
      setExtra(''); onSaved(`${user.full_name} is now ${role}.`)
    } catch (err) { onError(err.message) }
  }
  return (
    <span className="role-editor">
      <select aria-label={`Role of ${user.full_name}`} value={role} onChange={(e) => { setRole(e.target.value); setExtra('') }}>
        <option value="student">student</option><option value="faculty">faculty</option><option value="admin">admin</option>
      </select>
      {role !== user.role && <>
        {(needsRoll || needsDept) && <input className="small" placeholder={needsRoll ? 'Roll number' : 'Department'} value={extra} onChange={(e) => setExtra(e.target.value)} />}
        <button className="btn ghost small" disabled={needsRoll && !extra.trim()} onClick={apply}>Apply</button>
      </>}
    </span>
  )
}

const USER_SORT = {
  name: (a, b) => a.full_name.localeCompare(b.full_name),
  role: (a, b) => a.role.localeCompare(b.role) || a.full_name.localeCompare(b.full_name),
  id: (a, b) => a.id - b.id,
}

function Users() {
  const [users, error, reload] = useLoad('/admin/users')
  const [f, setF] = useState({ role: 'student' })
  const [m, setM] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [q, setQ] = useState('')
  const [role, setRole] = useState('all')
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('id')
  const shown = useMemo(() => (users || []).filter((u) =>
    (role === 'all' || u.role === role) &&
    (status === 'all' || (status === 'active') === u.is_active) &&
    (!q || `${u.full_name} ${u.email}`.toLowerCase().includes(q.toLowerCase()))).sort(USER_SORT[sort]), [users, q, role, status, sort])
  async function create(e) {
    e.preventDefault()
    try {
      await api('/admin/users', { method: 'POST', body: { ...f, previous_result_pct: f.previous_result_pct ? Number(f.previous_result_pct) : null } })
      setM({ ok: true, text: 'User created.' }); setF({ role: 'student' }); setShowCreate(false); reload()
    } catch (err) { setM({ ok: false, text: err.message }) }
  }
  async function toggle(u) {
    try { await api(`/admin/users/${u.id}`, { method: 'PATCH', body: { is_active: !u.is_active } }); reload() } catch (err) { setM({ ok: false, text: err.message }) }
  }
  if (!users) return error ? <ErrorBox error={error} /> : <Loading />
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const sortHead = (key, label) => (
    <th className="sortable" aria-sort={sort === key ? 'ascending' : 'none'} onClick={() => setSort(key)}>{label}{sort === key ? ' ↑' : ''}</th>
  )
  return (
    <>
      <Msg m={m} />
      {showCreate && <Card title="Create user" icon="plus" actions={<button className="btn ghost small" onClick={() => setShowCreate(false)}>Cancel</button>}>
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
      </Card>}
      <Card title="Users" subtitle={`${shown.length} of ${users.length} shown`} icon="users" actions={
        <div className="filters">
          <span className="search"><Icon name="search" size={15} />
            <input aria-label="Search users" placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} /></span>
          <select aria-label="Filter by role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="all">All roles</option><option value="student">Students</option><option value="faculty">Faculty</option><option value="admin">Admins</option>
          </select>
          <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">Any status</option><option value="active">Active</option><option value="inactive">Deactivated</option>
          </select>
          {!showCreate && <button className="btn primary" onClick={() => setShowCreate(true)}><Icon name="plus" size={16} />New user</button>}
        </div>}>
        <p className="small muted">Changing a role keeps the user's existing profile and history; a student role needs a roll number if the user has no student profile yet. Every change is audited.</p>
        <div className="table-wrap"><table>
          <thead><tr>{sortHead('id', 'ID')}{sortHead('name', 'User')}{sortHead('role', 'Role')}<th>Profile</th><th>Status</th><th /></tr></thead>
          <tbody>{shown.map((u) => (
            <tr key={u.id}><td className="muted">{u.id}</td>
              <td><div className="cell-user"><Avatar name={u.full_name} size="sm" /><div><strong>{u.full_name}</strong><div className="small muted">{u.email}</div></div></div></td>
              <td><RoleEditor key={`${u.id}-${u.role}`} user={u} onSaved={(text) => { setM({ ok: true, text }); reload() }} onError={(text) => setM({ ok: false, text })} /></td>
              <td className="small">{u.student_id ? `student ${u.student_id}` : u.faculty_id ? `faculty ${u.faculty_id}` : '—'}</td>
              <td>{u.is_active ? <span className="badge dot positive">active</span> : <span className="badge dot">deactivated</span>}</td>
              <td><button className="btn ghost small" onClick={() => toggle(u)}>{u.is_active ? 'Deactivate' : 'Activate'}</button></td></tr>
          ))}
          {shown.length === 0 && <tr><td colSpan={6} className="muted">No users match.</td></tr>}</tbody>
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
      <Card title="Assign a student to a faculty member" icon="link">
        <form className="record-form" onSubmit={add}>
          <label>Faculty<select value={f.faculty_id || ''} onChange={(e) => setF({ ...f, faculty_id: e.target.value })}><option value="">Select…</option>{fac.map((u) => <option key={u.id} value={u.faculty_id}>{u.full_name}</option>)}</select></label>
          <label>Student<select value={f.student_id || ''} onChange={(e) => setF({ ...f, student_id: e.target.value })}><option value="">Select…</option>{stu.map((u) => <option key={u.id} value={u.student_id}>{u.full_name}</option>)}</select></label>
          <button className="btn primary">Assign</button>
        </form>
        <Msg m={m} />
      </Card>
      <Card title="Current assignments" icon="users">
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
      <Card title="Intervention categories" icon="layers">
        <table className="compact"><thead><tr><th>Code</th><th>Name</th><th>Description</th><th>Active</th><th /></tr></thead>
          <tbody>{types.map((t) => <tr key={t.id}><td>{t.code}</td><td>{t.name}</td><td className="small">{t.description}</td><td>{t.is_active ? 'yes' : 'no'}</td>
            <td><button className="btn ghost small" onClick={() => toggleType(t)}>{t.is_active ? 'Disable' : 'Enable'}</button></td></tr>)}</tbody></table>
        <p className="small muted">Disabled categories are removed from every eligible set (exclusion X2).</p>
      </Card>
      <Card title="Add learning resource" icon="plus">
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
      <Card title={`Learning resources (${resources.length})`} icon="book">
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
      <Card title="Policy and evaluation parameters" icon="sliders">
        <form onSubmit={saveCfg} className="cfg-grid">
          {Object.keys(cfg).map((k) => (
            <label key={k}><code>{k}</code><input type="number" step="any" value={cfg[k]} onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })} /><span className="small muted">{CFG_HELP[k]}</span></label>
          ))}
          <div><button className="btn primary">Save parameters</button></div>
        </form>
      </Card>
      <Card title="Eligibility rules (JSON)" icon="file">
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
      <Card title={`Linear Thompson sampling policy — v${d.current_version}`} icon="cpu">
        <p className="small">λ = {d.lambda}, v = {d.v}. Posterior mean θ per intervention (expected reward = context · θ):</p>
        <div className="table-wrap"><table className="compact">
          <thead><tr><th>Intervention</th><th>n</th>{d.context_features.map((f) => <th key={f} className="small">{f}</th>)}</tr></thead>
          <tbody>{d.arms.map((a) => <tr key={a.intervention}><td>{INTERVENTION_LABEL[a.intervention] || a.intervention}</td><td>{a.n_observations}</td>
            {d.context_features.map((f) => <td key={f}>{a.posterior_mean_theta[f]}</td>)}</tr>)}</tbody>
        </table></div>
      </Card>
      <div className="grid-2">
        <Card title="Policy-update history" icon="clock">
          {d.updates.length === 0 ? <p className="muted">No updates yet.</p> : (
            <table className="compact"><thead><tr><th>When</th><th>Intervention #</th><th>Reward</th><th>Version</th></tr></thead>
              <tbody>{d.updates.map((u) => <tr key={u.assignment_id}><td>{fmtDateTime(u.created_at)}</td><td>{u.assignment_id}</td><td>{u.reward}</td><td>v{u.from_version} → v{u.to_version}</td></tr>)}</tbody></table>)}
        </Card>
        <Card title="Versions" icon="layers">
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
    <Card title="Audit log (latest 200)" icon="file">
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
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
            <Icon name={TAB_ICON[t]} size={15} />{t}
          </button>
        ))}
      </div>
      <div key={tab} className="tab-panel"><View go={setTab} /></div>
    </>
  )
}

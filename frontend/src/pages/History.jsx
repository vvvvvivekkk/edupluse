import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, CATEGORY_LABEL } from '../api.js'
import { useAuth } from '../App.jsx'
import { Card, ErrorBox, HistoryTable, Loading } from '../components/ui.jsx'

export default function History() {
  const { id } = useParams()
  const { session } = useAuth()
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [cat, setCat] = useState('all')
  useEffect(() => { api(`/students/${id}/interventions`).then(setRows).catch((e) => setError(e.message)) }, [id])
  if (!rows) return error ? <ErrorBox error={error} /> : <Loading />
  const shown = rows.filter((r) => cat === 'all' || r.category === cat || (cat === 'pending' && !r.category))
  const counts = rows.reduce((m, r) => ({ ...m, [r.category || 'pending']: (m[r.category || 'pending'] || 0) + 1 }), {})
  return (
    <>
      <div className="page-head">
        <div>
          <Link className="small" to={session.user.role === 'student' ? '/student' : `/students/${id}`}>← Back</Link>
          <h1>Intervention history</h1>
          <p className="muted">{rows.length} interventions · {Object.entries(counts).map(([k, v]) => `${CATEGORY_LABEL[k] || 'Pending'} ${v}`).join(' · ') || 'none yet'}</p>
        </div>
        <select value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="all">All</option><option value="positive">Positive</option><option value="partial">Partial</option>
          <option value="no_improvement">No Improvement</option><option value="pending">Pending</option>
        </select>
      </div>
      <Card><HistoryTable rows={shown} /></Card>
    </>
  )
}

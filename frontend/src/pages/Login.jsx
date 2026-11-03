import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, saveSession } from '../api.js'
import { homeFor, useAuth } from '../App.jsx'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setSession } = useAuth()
  const navigate = useNavigate()

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password) {
      setError('Enter your email or username and your password.')
      return
    }
    setBusy(true)
    try {
      const res = await api('/auth/login', { method: 'POST', body: { email, password } })
      saveSession(res.access_token, res.user)
      setSession({ token: res.access_token, user: res.user })
      navigate(homeFor(res.user))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-side">
        <div className="brand big"><span className="brand-mark">◉</span> EduPulse</div>
        <p className="lede">Response-adaptive academic support. Every intervention is measured, and every outcome shapes the next one.</p>
        <ol className="cycle">
          <li>Estimate state</li><li>Select support</li><li>Measure response</li><li>Adapt</li>
        </ol>
      </div>
      <form className="login-card" onSubmit={submit} noValidate>
        <h1>Sign in</h1>
        <label>Email or username
          <input type="text" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <p className="small muted">Students can also use their roll number as username.</p>
        <label>Password
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="alert error" role="alert">{error}</div>}
        <button className="btn primary block" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <details className="demo">
          <summary>Demo accounts</summary>
          <p className="small">student1@edupulse.edu / Student@123<br />faculty1@edupulse.edu / Faculty@123<br />admin@edupulse.edu / Admin@123</p>
        </details>
      </form>
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, saveSession } from '../api.js'
import { homeFor, useAuth } from '../App.jsx'
import { Icon, Logo } from '../components/icons.jsx'

const DEMO = [
  ['Student', 'student1@edupulse.edu', 'Student@123', 'cap'],
  ['Faculty', 'faculty1@edupulse.edu', 'Faculty@123', 'users'],
  ['Admin', 'admin@edupulse.edu', 'Admin@123', 'shield'],
]

// Decorative scene: a progress card whose line climbs, a learning-gain result and a study plan.
function Illustration() {
  return (
    <svg className="illustration" viewBox="0 0 500 330" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="il-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9fb1ff" stopOpacity="0.55" /><stop offset="1" stopColor="#9fb1ff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="il-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#b8c5ff" /><stop offset="1" stopColor="#e0cfff" />
        </linearGradient>
      </defs>
      {/* main progress card */}
      <g className="float-b">
        <rect x="70" y="52" width="300" height="196" rx="20" fill="rgba(255,255,255,0.09)" stroke="rgba(255,255,255,0.18)" />
        <circle cx="94" cy="76" r="5" fill="rgba(255,255,255,0.35)" /><circle cx="110" cy="76" r="5" fill="rgba(255,255,255,0.22)" />
        <rect x="270" y="70" width="78" height="12" rx="6" fill="rgba(255,255,255,0.16)" />
        {[120, 155, 190, 225].map((y) => <line key={y} x1="94" x2="346" y1={y} y2={y} stroke="rgba(255,255,255,0.08)" />)}
        <path d="M94 210 C130 205 150 196 175 190 S220 176 245 160 S300 128 346 108 L346 228 L94 228 Z" fill="url(#il-area)" />
        <path className="draw" d="M94 210 C130 205 150 196 175 190 S220 176 245 160 S300 128 346 108" fill="none" stroke="url(#il-line)" strokeWidth="4" strokeLinecap="round" />
        <circle cx="175" cy="190" r="6" fill="#fff" /><circle cx="245" cy="160" r="6" fill="#fff" />
        <circle cx="346" cy="108" r="8" fill="#c9b6ff" stroke="#fff" strokeWidth="3" />
      </g>
      {/* learning-gain result */}
      <g className="float-a">
        <rect x="286" y="14" width="204" height="70" rx="16" fill="#fff" />
        <circle cx="316" cy="49" r="16" fill="#e3f5ec" />
        <path d="M308 49 l6 6 l11 -12" fill="none" stroke="#2f9e6b" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
        <text x="342" y="44" fontSize="12" fill="#646d86" fontFamily="Inter, sans-serif" fontWeight="600">Learning gain</text>
        <text x="342" y="64" fontSize="17" fill="#1a2138" fontFamily="Inter, sans-serif" fontWeight="800">+0.55 Positive</text>
      </g>
      {/* study plan */}
      <g className="float-c">
        <rect x="18" y="214" width="200" height="88" rx="16" fill="#fff" />
        <rect x="34" y="230" width="34" height="34" rx="10" fill="#ebefff" />
        <path d="M42 239 h7 a4 4 0 0 1 4 4 v13 a3 3 0 0 0 -3 -3 h-8 z M64 239 h-7 a4 4 0 0 0 -4 4 v13 a3 3 0 0 1 3 -3 h8 z" fill="none" stroke="#3b5bdb" strokeWidth="2" strokeLinejoin="round" />
        <text x="78" y="244" fontSize="12" fill="#646d86" fontFamily="Inter, sans-serif" fontWeight="600">Study plan</text>
        <text x="78" y="261" fontSize="14" fill="#1a2138" fontFamily="Inter, sans-serif" fontWeight="800">Day 3 of 5</text>
        <rect x="34" y="278" width="168" height="8" rx="4" fill="#eceff6" />
        <rect x="34" y="278" width="101" height="8" rx="4" fill="#3b5bdb" />
      </g>
      {/* graduation cap */}
      <g className="float-a" transform="translate(392 214)">
        <circle cx="38" cy="38" r="40" fill="rgba(255,255,255,0.10)" />
        <path d="M38 16 L72 32 L38 48 L4 32 Z" fill="#fff" />
        <path d="M18 39 v14 c10 8 30 8 40 0 v-14 l-20 9 z" fill="#d7defe" />
        <path d="M68 34 v18" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
        <circle cx="68" cy="55" r="4" fill="#c9b6ff" />
      </g>
    </svg>
  )
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [errorCount, setErrorCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const { setSession } = useAuth()
  const navigate = useNavigate()

  function fail(msg) {
    setError(msg)
    setErrorCount((n) => n + 1)
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password) {
      fail('Enter your email or username and your password.')
      return
    }
    setBusy(true)
    try {
      const res = await api('/auth/login', { method: 'POST', body: { email, password } })
      saveSession(res.access_token, res.user)
      setSession({ token: res.access_token, user: res.user })
      navigate(homeFor(res.user))
    } catch (err) {
      fail(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-side">
        <div className="brand"><Logo size={34} /> EduPulse</div>
        <div className="login-copy">
          <h2>Support that <span>adapts</span> to every student.</h2>
          <p className="lede">Response-adaptive academic support. Every intervention is measured, and every outcome shapes the next one.</p>
        </div>
        <Illustration />
        <ol className="cycle">
          <li>Estimate state</li><li>Select support</li><li>Measure response</li><li>Adapt</li>
        </ol>
      </div>
      <main className="login-main">
        <form className="login-card" onSubmit={submit} noValidate>
          <div>
            <h1>Sign in</h1>
          </div>
          <p className="sub">Welcome back. Sign in to see your dashboard.</p>
          <div className="field">
            <label className="field-label" htmlFor="login-email">Email or username</label>
            <div className="input-icon">
              <Icon name="mail" size={18} />
              <input id="login-email" type="text" autoComplete="username" placeholder="you@edupulse.edu or roll number"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <span className="field-hint">Students can also use their roll number as username.</span>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="login-password">Password</label>
            <div className="input-icon">
              <Icon name="lock" size={18} />
              <input id="login-password" type={showPw ? 'text' : 'password'} autoComplete="current-password" placeholder="Your password"
                value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="icon-btn reveal" aria-label={showPw ? 'Hide password' : 'Show password'}
                aria-pressed={showPw} onClick={() => setShowPw(!showPw)}>
                <Icon name={showPw ? 'eyeOff' : 'eye'} size={18} />
              </button>
            </div>
          </div>
          {error && <div className="alert error shake" role="alert" key={errorCount}><Icon name="alert" size={16} />{error}</div>}
          <button className="btn primary block lg" disabled={busy}>
            {busy ? <><span className="spinner" aria-hidden />Signing in…</> : <>Sign in<Icon name="arrowRight" size={17} /></>}
          </button>
          <div className="demo-box">
            <p>Demo accounts: click one to fill in the sign-in form</p>
            <div className="demo-chips">
              {DEMO.map(([label, em, pw, icon]) => (
                <button key={label} type="button" className="chip" title={em}
                  onClick={() => { setEmail(em); setPassword(pw); setError('') }}>
                  <Icon name={icon} size={14} />{label}
                </button>
              ))}
            </div>
          </div>
          <p className="login-foot">EduPulse supports academic guidance. Final decisions remain with faculty.</p>
        </form>
      </main>
    </div>
  )
}

import { createContext, useContext, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { clearSession, getSession } from './api.js'
import Login from './pages/Login.jsx'
import StudentDashboard from './pages/StudentDashboard.jsx'
import FacultyDashboard from './pages/FacultyDashboard.jsx'
import StudentDetail from './pages/StudentDetail.jsx'
import InterventionDetail from './pages/InterventionDetail.jsx'
import History from './pages/History.jsx'
import Admin from './pages/Admin.jsx'
import Analytics from './pages/Analytics.jsx'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export const homeFor = (user) =>
  user.role === 'student' ? '/student' : user.role === 'faculty' ? '/faculty' : '/admin'

function Protected({ roles, children }) {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  if (roles && !roles.includes(session.user.role)) return <Navigate to={homeFor(session.user)} replace />
  return <Shell>{children}</Shell>
}

function Shell({ children }) {
  const { session, setSession } = useAuth()
  const navigate = useNavigate()
  const u = session.user
  const links =
    u.role === 'student'
      ? [['/student', 'My dashboard'], [`/students/${u.student_id}/history`, 'History']]
      : u.role === 'faculty'
        ? [['/faculty', 'My students'], ['/analytics', 'Analytics']]
        : [['/admin', 'Administration'], ['/faculty', 'All students'], ['/analytics', 'Analytics']]
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden>◉</span> EduPulse
        </div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="userbox">
          <span>
            {u.full_name} <em>{u.role}</em>
          </span>
          <button
            className="btn ghost small"
            onClick={() => {
              clearSession()
              setSession(null)
              navigate('/login')
            }}
          >
            Log out
          </button>
        </div>
      </header>
      <main className="page">{children}</main>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(getSession())
  return (
    <AuthContext.Provider value={{ session, setSession }}>
      <Routes>
        <Route path="/login" element={session ? <Navigate to={homeFor(session.user)} replace /> : <Login />} />
        <Route path="/student" element={<Protected roles={['student']}><StudentDashboard /></Protected>} />
        <Route path="/faculty" element={<Protected roles={['faculty', 'admin']}><FacultyDashboard /></Protected>} />
        <Route path="/students/:id" element={<Protected roles={['faculty', 'admin']}><StudentDetail /></Protected>} />
        <Route path="/students/:id/history" element={<Protected><History /></Protected>} />
        <Route path="/interventions/:id" element={<Protected><InterventionDetail /></Protected>} />
        <Route path="/analytics" element={<Protected roles={['faculty', 'admin']}><Analytics /></Protected>} />
        <Route path="/admin" element={<Protected roles={['admin']}><Admin /></Protected>} />
        <Route path="*" element={<Navigate to={session ? homeFor(session.user) : '/login'} replace />} />
      </Routes>
    </AuthContext.Provider>
  )
}

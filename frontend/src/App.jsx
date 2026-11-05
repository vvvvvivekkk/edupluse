import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, matchPath, useLocation, useNavigate } from 'react-router-dom'
import { clearSession, getSession } from './api.js'
import { Icon, Logo } from './components/icons.jsx'
import { NotificationBell } from './components/Notifications.jsx'
import { Avatar } from './components/ui.jsx'
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

const NAV = {
  student: (u) => [['/student', 'My dashboard', 'home'], [`/students/${u.student_id}/history`, 'History', 'clock']],
  faculty: () => [['/faculty', 'My students', 'users'], ['/analytics', 'Analytics', 'chart']],
  admin: () => [['/admin', 'Administration', 'shield'], ['/faculty', 'All students', 'users'], ['/analytics', 'Analytics', 'chart']],
}
const TIPS = {
  student: ['Your next step', 'Finish your open activity, then record the follow-up score to see how much it helped.'],
  faculty: ['Final say is yours', 'EduPulse recommends support; you can always record faculty support yourself.'],
  admin: ['Everything is audited', 'User, content, configuration and policy changes are written to the audit log.'],
}
const TITLES = [
  ['/student', 'My dashboard'], ['/faculty', 'Students'], ['/analytics', 'Analytics'], ['/admin', 'Administration'],
  ['/students/:id/history', 'Intervention history'], ['/students/:id', 'Student profile'], ['/interventions/:id', 'Intervention'],
]

function Shell({ children }) {
  const { session, setSession } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const u = session.user
  const links = NAV[u.role](u)
  const title = TITLES.find(([p]) => matchPath(p, location.pathname))?.[1] || 'EduPulse'
  const [tipTitle, tipText] = TIPS[u.role]
  useEffect(() => { setNavOpen(false) }, [location.pathname])

  return (
    <div className={`app ${navOpen ? 'nav-open' : ''}`}>
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand"><Logo size={30} /><span>EduPulse<span className="brand-sub">Adaptive support</span></span></div>
        <div className="side-label">Menu</div>
        <nav className="side-nav">
          {links.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
              <Icon name={icon} size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <div className="side-tip"><strong>{tipTitle}</strong>{tipText}</div>
          <div className="side-user">
            <Avatar name={u.full_name} />
            <div className="side-user-text">
              <div className="side-user-name">{u.full_name}</div>
              <div className="side-user-role">{u.role}</div>
            </div>
            <button
              className="icon-btn"
              aria-label="Log out"
              title="Log out"
              onClick={() => {
                clearSession()
                setSession(null)
                navigate('/login')
              }}
            >
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="scrim" onClick={() => setNavOpen(false)} aria-hidden />
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setNavOpen(true)}><Icon name="menu" size={20} /></button>
          <div className="topbar-title">
            <div className="crumb">EduPulse · <span style={{ textTransform: 'capitalize' }}>{u.role}</span></div>
            <div className="here">{title}</div>
          </div>
          <div className="topbar-actions">
            <span className="today">{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</span>
            <NotificationBell userId={u.id} />
          </div>
        </header>
        <main className="page" key={location.pathname}>{children}</main>
      </div>
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

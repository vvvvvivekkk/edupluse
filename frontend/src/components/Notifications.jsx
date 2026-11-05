import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, timeAgo } from '../api.js'
import { Icon } from './icons.jsx'

const KIND_ICON = { assigned: 'zap', reminder: 'clock', followup: 'file', result: 'award', state: 'activity', review: 'alert' }
const POLL_MS = 60000

// Read state lives in this browser only (per user); notifications themselves are derived by the API.
const readKey = (userId) => `edupulse_read_${userId}`
function loadRead(userId) {
  try { return new Set(JSON.parse(localStorage.getItem(readKey(userId)) || '[]')) } catch { return new Set() }
}
function saveRead(userId, set) {
  try { localStorage.setItem(readKey(userId), JSON.stringify([...set].slice(-300))) } catch { /* storage unavailable */ }
}

export function useNotifications(userId) {
  const [items, setItems] = useState([])
  const [read, setRead] = useState(() => loadRead(userId))
  const location = useLocation()
  const refresh = useCallback(() => api('/notifications').then((r) => setItems(r || [])).catch(() => {}), [])
  useEffect(() => { refresh() }, [refresh, location.pathname])
  useEffect(() => {
    const t = setInterval(refresh, POLL_MS)
    return () => clearInterval(t)
  }, [refresh])
  const markRead = (ids) => setRead((prev) => {
    const next = new Set(prev)
    ids.forEach((id) => next.add(id))
    saveRead(userId, next)
    return next
  })
  return { items, read, markRead, unread: items.filter((n) => !read.has(n.id)).length }
}

export function NotificationBell({ userId }) {
  const { items, read, markRead, unread } = useNotifications(userId)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  function go(n) {
    markRead([n.id])
    setOpen(false)
    if (n.link) navigate(n.link)
  }

  return (
    <div className="notif" ref={ref}>
      <button className="icon-btn" aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="bell" size={18} />
        {unread > 0 && <span className="notif-count" aria-hidden>{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-head">
            <h2>Notifications</h2>
            {unread > 0 && <button onClick={() => markRead(items.map((n) => n.id))}>Mark all as read</button>}
          </div>
          {items.length === 0 ? (
            <div className="notif-empty"><Icon name="checkCircle" size={28} strokeWidth={1.6} /><p>You're all caught up.</p></div>
          ) : (
            <ul className="notif-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button className={`notif-item ${read.has(n.id) ? '' : 'unread'}`} onClick={() => go(n)}>
                    <span className={`notif-ico k-${n.kind}`}><Icon name={KIND_ICON[n.kind] || 'bell'} size={16} /></span>
                    <span className="notif-text">
                      <span className="notif-title">{!read.has(n.id) && <span className="dot" aria-label="unread" />}{n.title}</span>
                      <span className="notif-body">{n.body}</span>
                      <span className="notif-when">{timeAgo(n.at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

// Action items (things the student still has to do), shown on the student dashboard.
export function Reminders({ items }) {
  const todo = items.filter((n) => n.action_required)
  if (!todo.length) return null
  return (
    <div className="reminders">
      {todo.map((n) => (
        <Link key={n.id} to={n.link} className="reminder">
          <span className={`notif-ico k-${n.kind}`}><Icon name={KIND_ICON[n.kind] || 'bell'} size={16} /></span>
          <span className="grow"><span className="notif-title">{n.title}</span><span className="notif-body">{n.body}</span></span>
          <Icon name="arrowRight" size={16} className="arrow" />
        </Link>
      ))}
    </div>
  )
}

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App.jsx'
import { saveSession } from '../api.js'
import { NotificationBell } from '../components/Notifications.jsx'
import Admin from '../pages/Admin.jsx'
import { mockFetch } from './setup.js'

function Where() { return <output data-testid="path">{useLocation().pathname}</output> }

describe('Login page', () => {
  it('shows and hides the password', async () => {
    mockFetch([])
    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
    const pw = screen.getByLabelText('Password')
    expect(pw).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(pw).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(pw).toHaveAttribute('type', 'password')
  })

  it('fills the form from a demo account', async () => {
    mockFetch([])
    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Faculty' }))
    expect(screen.getByLabelText('Email or username')).toHaveValue('faculty1@edupulse.edu')
    expect(screen.getByLabelText('Password')).toHaveValue('Faculty@123')
  })
})

describe('NotificationBell', () => {
  const items = [
    { id: 'followup-4', kind: 'followup', title: 'Follow-up assessment due: Recursion', body: 'Record your follow-up score.', at: new Date().toISOString(), link: '/interventions/4', action_required: true },
    { id: 'result-3', kind: 'result', title: 'Result: Positive', body: 'Targeted Practice Questions on Loops (38% → 72%).', at: '2026-10-01T10:00:00Z', link: '/interventions/3', action_required: false },
  ]
  const renderBell = () => render(
    <MemoryRouter initialEntries={['/student']}>
      <Routes><Route path="*" element={<><NotificationBell userId={7} /><Where /></>} /></Routes>
    </MemoryRouter>,
  )

  it('counts unread items, opens the panel and goes to the linked page', async () => {
    saveSession('t', { id: 7, role: 'student' })
    mockFetch([['/api/notifications', { body: items }]])
    renderBell()
    const bell = await screen.findByRole('button', { name: 'Notifications, 2 unread' })
    await userEvent.click(bell)
    const panel = screen.getByRole('dialog', { name: 'Notifications' })
    expect(within(panel).getByText('Follow-up assessment due: Recursion')).toBeInTheDocument()
    expect(within(panel).getByText('just now')).toBeInTheDocument()
    await userEvent.click(within(panel).getByText('Follow-up assessment due: Recursion'))
    expect(screen.getByTestId('path')).toHaveTextContent('/interventions/4')
    expect(await screen.findByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('edupulse_read_7'))).toEqual(['followup-4'])
  })

  it('marks everything as read', async () => {
    saveSession('t', { id: 7, role: 'student' })
    mockFetch([['/api/notifications', { body: items }]])
    renderBell()
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications, 2 unread' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mark all as read' }))
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('says when there is nothing new', async () => {
    saveSession('t', { id: 7, role: 'student' })
    mockFetch([['/api/notifications', { body: [] }]])
    renderBell()
    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(await screen.findByText("You're all caught up.")).toBeInTheDocument()
  })
})

describe('Intervention history timeline', () => {
  // newest first, as the API returns it
  const rows = [
    { id: 9, assigned_at: '2026-11-03T10:00:00Z', intervention: 'study_plan', intervention_name: 'Personalized Study Plan', topic: 'Recursion',
      reason: ['R3: Mixed performance'], status: 'accessed', pre_score: 72, post_score: null, category: null, selection_method: 'linear_thompson' },
    { id: 8, assigned_at: '2026-11-01T10:00:00Z', intervention: 'targeted_practice', intervention_name: 'Targeted Practice Questions', topic: 'Recursion',
      reason: ['R1: Low assessment performance'], status: 'evaluated', pre_score: 38, post_score: 72, learning_gain: 0.55, category: 'positive', selection_method: 'linear_thompson' },
  ]
  const renderHistory = () => {
    saveSession('t', { id: 5, role: 'student', student_id: 1, full_name: 'S' })
    mockFetch([['/api/students/1/interventions', { body: rows }]])
    return render(<MemoryRouter initialEntries={['/students/1/history']}><App /></MemoryRouter>)
  }

  it('shows before/after, the change and what was recommended next', async () => {
    renderHistory()
    expect(await screen.findByRole('heading', { name: 'Intervention history' })).toBeInTheDocument()
    const item = screen.getByRole('link', { name: 'Targeted Practice Questions' }).closest('.tl-card')
    expect(item).toHaveTextContent('38%')
    expect(item).toHaveTextContent('72%')
    expect(within(item).getByText('+34 pts')).toBeInTheDocument()
    expect(item).toHaveTextContent('gain g = 0.55')
    expect(item).toHaveTextContent('Next recommendation switched to Personalized Study Plan')
    expect(screen.getByText('Activities completed').previousSibling).toHaveTextContent('1')
  })

  it('switches to the table view', async () => {
    renderHistory()
    await userEvent.click(await screen.findByRole('button', { name: 'Table' }))
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toContain('Reason / eligibility')
  })
})

describe('Faculty dashboard', () => {
  it('tracks interventions by stage and sorts students needing support first', async () => {
    saveSession('t', { id: 2, role: 'faculty', full_name: 'F' })
    const st = (state, score) => ({ state, features: { latest_score: score, attendance_pct: 80, assignment_completion_pct: 90 } })
    mockFetch([
      ['/api/students', { body: [
        { id: 1, name: 'Asha Normal', roll_number: 'EP1', state: st('normal', 88), no_improvement_streak: 0, open_intervention: null },
        { id: 2, name: 'Bala High', roll_number: 'EP2', state: st('high_support_need', 31), no_improvement_streak: 0, open_intervention: null },
      ] }],
      ['/api/dashboard/summary', { body: {
        student_count: 2, state_distribution: { normal: 1, high_support_need: 1 }, intervention_status: { assigned: 1, completed: 2, evaluated: 3 },
        response_categories: { positive: 2, partial: 1 }, interventions_by_type: { study_plan: 6 }, students_needing_review: [], pending_faculty_support: [],
      } }],
    ])
    render(<MemoryRouter initialEntries={['/faculty']}><App /></MemoryRouter>)
    const tracking = (await screen.findByRole('heading', { name: 'Intervention tracking' })).closest('.card')
    expect(within(tracking).getByText('Awaiting follow-up').closest('.pipe')).toHaveTextContent('2')
    expect(within(tracking).getByText('Evaluated').closest('.pipe')).toHaveTextContent('3')
    const names = () => screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('link')[0].textContent)
    expect(names()).toEqual(['Bala High', 'Asha Normal'])
    await userEvent.selectOptions(screen.getByLabelText('Sort students'), 'name')
    expect(names()).toEqual(['Asha Normal', 'Bala High'])
  })
})

describe('Admin user management', () => {
  it('searches and filters the user table', async () => {
    saveSession('t', { id: 1, role: 'admin', full_name: 'A' })
    mockFetch([['/api/admin/users', { body: [
      { id: 1, full_name: 'Admin One', email: 'admin@edupulse.edu', role: 'admin', is_active: true },
      { id: 2, full_name: 'Faculty One', email: 'faculty1@edupulse.edu', role: 'faculty', faculty_id: 1, is_active: true },
      { id: 3, full_name: 'Student One', email: 'student1@edupulse.edu', role: 'student', student_id: 1, is_active: false },
    ] }]])
    render(<MemoryRouter><Admin /></MemoryRouter>)
    await userEvent.click(screen.getByRole('tab', { name: 'Users' }))
    expect(await screen.findByText('3 of 3 shown')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search users'), 'faculty1')
    expect(screen.getByText('1 of 3 shown')).toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Search users'))
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'inactive')
    expect(screen.getByText('Student One')).toBeInTheDocument()
    expect(screen.queryByText('Admin One')).toBeNull()
  })
})

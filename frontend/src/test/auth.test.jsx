import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App.jsx'
import { saveSession } from '../api.js'
import { mockFetch } from './setup.js'

function Where() { return <output data-testid="path">{useLocation().pathname}</output> }
const renderAt = (path) => render(<MemoryRouter initialEntries={[path]}><App /><Where /></MemoryRouter>)

describe('Login screen (Screen 1)', () => {
  it('validates empty fields without calling the API', async () => {
    const calls = mockFetch([])
    renderAt('/login')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your email or username and your password.')
    expect(calls).toHaveLength(0)
  })

  it('shows the server error for wrong credentials', async () => {
    mockFetch([['/api/auth/login', { status: 401, body: { detail: 'Incorrect email or password' } }]])
    renderAt('/login')
    await userEvent.type(screen.getByLabelText('Email or username'), 'student1@edupulse.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
  })

  it.each([
    ['student', 'My dashboard'],
    ['faculty', 'My students'],
    ['admin', 'Administration'],
  ])('redirects a %s to their own home', async (role, navLabel) => {
    const home = { student: '/student', faculty: '/faculty', admin: '/admin' }[role]
    const calls = mockFetch([['/api/auth/login', { body: { access_token: 't', user: { id: 9, role, full_name: 'U', student_id: 1 } } }]])
    renderAt('/login')
    await userEvent.type(screen.getByLabelText('Email or username'), 'EP26001')
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('link', { name: navLabel })).toBeInTheDocument()
    expect(screen.getByTestId('path')).toHaveTextContent(home)
    expect(JSON.parse(calls[0].body)).toEqual({ email: 'EP26001', password: 'pw' })
  })
})

describe('role-based routing', () => {
  it('keeps a student out of the admin and faculty screens', async () => {
    mockFetch([])
    saveSession('t', { id: 5, role: 'student', full_name: 'S', student_id: 1 })
    for (const path of ['/admin', '/faculty', '/analytics', '/students/2']) {
      const { unmount } = renderAt(path)
      expect(screen.getByTestId('path')).toHaveTextContent(/^\/student$/)
      expect(screen.queryByRole('heading', { name: 'Administration' })).toBeNull()
      unmount()
    }
  })

  it('sends visitors without a session to the login screen', () => {
    mockFetch([])
    renderAt('/faculty')
    expect(screen.getByTestId('path')).toHaveTextContent('/login')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })
})

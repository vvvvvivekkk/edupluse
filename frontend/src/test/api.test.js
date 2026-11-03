import { describe, expect, it } from 'vitest'
import { api, errorMessage, saveSession } from '../api.js'
import { mockFetch } from './setup.js'

describe('errorMessage', () => {
  it('turns API error details into readable text', () => {
    expect(errorMessage('Not permitted')).toBe('Not permitted')
    expect(errorMessage([{ msg: 'Value error, raw_score cannot exceed max_score' }, { msg: 'Row 3: unknown topic' }]))
      .toBe('raw_score cannot exceed max_score; Row 3: unknown topic')
    expect(errorMessage(null)).toBe('Something went wrong')
  })
})

describe('api', () => {
  it('sends JSON with the bearer token', async () => {
    saveSession('tok123', { id: 1, role: 'faculty' })
    const calls = mockFetch([['/api/students', { body: [{ id: 1 }] }]])
    expect(await api('/students')).toEqual([{ id: 1 }])
    expect(calls[0].headers).toEqual({ 'Content-Type': 'application/json', Authorization: 'Bearer tok123' })
  })

  it('sends FormData uploads without forcing a JSON content type', async () => {
    saveSession('tok123', { id: 1, role: 'faculty' })
    const calls = mockFetch([['/api/academic-records/import', { body: { imported: 2 } }]])
    const form = new FormData()
    form.append('file', new Blob(['a,b\n']), 'r.csv')
    await api('/academic-records/import', { method: 'POST', body: form })
    expect(calls[0].body).toBe(form)
    expect(calls[0].headers['Content-Type']).toBeUndefined()
  })

  it('throws the server message on errors', async () => {
    mockFetch([['/api/auth/login', { status: 401, body: { detail: 'Incorrect email or password' } }]])
    await expect(api('/auth/login', { method: 'POST', body: {} })).rejects.toThrow('Incorrect email or password')
  })
})

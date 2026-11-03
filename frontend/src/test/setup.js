import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom does not provide.
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} }

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

// Mock fetch with a list of [matcher, response] pairs; unmatched requests never resolve (page stays "Loading…").
export function mockFetch(routes) {
  const calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts = {}) => {
    calls.push({ url, ...opts })
    const hit = routes.find(([m]) => (typeof m === 'string' ? url.startsWith(m) : m.test(url)))
    if (!hit) return new Promise(() => {})
    const [, { status = 200, body = {} }] = hit
    return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })
  })
  return calls
}

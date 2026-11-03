import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { HistoryTable, IndicatorGrid, StateCard } from '../components/ui.jsx'
import ImportRecords from '../components/ImportRecords.jsx'
import Analytics from '../pages/Analytics.jsx'
import { saveSession } from '../api.js'
import { mockFetch } from './setup.js'

describe('IndicatorGrid', () => {
  it('shows missing indicators as "no data", never as 0%', () => {
    render(<IndicatorGrid indicators={{ latest_score: 0, avg_score: 55.4, attendance_pct: null }} />)
    const card = (label) => screen.getByText(label).closest('.indicator')
    expect(within(card('Latest assessment')).getByText('0%')).toBeInTheDocument()
    expect(within(card('Average assessment')).getByText('55%')).toBeInTheDocument()
    expect(within(card('Attendance')).getByText('no data')).toBeInTheDocument()
    expect(within(card('Previous result')).getByText('no data')).toBeInTheDocument()
  })
})

describe('StateCard', () => {
  const state = {
    state: 'attention_needed', model_version: 'rf-synth-1.0', created_at: '2026-11-01T10:00:00Z',
    probabilities: { normal: 0.2, attention_needed: 0.7, high_support_need: 0.1 },
    explanation: { concerns: ['Attendance 60% is below the typical 82%'], imputed_note: 'Not available, filled with training median: Practice accuracy' },
  }
  it('shows state, probabilities, explanation and the guidance disclaimer', () => {
    render(<StateCard state={state} stale />)
    expect(screen.getAllByText('Attention Needed').length).toBeGreaterThan(0)
    expect(screen.getByText('70%')).toBeInTheDocument()
    expect(screen.getByText(/Attendance 60% is below/)).toBeInTheDocument()
    expect(screen.getByText(/filled with training median/)).toBeInTheDocument()
    expect(screen.getByText('update pending')).toBeInTheDocument()
    expect(screen.getByText(/not a judgment of ability/)).toBeInTheDocument()
  })
  it('handles a student with no estimate yet', () => {
    render(<StateCard state={null} />)
    expect(screen.getByText('No state estimate yet.')).toBeInTheDocument()
  })
})

describe('HistoryTable (Screen 7)', () => {
  it('lists date, intervention, reason, status, before/after and response', () => {
    const rows = [
      { id: 7, assigned_at: '2026-11-01T10:00:00Z', intervention_name: 'Targeted Practice Questions', topic: 'Recursion',
        reason: ['R1: Low assessment performance with weak topic mastery'], status: 'evaluated', pre_score: 38, post_score: 72, category: 'positive' },
      { id: 8, assigned_at: '2026-11-02T10:00:00Z', intervention_name: 'Faculty Support', selection_method: 'faculty_manual',
        topic: null, reason: ['Recorded by faculty member'], status: 'assigned', pre_score: 72, post_score: null, category: null },
    ]
    render(<MemoryRouter><HistoryTable rows={rows} /></MemoryRouter>)
    const [, r1, r2] = screen.getAllByRole('row')
    expect(within(r1).getByRole('link', { name: 'Targeted Practice Questions' })).toHaveAttribute('href', '/interventions/7')
    expect(r1).toHaveTextContent('R1: Low assessment performance')
    expect(r1).toHaveTextContent('38%')
    expect(r1).toHaveTextContent('72%')
    expect(within(r1).getByText('Positive')).toBeInTheDocument()
    expect(within(r2).getByText('Pending')).toBeInTheDocument()
    expect(r2).toHaveTextContent('recorded by faculty')
  })
  it('says so when there is no history', () => {
    render(<MemoryRouter><HistoryTable rows={[]} /></MemoryRouter>)
    expect(screen.getByText('No interventions recorded yet.')).toBeInTheDocument()
  })
})

describe('ImportRecords', () => {
  const file = () => new File(['roll_number,record_type\n'], 'records.csv', { type: 'text/csv' })

  it('only allows import after a clean check, and shows row errors otherwise', async () => {
    saveSession('t', { id: 2, role: 'faculty' })
    const calls = mockFetch([
      ['/api/academic-records/import?dry_run=true', { body: { dry_run: true, rows: 3, valid: 1, by_type: { attendance: 1 },
        errors: [{ row: 3, error: 'unknown roll_number' }, { row: 4, error: 'raw_score cannot exceed max_score' }] } }],
    ])
    render(<ImportRecords />)
    const importBtn = screen.getByRole('button', { name: /^Import/ })
    expect(importBtn).toBeDisabled()
    await userEvent.upload(screen.getByLabelText('CSV file'), file())
    await userEvent.click(screen.getByRole('button', { name: 'Check file' }))
    expect(await screen.findByText(/3 rows checked: 1 valid, 2 with errors/)).toBeInTheDocument()
    expect(screen.getByText('unknown roll_number')).toBeInTheDocument()
    expect(importBtn).toBeDisabled()
    expect(calls).toHaveLength(1)
  })

  it('imports after a clean check', async () => {
    saveSession('t', { id: 2, role: 'faculty' })
    let imported = false
    const calls = mockFetch([
      ['/api/academic-records/import?dry_run=true', { body: { dry_run: true, rows: 2, valid: 2, by_type: { practice: 2 }, errors: [] } }],
      ['/api/academic-records/import?dry_run=false', { body: { dry_run: false, imported: 2, students: 1, errors: [] } }],
    ])
    render(<ImportRecords onImported={() => { imported = true }} />)
    await userEvent.upload(screen.getByLabelText('CSV file'), file())
    await userEvent.click(screen.getByRole('button', { name: 'Check file' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Import 2 records' }))
    expect(await screen.findByText(/Imported 2 records for 1 student/)).toBeInTheDocument()
    expect(imported).toBe(true)
    expect(calls[1].method).toBe('POST')
    expect(calls[1].body.get('file').name).toBe('records.csv')
  })

  it('offers a downloadable template', () => {
    render(<ImportRecords />)
    const link = screen.getByRole('link', { name: 'Download template' })
    expect(decodeURIComponent(link.getAttribute('href'))).toContain('roll_number,record_type,assessment_title')
  })
})

describe('Analytics (Screen 9)', () => {
  it('does not claim effectiveness for intervention types with too little data', async () => {
    saveSession('t', { id: 2, role: 'faculty', full_name: 'F' })
    mockFetch([['/api/analytics', { body: {
      outcomes_over_time: [], intervention_counts: { targeted_practice: 3 }, response_categories: { positive: 2, partial: 1 },
      score_changes: [], avg_score_over_time: [], assignment_status: {},
      type_summary: [{ intervention: 'targeted_practice', n_evaluated: 3, mean_reward: null, sufficient_data: false }],
      comparison_note: 'Effectiveness is only summarised for intervention types with at least 30 evaluated outcomes.',
    } }]])
    render(<MemoryRouter><Analytics /></MemoryRouter>)
    expect(await screen.findByText('insufficient data')).toBeInTheDocument()
    expect(screen.getByText(/at least 30 evaluated outcomes/)).toBeInTheDocument()
  })
})

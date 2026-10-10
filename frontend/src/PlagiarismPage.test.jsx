import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('./services/api', () => ({
  researchApi: {
    getPlagiarismStatus: vi.fn(),
    startPlagiarismScan: vi.fn(),
    getPlagiarismScan: vi.fn(),
    downloadPlagiarismReport: vi.fn(),
  },
}))

import { researchApi } from './services/api'
import PlagiarismPage from './PlagiarismPage'

const STATUS = {
  corpus: { name: 'Bundled corpus', source_count: 4 },
  semantic: { status: 'unavailable' },
  external: { configured: false, message: 'No external provider configured.' },
  engines: [
    { id: 'lexical', available: true },
    { id: 'semantic', available: false },
  ],
}

const REPORT = {
  scan_id: 'PLG-1',
  provider: 'internal',
  engines: [{ engine: 'lexical', status: 'completed' }],
  summary: {
    overall_similarity: 0.5,
    matched_words: 50,
    total_words: 100,
    suspected_unattributed_words: 50,
    suspected_unattributed_ratio: 0.5,
    match_count: 1,
    source_count: 1,
    quotation_match_count: 0,
    attributed_match_count: 0,
  },
  sources: [
    { id: 'src-1', title: 'Source One', url: 'https://example.test/source', matched_words: 50, passage_count: 1, max_similarity: 1 },
  ],
  matches: [
    {
      id: 'PM-0001',
      passage: 'Federated learning enables multiple institutions to collaboratively train a shared model.',
      location: { section_heading: 'Introduction', paragraph_number: 2 },
      source: { id: 'src-1', title: 'Source One' },
      method: 'exact',
      similarity: 1,
      coverage: 1,
      classification: 'suspected_unattributed',
      matched_text: 'Federated learning enables multiple institutions to collaboratively train a shared model.',
      note: 'Overlaps an identified source.',
    },
  ],
  classifier: {
    status: { status: 'completed', detail: 'Trained logistic-regression model loaded.' },
    note: 'Scores are not calibrated confidence.',
    candidate_scores: [
      {
        source: { id: 'src-1', title: 'Source One', url: 'https://example.test/source' },
        source_passage: 'Identified source passage.',
        passage_location: { paragraph_number: 2 },
        positive_score: 0.75,
        predicted_label: 1,
        threshold: 0.55,
      },
    ],
  },
  citation_warnings: [
    { type: 'match_without_citation', severity: 'high', message: 'Paragraph 2 overlaps Source One.', suggestion: 'Add a citation.' },
  ],
  exclusions: { references_words_excluded: 12, quoted_passages_retained: 0, boilerplate_passages_excluded: 0, notes: ['Reference list excluded.'] },
  scope: { corpus: { name: 'Bundled corpus', source_count: 4 }, limitations: ['Similarity is not proof of plagiarism.'] },
  disclaimer: 'Similarity is not a verdict.',
}

const manuscript = { document_id: 'DOC-1', title: 'Test manuscript' }

beforeEach(() => {
  vi.clearAllMocks()
  researchApi.getPlagiarismStatus.mockResolvedValue(STATUS)
})

afterEach(cleanup)

describe('PlagiarismPage', () => {
  it('runs a scan and renders the results dashboard', async () => {
    researchApi.startPlagiarismScan.mockResolvedValue({ scan_id: 'PLG-1', status: 'queued' })
    researchApi.getPlagiarismScan.mockResolvedValue({ scan_id: 'PLG-1', status: 'completed', provider: 'internal', report: REPORT })

    render(<PlagiarismPage document={manuscript} setActive={() => {}} />)
    expect(await screen.findByText(/plagiarism check/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /start similarity scan/i }))

    await waitFor(() => expect(researchApi.startPlagiarismScan).toHaveBeenCalledWith('DOC-1', {
      provider: 'internal',
      engines: ['lexical'],
      consent_external: false,
    }))
    expect((await screen.findAllByText(/suspected unattributed/i)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Source One/).length).toBeGreaterThan(0)
    expect(screen.getByText(/match without citation/i)).toBeTruthy()
    expect(screen.getByText(/reference list excluded/i)).toBeTruthy()
    expect(screen.getByText(/model score 0\.750/i)).toBeTruthy()
    expect(screen.getByText(/source passage: identified source passage/i)).toBeTruthy()
  })

  it('shows an error when the scan fails', async () => {
    researchApi.startPlagiarismScan.mockResolvedValue({ scan_id: 'PLG-2', status: 'queued' })
    researchApi.getPlagiarismScan.mockResolvedValue({ scan_id: 'PLG-2', status: 'failed', provider: 'internal', error: 'provider timeout' })

    render(<PlagiarismPage document={manuscript} setActive={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: /start similarity scan/i }))

    expect(await screen.findByText(/provider timeout/i)).toBeTruthy()
  })

  it('requires consent before sending a manuscript to an external provider', async () => {
    researchApi.getPlagiarismStatus.mockResolvedValue({
      ...STATUS,
      external: { configured: true, message: 'External provider configured.' },
    })

    render(<PlagiarismPage document={manuscript} setActive={() => {}} />)
    const select = await screen.findByLabelText(/comparison provider/i)
    fireEvent.change(select, { target: { value: 'external' } })

    fireEvent.click(screen.getByRole('button', { name: /start similarity scan/i }))

    expect(await screen.findByText(/confirm consent/i)).toBeTruthy()
    expect(researchApi.startPlagiarismScan).not.toHaveBeenCalled()
  })

  it('prompts to upload when no manuscript is loaded', async () => {
    render(<PlagiarismPage document={{}} setActive={() => {}} />)
    expect(await screen.findByText(/no manuscript loaded/i)).toBeTruthy()
  })
})

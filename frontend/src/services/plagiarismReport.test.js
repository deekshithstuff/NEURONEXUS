import { describe, expect, it } from 'vitest'
import {
  buildReportFilename,
  classificationMeta,
  engineAvailability,
  formatPercent,
  providerLabel,
  summarizeScan,
} from './plagiarismReport'

describe('plagiarismReport helpers', () => {
  it('formats similarity values as percentages', () => {
    expect(formatPercent(0.1234)).toBe('12.3%')
    expect(formatPercent(0)).toBe('0.0%')
    expect(formatPercent(undefined)).toBe('—')
  })

  it('maps classifications to honest labels', () => {
    expect(classificationMeta('suspected_unattributed').tone).toBe('danger')
    expect(classificationMeta('semantic_related').description).toMatch(/not evidence of plagiarism/i)
    expect(classificationMeta('unknown_kind').label).toBe('unknown kind')
  })

  it('labels internal and external providers differently', () => {
    expect(providerLabel('internal')).toMatch(/internal/i)
    expect(providerLabel('external:copyleaks')).toMatch(/copyleaks/i)
  })

  it('summarizes a report into dashboard statistics', () => {
    const stats = summarizeScan({
      summary: {
        overall_similarity: 0.25,
        matched_words: 25,
        total_words: 100,
        suspected_unattributed_ratio: 0.1,
        suspected_unattributed_words: 10,
        source_count: 2,
        match_count: 3,
        quotation_match_count: 1,
      },
    })
    expect(stats.map((stat) => stat.key)).toEqual(['overall', 'suspected', 'sources', 'matches'])
    expect(stats[0].value).toBe('25.0%')
    expect(stats[3].value).toBe(3)
  })

  it('reports engine availability from the status payload', () => {
    const availability = engineAvailability({
      engines: [
        { id: 'lexical', available: true },
        { id: 'semantic', available: false },
      ],
    })
    expect(availability).toEqual({ lexical: true, semantic: false })
  })

  it('sanitizes report filenames', () => {
    expect(buildReportFilename('PLG-ABC123')).toBe('paperpilot-plagiarism-PLG-ABC123.json')
    expect(buildReportFilename('../evil')).toBe('paperpilot-plagiarism-evil.json')
  })
})

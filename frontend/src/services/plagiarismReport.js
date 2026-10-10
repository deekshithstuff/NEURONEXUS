export function formatPercent(value, digits = 1) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '—'
  return `${(numeric * 100).toFixed(digits)}%`
}

const CLASSIFICATION_META = {
  suspected_unattributed: {
    label: 'Suspected unattributed',
    tone: 'danger',
    description: 'Overlaps an identified source with no nearby citation.',
  },
  external_match: {
    label: 'External match',
    tone: 'danger',
    description: 'Reported by the external provider; verify against the original source.',
  },
  quotation: {
    label: 'Quotation without citation',
    tone: 'warning',
    description: 'Quoted text that still needs an in-text citation.',
  },
  cited_match: {
    label: 'Cited match',
    tone: 'info',
    description: 'Overlaps a source and includes an in-text citation.',
  },
  attributed_quotation: {
    label: 'Attributed quotation',
    tone: 'good',
    description: 'Properly quoted and cited.',
  },
  semantic_related: {
    label: 'Semantic similarity',
    tone: 'neutral',
    description: 'Topically similar; semantics alone are not evidence of plagiarism.',
  },
}

export function classificationMeta(classification) {
  return CLASSIFICATION_META[classification] || {
    label: (classification || 'match').replaceAll('_', ' '),
    tone: 'neutral',
    description: 'Similarity signal to review.',
  }
}

export function providerLabel(provider) {
  if (!provider) return 'Internal corpus comparison'
  if (provider.startsWith('external:')) return `External provider (${provider.split(':')[1]})`
  return 'Internal corpus comparison'
}

export function summarizeScan(report) {
  const summary = report?.summary || {}
  return [
    { key: 'overall', label: 'Overall similarity', value: formatPercent(summary.overall_similarity), detail: `${summary.matched_words || 0} of ${summary.total_words || 0} words` },
    { key: 'suspected', label: 'Suspected unattributed', value: formatPercent(summary.suspected_unattributed_ratio), detail: `${summary.suspected_unattributed_words || 0} words flagged` },
    { key: 'sources', label: 'Sources matched', value: summary.source_count || 0, detail: 'identified corpus sources' },
    { key: 'matches', label: 'Matching passages', value: summary.match_count || 0, detail: `${summary.quotation_match_count || 0} quoted` },
  ]
}

export function buildReportFilename(scanId) {
  const safe = (scanId || 'report').replace(/[^A-Za-z0-9._-]/g, '').replace(/^\.+/, '')
  return `paperpilot-plagiarism-${safe || 'report'}.json`
}

export function engineAvailability(statusConfig) {
  const engines = statusConfig?.engines || []
  return {
    lexical: engines.find((engine) => engine.id === 'lexical')?.available !== false,
    semantic: Boolean(engines.find((engine) => engine.id === 'semantic')?.available),
  }
}

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  Download,
  Info,
  Link2,
  FileUp,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
  Trash2,
} from 'lucide-react'
import { researchApi } from './services/api'
import {
  buildReportFilename,
  classificationMeta,
  engineAvailability,
  formatPercent,
  providerLabel,
  summarizeScan,
} from './services/plagiarismReport'

const TONE_MARK = { danger: 'warning', warning: 'warning', info: 'neutral', neutral: 'neutral', good: 'good' }
const SOURCE_HIGHLIGHTS = ['#fff1a8', '#d9ecff', '#e8d9ff', '#d8f1df', '#ffdce5', '#d4f0f0']

function LoadingStatus({ label }) {
  return (
    <div className="status-box" role="status">
      <strong>{label}</strong>
      <p>This can take a moment while every passage is compared against the identified sources.</p>
    </div>
  )
}

export default function PlagiarismPage({ document, setActive }) {
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState('')
  const [provider, setProvider] = useState('internal')
  const [useSemantic, setUseSemantic] = useState(false)
  const [consent, setConsent] = useState(false)
  const [phase, setPhase] = useState('idle')
  const [scan, setScan] = useState(null)
  const [error, setError] = useState('')
  const [isDownloading, setIsDownloading] = useState(false)
  const [referenceDocuments, setReferenceDocuments] = useState([])
  const [isIndexingReference, setIsIndexingReference] = useState(false)
  const [referenceError, setReferenceError] = useState('')
  const [matchFilter, setMatchFilter] = useState('all')
  const mounted = useRef(true)
  const activeScanId = useRef(null)

  useEffect(() => {
    mounted.current = true
    researchApi
      .getPlagiarismStatus()
      .then((payload) => setConfig(payload))
      .catch((requestError) => setConfigError(requestError.message || 'Plagiarism configuration is unavailable.'))
    researchApi
      .getPlagiarismReferences()
      .then((payload) => setReferenceDocuments(payload.documents || []))
      .catch((requestError) => setReferenceError(requestError.message || 'The local reference index is unavailable.'))
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    activeScanId.current = null
    setScan(null)
    setPhase('idle')
    setError('')
  }, [document?.document_id])

  const externalAvailable = Boolean(config?.external?.configured)
  const availability = engineAvailability(config)

  const refreshReferences = async () => {
    const [references, status] = await Promise.all([
      researchApi.getPlagiarismReferences(),
      researchApi.getPlagiarismStatus(),
    ])
    setReferenceDocuments(references.documents || [])
    setConfig(status)
  }

  const uploadReference = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setReferenceError('')
    setIsIndexingReference(true)
    try {
      const result = await researchApi.uploadPlagiarismReference(file)
      await refreshReferences()
      if (result.status !== 'indexed') setReferenceError(result.error || `Reference status: ${result.status}.`)
    } catch (requestError) {
      setReferenceError(requestError.message || 'The PDF could not be indexed.')
    } finally {
      setIsIndexingReference(false)
    }
  }

  const removeReference = async (referenceId) => {
    setReferenceError('')
    try {
      await researchApi.deletePlagiarismReference(referenceId)
      await refreshReferences()
    } catch (requestError) {
      setReferenceError(requestError.message || 'The reference could not be removed.')
    }
  }

  const reindexReference = async (referenceId) => {
    setReferenceError('')
    try {
      await researchApi.reindexPlagiarismReference(referenceId)
      await refreshReferences()
    } catch (requestError) {
      setReferenceError(requestError.message || 'The reference could not be re-indexed.')
    }
  }

  const pollScan = useCallback(async (scanId) => {
    for (let attempt = 0; attempt < 150; attempt += 1) {
      const payload = await researchApi.getPlagiarismScan(scanId)
      if (!mounted.current || activeScanId.current !== scanId) return
      setScan(payload)
      if (payload.status === 'completed') {
        setPhase('completed')
        return
      }
      if (payload.status === 'failed') {
        setPhase('failed')
        setError(payload.error || 'The similarity scan could not be completed.')
        return
      }
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    if (mounted.current && activeScanId.current === scanId) {
      setPhase('failed')
      setError('The scan is taking longer than expected. Please try again.')
    }
  }, [])

  const startScan = async () => {
    if (!document?.document_id) {
      setError('Open an analyzed manuscript before running a similarity scan.')
      return
    }
    if (provider === 'external' && !consent) {
      setError('Please confirm consent before sending the manuscript to an external provider.')
      return
    }
    setError('')
    setScan(null)
    setPhase('starting')
    try {
      const engines = ['lexical', ...(useSemantic && availability.semantic ? ['semantic'] : [])]
      const started = await researchApi.startPlagiarismScan(document.document_id, {
        provider,
        engines,
        consent_external: consent,
      })
      activeScanId.current = started.scan_id
      setPhase('running')
      await pollScan(started.scan_id)
    } catch (requestError) {
      if (mounted.current) {
        setPhase('failed')
        setError(requestError.message || 'The similarity scan could not be started.')
      }
    }
  }

  const download = async () => {
    if (!scan?.scan_id) return
    setIsDownloading(true)
    setError('')
    try {
      const link = globalThis.document.createElement('a')
      link.href = await researchApi.buildDownloadUrl(`/api/plagiarism/scans/${scan.scan_id}/download`)
      link.download = buildReportFilename(scan.scan_id)
      link.rel = 'noopener'
      link.style.display = 'none'
      globalThis.document.body.appendChild(link)
      link.click()
      setTimeout(() => link.remove(), 1500)
    } catch (requestError) {
      setError(requestError.message || 'Could not download the similarity report.')
    } finally {
      if (mounted.current) setIsDownloading(false)
    }
  }

  const report = scan?.report || null
  const stats = report ? summarizeScan(report) : []
  const busy = phase === 'starting' || phase === 'running'
  const sourceColors = new Map((report?.sources || []).map((source, index) => [source.id, SOURCE_HIGHLIGHTS[index % SOURCE_HIGHLIGHTS.length]]))
  const visibleMatches = (report?.matches || []).filter((match) => matchFilter === 'all' || match.method === matchFilter)

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">ORIGINALITY & ATTRIBUTION</p>
          <h1>Plagiarism check<span className="period">.</span></h1>
          <p className="subtitle">
            Compare the manuscript against clearly identified sources, then review matching passages
            and citations. Similarity is not a verdict.
          </p>
        </div>
        <button type="button" className="outline-button" onClick={() => setActive('citations')}>
          Review citations <ArrowUpRight size={16} />
        </button>
      </section>

      <section className="panel reference-corpus-panel">
        <div className="panel-heading">
          <div><p className="kicker">LOCAL REFERENCE CORPUS</p><h2>Manage comparison PDFs</h2></div>
          <label className="outline-button reference-upload-button">
            <FileUp size={16} /> {isIndexingReference ? 'Indexing PDF…' : 'Add reference PDF'}
            <input type="file" accept="application/pdf,.pdf" onChange={uploadReference} disabled={isIndexingReference || busy} />
          </label>
        </div>
        <p className="reference-scope-note">
          Local comparison uses this account’s indexed PDFs and the configured local corpus; it does not search all scholarly content or the internet.
          Any external provider is a separate optional scan. Similarity is evidence for review, not proof of plagiarism.
        </p>
        <div className="plag-meta">
          <span><Info size={14} /> {config?.corpus?.source_count ?? '—'} searchable local sources</span>
          <span><Info size={14} /> {config?.reference_index?.indexed_count ?? 0} account PDFs indexed</span>
          <span><Info size={14} /> Last index update: {config?.reference_index?.last_indexed_at || 'none yet'}</span>
          {(config?.reference_index?.failure_count || 0) > 0 && <span>{config.reference_index.failure_count} PDF(s) need review</span>}
          <span><Info size={14} /> PDF text extraction only; scanned files need OCR</span>
        </div>
        {referenceError && <div className="status-box error-box" role="alert">{referenceError}</div>}
        {referenceDocuments.length === 0 ? (
          <div className="status-box"><strong>No account PDFs indexed yet.</strong><p>Add reference papers you are permitted to use for comparison.</p></div>
        ) : (
          <div className="reference-document-list">
            {referenceDocuments.map((reference) => (
              <article className="reference-document" key={reference.id}>
                <div>
                  <strong>{reference.title}</strong>
                  <span>{reference.filename} · {reference.page_count} page(s){reference.year ? ` · ${reference.year}` : ''}</span>
                  {reference.authors?.length > 0 && <span>{reference.authors.join(', ')}</span>}
                  <span className={`reference-status ${reference.status}`}>{reference.status.replaceAll('_', ' ')}</span>
                  {reference.error && <span className="reference-error">{reference.error}</span>}
                  {reference.duplicate_of && <span>Duplicate of {reference.duplicate_of}</span>}
                </div>
                <div className="reference-actions">
                  {reference.status !== 'indexed' && (
                    <button type="button" className="outline-button" onClick={() => reindexReference(reference.id)} disabled={busy || isIndexingReference}>Re-index</button>
                  )}
                  <button type="button" className="icon-button" aria-label={`Remove ${reference.filename}`} onClick={() => removeReference(reference.id)} disabled={busy || isIndexingReference}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {!document?.document_id && (
        <section className="status-box">
          <strong>No manuscript loaded.</strong>
          <p>Add references above, then upload a DOCX or PDF manuscript to run a comparison.</p>
          <button type="button" className="outline-button" onClick={() => setActive('upload')}>Upload manuscript</button>
        </section>
      )}

      {document?.document_id && <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="kicker">SCAN SETUP</p>
            <h2>Run a similarity scan</h2>
          </div>
          <div className="score-badge">{providerLabel(provider)}</div>
        </div>

        <div className="plag-controls">
          <label className="plag-field">
            <span>Comparison provider</span>
            <select value={provider} onChange={(event) => setProvider(event.target.value)} disabled={busy}>
              <option value="internal">Internal corpus comparison</option>
              <option value="external" disabled={!externalAvailable}>
                External provider{externalAvailable ? '' : ' (not configured)'}
              </option>
            </select>
          </label>

          <fieldset className="plag-engines" disabled={busy}>
            <legend>Matching engines</legend>
            <label className="plag-check">
              <input type="checkbox" checked readOnly />
              <span>Exact &amp; near-exact text matching</span>
            </label>
            <label className="plag-check">
              <input
                type="checkbox"
                checked={useSemantic}
                onChange={(event) => setUseSemantic(event.target.checked)}
                disabled={!availability.semantic}
              />
              <span>
                Semantic similarity (Sentence Transformers)
                {!availability.semantic ? ' — not installed on the server' : ''}
              </span>
            </label>
          </fieldset>

          {provider === 'external' && (
            <label className="plag-check plag-consent">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} disabled={busy} />
              <span>I consent to sending the extracted manuscript text to the external provider for comparison.</span>
            </label>
          )}

          <div className="plag-meta">
            <span><Info size={14} /> Corpus sources: {config?.corpus?.source_count ?? '—'}</span>
            <span><Info size={14} /> {config?.external?.message || configError || 'Loading configuration…'}</span>
          </div>

          <div className="button-row">
            <button type="button" className="primary-button" onClick={startScan} disabled={busy}>
              {busy ? <RefreshCw size={16} className="spin" /> : <ScanSearch size={16} />}
              {phase === 'completed' ? 'Re-run scan' : 'Start similarity scan'}
            </button>
            {report && scan?.status === 'completed' && (
              <button type="button" className="outline-button" onClick={download} disabled={isDownloading}>
                <Download size={16} /> {isDownloading ? 'Preparing…' : 'Download report'}
              </button>
            )}
          </div>
        </div>

        {error && <div className="status-box error-box" role="alert">{error}</div>}
        {busy && <LoadingStatus label={phase === 'starting' ? 'Starting scan…' : 'Scanning manuscript…'} />}
      </section>

      {report && (
        <>
          {report.scope?.corpus?.version && config?.corpus?.version && report.scope.corpus.version !== config.corpus.version && (
            <div className="status-box" role="status">
              <strong>The local corpus changed after this report was created.</strong>
              <p>Run the scan again to compare against the current reference set.</p>
            </div>
          )}
          <div className="status-box" role="status">
            <strong>{providerLabel(report.provider)}</strong>
            <p>{report.disclaimer}</p>
          </div>

          <section className="stats-grid compact-grid">
            {stats.map((stat) => (
              <div className="stat-card" key={stat.key}>
                <div className="stat-icon"><ScanSearch size={17} /></div>
                <div>
                  <span className="stat-label">{stat.label}</span>
                  <div className="stat-number">{stat.value}</div>
                  <span className="stat-detail">{stat.detail}</span>
                </div>
              </div>
            ))}
          </section>

          <div className="detail-grid two-col">
            <section className="panel">
              <div className="panel-heading">
                <div><p className="kicker">SOURCES</p><h2>Identified matches</h2></div>
              </div>
              <div className="finding-list">
                {(report.sources || []).length === 0 ? (
                  <div className="finding">
                    <span className="finding-mark good"><Check size={14} /></span>
                    <div><strong>No source overlap detected</strong><span>The manuscript does not overlap the identified corpus.</span></div>
                  </div>
                ) : (
                  (report.sources || []).map((source) => (
                    <div className="finding" key={source.id}>
                      <span className="finding-mark warning">!</span>
                      <div>
                        <strong>{source.title}</strong>
                        <span>
                          {source.matched_words} words · {source.passage_count} passage(s) ·{' '}
                          {formatPercent(source.max_similarity)} peak match
                          {' · '}{formatPercent(source.similarity)} source similarity
                          {source.filename && ` · ${source.filename}`}
                          {source.url && (
                            <>
                              {' · '}
                              <a href={source.url} target="_blank" rel="noopener noreferrer"><Link2 size={12} /> open source</a>
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div><p className="kicker">CITATIONS</p><h2>Citation warnings</h2></div>
              </div>
              <div className="finding-list">
                {(report.citation_warnings || []).length === 0 ? (
                  <div className="finding">
                    <span className="finding-mark good"><Check size={14} /></span>
                    <div><strong>No citation warnings</strong><span>No unattributed overlap or reference issues were flagged.</span></div>
                  </div>
                ) : (
                  (report.citation_warnings || []).map((warning, index) => (
                    <div className="finding" key={`${warning.type}-${index}`}>
                      <span className="finding-mark warning">!</span>
                      <div>
                        <strong>{warning.type?.replaceAll('_', ' ') || 'warning'}</strong>
                        <span>{warning.message} {warning.suggestion || ''}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>

          <section className="panel">
            <div className="panel-heading">
              <div><p className="kicker">PASSAGES</p><h2>Matching passages</h2></div>
              <label className="plag-filter">Filter
                <select value={matchFilter} onChange={(event) => setMatchFilter(event.target.value)}>
                  <option value="all">All match types</option>
                  <option value="exact">Exact</option>
                  <option value="near_exact">Near-exact</option>
                  <option value="semantic">Semantic candidate</option>
                </select>
              </label>
            </div>
            <div className="plag-matches">
              <div className="source-highlight-legend" aria-label="Source highlight legend">
                {(report.sources || []).map((source) => (
                  <span key={source.id}><i style={{ backgroundColor: sourceColors.get(source.id) }} />{source.title}</span>
                ))}
              </div>
              {(report.matches || []).length === 0 ? (
                <div className="status-box"><strong>No matching passages</strong><p>Nothing in the manuscript overlapped the identified sources.</p></div>
              ) : visibleMatches.length === 0 ? (
                <div className="status-box"><strong>No matches for this filter.</strong><p>Choose another match type to review evidence.</p></div>
              ) : (
                visibleMatches.map((match) => {
                  const meta = classificationMeta(match.classification)
                  return (
                    <article className={`plag-match ${meta.tone}`} key={match.id}>
                      <div className="plag-match-head">
                        <span className={`plag-badge ${meta.tone}`}>{meta.label}</span>
                        <small>
                          {match.method} · {formatPercent(match.similarity)} similarity
                          {match.coverage != null ? ` · ${formatPercent(match.coverage)} coverage` : ''}
                        </small>
                      </div>
                      <div className="plag-evidence-grid">
                        <div>
                          <span className="evidence-label">MANUSCRIPT · paragraph {match.location?.paragraph_number ?? '—'}</span>
                          <mark className="plag-mark" style={{ backgroundColor: sourceColors.get(match.source?.id) || SOURCE_HIGHLIGHTS[0] }}>{match.passage}</mark>
                        </div>
                        <div>
                          <span className="evidence-label">SOURCE · page {match.source_location?.page ?? '—'}</span>
                          <p className="plag-mark source-excerpt">{match.matched_text || 'Source excerpt unavailable.'}</p>
                        </div>
                      </div>
                      <div className="plag-match-source">
                        <span>
                          Located in {match.location?.section_heading || 'body'} · paragraph {match.location?.paragraph_number ?? '—'}
                        </span>
                        <span>Source: {match.source?.title}{match.source?.authors?.length ? ` · ${match.source.authors.join(', ')}` : ''}{match.source?.year ? ` · ${match.source.year}` : ''}</span>
                        {match.source?.filename && <span>File: {match.source.filename}</span>}
                        {match.source_location?.page && <span>Reference page: {match.source_location.page}</span>}
                        <span className="plag-note">{match.note || meta.description}</span>
                      </div>
                    </article>
                  )
                })
              )}
            </div>
          </section>

          <div className="detail-grid two-col">
            <section className="panel">
              <div className="panel-heading">
                <div><p className="kicker">TRANSPARENCY</p><h2>Exclusions</h2></div>
              </div>
              <div className="info-list">
                <p><strong>Reference list words excluded:</strong> {report.exclusions?.references_words_excluded ?? 0}</p>
                <p><strong>Quoted passages retained:</strong> {report.exclusions?.quoted_passages_retained ?? 0}</p>
                <p><strong>Boilerplate passages excluded:</strong> {report.exclusions?.boilerplate_passages_excluded ?? 0}</p>
                <ul className="mini-list">
                  {(report.exclusions?.notes || []).map((note) => <li key={note}>{note}</li>)}
                </ul>
              </div>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div><p className="kicker">SCOPE</p><h2>Scope &amp; limitations</h2></div>
              </div>
              <div className="info-list">
                <p><strong>Corpus:</strong> {report.scope?.corpus?.name} ({report.scope?.corpus?.source_count} sources)</p>
                <p><strong>Matcher version:</strong> {report.algorithm_version || 'legacy'}</p>
                <p><strong>Corpus fingerprint:</strong> {report.scope?.corpus?.version?.slice(0, 12) || 'unavailable'}</p>
                <p><strong>Engines:</strong> {(report.engines || []).map((engine) => `${engine.engine}: ${engine.status}`).join(', ')}</p>
                <ul className="mini-list">
                  {(report.scope?.limitations || []).map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
              </div>
            </section>
          </div>

          <section className="panel">
            <div className="panel-heading">
              <div><p className="kicker">SUPERVISED SIGNAL</p><h2>Retrieved candidate scores</h2></div>
            </div>
            <div className="info-list">
              <p>{report.classifier?.status?.detail || 'No trained classifier artifact is available.'}</p>
              <p>{report.classifier?.note || 'Classifier scores are separate from textual matching evidence.'}</p>
              {(report.classifier?.candidate_scores || []).slice(0, 5).map((candidate, index) => (
                <article className="plag-match" key={`${candidate.source?.id}-${candidate.passage_location?.paragraph_number}-${index}`}>
                  <div className="plag-match-source">
                    <strong>{candidate.source?.title || candidate.source?.id}</strong>
                    <span>
                      Paragraph {candidate.passage_location?.paragraph_number ?? '—'} · model score {Number(candidate.positive_score).toFixed(3)} ·
                      {' '}{candidate.predicted_label === 1 ? 'above' : 'below'} threshold {Number(candidate.threshold).toFixed(2)}
                    </span>
                    <span className="plag-snippet">Source passage: {candidate.source_passage}</span>
                    {candidate.source?.url && <a href={candidate.source.url} target="_blank" rel="noreferrer">View identified source</a>}
                  </div>
                </article>
              ))}
              {report.classifier?.status?.status === 'completed' && !report.classifier?.candidate_scores?.length && (
                <p>No source passages were retrieved for supervised scoring.</p>
              )}
            </div>
          </section>

          <div className="panel">
            <div className="panel-heading">
              <div><p className="kicker">INTEGRITY</p><h2>How to read this report</h2></div>
              <ShieldAlert size={18} />
            </div>
            <div className="info-list">
              <p>
                Matches are separated into <strong>attributed</strong> text (quotations and cited passages),
                <strong> suspected unattributed</strong> overlap, and <strong>semantic</strong> similarity.
                Only suspected unattributed overlap is counted as a potential integrity concern, and even then it is a
                signal to review — not proof of plagiarism.
              </p>
              <p><strong>Score:</strong> {report.summary?.score_status === 'insufficient_content' ? 'Unavailable because no eligible manuscript words were available.' : report.summary?.score_method}</p>
              <p>The original manuscript and its citations are never modified by this check.</p>
            </div>
          </div>
        </>
      )}
      </>}
    </>
  )
}

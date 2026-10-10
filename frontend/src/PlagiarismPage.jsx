import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  Download,
  Info,
  Link2,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
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
  const mounted = useRef(true)
  const activeScanId = useRef(null)

  useEffect(() => {
    mounted.current = true
    researchApi
      .getPlagiarismStatus()
      .then((payload) => setConfig(payload))
      .catch((requestError) => setConfigError(requestError.message || 'Plagiarism configuration is unavailable.'))
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

  if (!document?.document_id) {
    return (
      <section className="status-box">
        <strong>No manuscript loaded.</strong>
        <p>Upload a DOCX or PDF manuscript, then run a similarity scan from this tab.</p>
        <button type="button" className="outline-button" onClick={() => setActive('upload')}>Upload manuscript</button>
      </section>
    )
  }

  const report = scan?.report || null
  const stats = report ? summarizeScan(report) : []
  const busy = phase === 'starting' || phase === 'running'

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
                          {formatPercent(source.max_similarity)} peak similarity
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
            </div>
            <div className="plag-matches">
              {(report.matches || []).length === 0 ? (
                <div className="status-box"><strong>No matching passages</strong><p>Nothing in the manuscript overlapped the identified sources.</p></div>
              ) : (
                (report.matches || []).map((match) => {
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
                      <mark className="plag-mark">{match.passage}</mark>
                      <div className="plag-match-source">
                        <span>
                          Located in {match.location?.section_heading || 'body'} · paragraph {match.location?.paragraph_number ?? '—'}
                        </span>
                        <span>Source: {match.source?.title}</span>
                        {match.matched_text && <span className="plag-snippet">Matched text: “{match.matched_text}”</span>}
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
              <p>The original manuscript and its citations are never modified by this check.</p>
            </div>
          </div>
        </>
      )}
    </>
  )
}

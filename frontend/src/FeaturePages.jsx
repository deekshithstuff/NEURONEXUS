import { useEffect, useMemo, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  ClipboardCheck,
  Download,
  FileDown,
  FileText,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import { researchApi } from './services/api'

function NoAnalysis({ setActive }) {
  return (
    <section className="status-box">
      <strong>No manuscript analysis loaded.</strong>
      <p>Upload a DOCX or open a saved manuscript to use these tools.</p>
      <button type="button" className="outline-button" onClick={() => setActive('upload')}>Upload manuscript</button>
    </section>
  )
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/* ------------------------------------------------------------------ */
/* Compliance                                                           */
/* ------------------------------------------------------------------ */
export function CompliancePage({ document, setActive }) {
  const [articleTypes, setArticleTypes] = useState([])
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [isChecking, setIsChecking] = useState(false)

  useEffect(() => {
    researchApi.getArticleTypes().then(({ article_types }) => setArticleTypes(article_types || [])).catch(() => {})
  }, [])

  const runCheck = async () => {
    if (!document?.document_id) return
    setError('')
    setIsChecking(true)
    try {
      setReport(await researchApi.getCompliance(document.document_id))
    } catch (requestError) {
      setError(requestError.message || 'Compliance check failed.')
    } finally {
      setIsChecking(false)
    }
  }

  if (!document?.document_id) return <NoAnalysis setActive={setActive} />
  const counts = report?.counts || {}
  const failed = (report?.rules || []).filter((rule) => rule.status === 'failed')
  const warnings = (report?.rules || []).filter((rule) => rule.status === 'warning')
  const manual = report?.manual_review_required || []

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">JOURNAL PROFILE CHECK</p>
          <h1>Compliance check<span className="period">.</span></h1>
          <p className="subtitle">
            Rule-based structural and formatting checks against the selected profile.
          </p>
        </div>
        <button type="button" className="primary-button" onClick={runCheck} disabled={isChecking}>
          {isChecking ? <Loader2 size={16} className="spin" /> : <ClipboardCheck size={16} />}
          Run compliance check
        </button>
      </section>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {!report && !error && (
        <div className="status-box">
          Run the check to verify the manuscript against the selected profile rules. Items that cannot be verified
          automatically are marked for manual review instead of being decided for you.
        </div>
      )}
      {report && (
        <>
          <section className="stats-grid compact-grid">
            <StatTile label="Overall status" value={(report.overall_status || 'unknown').replace('_', ' ')} icon={ShieldCheck} tone={report.overall_status === 'passed' ? 'good' : report.overall_status === 'warning' ? 'warn' : 'bad'} />
            <StatTile label="Compliance score" value={`${report.compliance_score ?? '—'}`} suffix="/100" detail="automated rules only" icon={GaugeIcon} />
            <StatTile label="Rules" value={report.rules?.length || 0} detail={`${counts.failed || 0} failed · ${counts.warning || 0} warning`} icon={ClipboardCheck} />
            <StatTile label="Manual review" value={manual.length} detail="needs your verification" icon={Users} />
          </section>
          {failed.length > 0 && (
            <section className="panel">
              <div className="panel-heading"><div><p className="kicker">REQUIRED ACTIONS</p><h2>Failed rules</h2></div></div>
              <div className="finding-list">
                {failed.map((rule) => (
                  <div className="finding" key={rule.rule_id}>
                    <span className="finding-mark warning">!</span>
                    <div>
                      <strong>{rule.description}</strong>
                      <span>{rule.action || `Address this rule for the selected profile (${report.journal_name}).`}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
          {warnings.length > 0 && (
            <section className="panel">
              <div className="panel-heading"><div><p className="kicker">ONGOING</p><h2>Warnings</h2></div></div>
              <ul className="mini-list">
                {warnings.map((rule) => <li key={rule.rule_id}>{rule.description} — {rule.action || 'Review to confirm.'}</li>)}
              </ul>
            </section>
          )}
          <section className="panel">
            <div className="panel-heading"><div><p className="kicker">EVIDENCE</p><h2>Rule results</h2></div></div>
            <div className="data-table">
              {report.rules.map((rule) => (
                <div className="data-row" key={rule.rule_id}>
                  <span className={`status-chip ${rule.status}`}>{rule.status.replace('_', ' ')}</span>
                  <span className="data-main">{rule.description}<small>{rule.evidence}</small></span>
                  <span className="data-meta">{rule.rule_id}</span>
                </div>
              ))}
            </div>
            <p className="supporting-text">
              Profile source: {report.guide_source || report.journal_name || 'configured profile'} · verification: {report.guide_verification_status || 'unverified'}.
              {report.guide_source_url ? <a href={report.guide_source_url} target="_blank" rel="noreferrer">Review publisher instructions <ArrowUpRight size={12} /></a> : null}
            </p>
          </section>
        </>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Analytics                                                            */
/* ------------------------------------------------------------------ */
export function AnalyticsPage({ document, setActive }) {
  const [dashboard, setDashboard] = useState(null)
  const [versions, setVersions] = useState([])
  const [versionId, setVersionId] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const load = async (targetVersion) => {
    if (!document?.document_id) return
    setError('')
    setIsLoading(true)
    try {
      const params = targetVersion ? { version_id: targetVersion } : {}
      setDashboard(await researchApi.getAnalytics(document.document_id, params))
    } catch (requestError) {
      setError(requestError.message || 'Analytics could not be loaded.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!document?.document_id) return
    researchApi.getVersions(document.document_id)
      .then((result) => setVersions(result.versions || []))
      .catch(() => {})
    load('')
  }, [document?.document_id])

  const exportJson = async () => {
    try {
      const params = versionId ? { version_id: versionId } : {}
      const blob = await researchApi.exportAnalytics(document.document_id, params)
      downloadBlob(blob, `paperpilot-analytics-${document.document_id}.json`)
    } catch (requestError) {
      setError(requestError.message || 'Export failed.')
    }
  }

  if (!document?.document_id) return <NoAnalysis setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">SUBMISSION INTELLIGENCE</p>
          <h1>Analytics dashboard<span className="period">.</span></h1>
          <p className="subtitle">{dashboard ? `${dashboard.journal_name || 'Selected profile'} · ${dashboard.access_role} access` : 'Aggregated, evidence-based metrics for this manuscript.'}</p>
        </div>
        <div className="button-row">
          {versions.length > 0 && (
            <select className="filter-select" value={versionId} onChange={(event) => { setVersionId(event.target.value); load(event.target.value) }}>
              <option value="">Latest version</option>
              {versions.map((version) => (
                <option key={version.version_id} value={version.version_id}>Version {version.version_number}{version.label ? ` — ${version.label}` : ''}</option>
              ))}
            </select>
          )}
          <button type="button" className="primary-button" onClick={() => load(versionId)} disabled={isLoading}>
            {isLoading ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />} Refresh
          </button>
          <button type="button" className="outline-button" onClick={exportJson}><Download size={16} /> Export JSON</button>
        </div>
      </section>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {!dashboard && !error && (
        <div className="status-box">Loading the analytics dashboard…</div>
      )}
      {dashboard && (
        <>
          <section className="indicator-grid">
            {dashboard.indicators.map((indicator) => (
              <div className="indicator-card" key={indicator.key}>
                <div className="indicator-top">
                  <span className="kicker">{indicator.label}</span>
                  <span className={`status-chip ${indicator.available ? 'passed' : 'unavailable'}`}>
                    {indicator.available ? 'available' : 'unavailable'}
                  </span>
                </div>
                <div className="indicator-value">
                  {indicator.available
                    ? `${typeof indicator.value === 'number' ? (Math.round(indicator.value * 100) / 100) : indicator.value}${indicator.unit ? ` <small>${indicator.unit}</small>` : ''}`
                    : '—'}
                </div>
                <p className="indicator-method">{indicator.method}</p>
                <p className="indicator-detail">{indicator.interpretation}</p>
                {indicator.inputs && <p className="supporting-text">Inputs: {indicator.inputs}</p>}
                {indicator.key === 'similarity' && dashboard.indicators.find((item) => item.key === 'similarity') ? (
                  <p className="supporting-text">Similarity is not a verdict and does not prove plagiarism.</p>
                ) : null}
              </div>
            ))}
          </section>

          {dashboard.prioritized_actions?.length > 0 && (
            <section className="panel">
              <div className="panel-heading"><div><p className="kicker">PRIORITIZED</p><h2>Recommended actions</h2><span className="supporting-text">Each action requires your explicit approval before it can change the manuscript.</span></div></div>
              <div className="finding-list">
                {dashboard.prioritized_actions.map((action, index) => (
                  <div className="finding" key={`${index}-${action.title}`}>
                    <span className={`finding-mark ${action.priority === 'CRITICAL' ? 'warning' : 'neutral'}`}>{action.priority === 'CRITICAL' ? '!' : '•'}</span>
                    <div>
                      <strong>{action.title}</strong>
                      <span>{action.detail}</span>
                    </div>
                    <span className={`status-chip ${action.priority === 'CRITICAL' ? 'warning' : 'passed'}`}>{action.priority}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="detail-grid two-col">
            <section className="panel">
              <div className="panel-heading"><div><p className="kicker">HISTORY</p><h2>Versions</h2></div></div>
              {dashboard.versions?.length ? (
                <div className="data-table">
                  {dashboard.versions.map((version) => (
                    <div className="data-row" key={version.version_id}>
                      <span className="status-chip passed">v{version.version_number}</span>
                      <span className="data-main">{version.label || 'Unlabeled version'}<small>{version.change_summary || 'No summary provided.'}</small></span>
                      <span className="data-meta">{version.created_at}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="supporting-text">No versions have been recorded.</p>}
            </section>
            <section className="panel">
              <div className="panel-heading"><div><p className="kicker">SCOPE</p><h2>Integrity notes</h2></div></div>
              <ul className="mini-list">
                <li>{dashboard.evidence_scope}</li>
                <li>{dashboard.disclaimer}</li>
                <li>Snapshot: {dashboard.snapshot_id} · Generated {dashboard.generated_at}</li>
              </ul>
            </section>
          </section>
        </>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Conversion                                                           */
/* ------------------------------------------------------------------ */
export function ConversionPage({ document, setActive }) {
  const [journalList, setJournalList] = useState([])
  const [articleTypes, setArticleTypes] = useState([])
  const [articleType, setArticleType] = useState('original_research')
  const [selected, setSelected] = useState([])
  const [jobs, setJobs] = useState([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [isStarting, setIsStarting] = useState(false)

  useEffect(() => {
    researchApi.getJournals()
      .then(({ journals }) => setJournalList(journals || []))
      .catch((requestError) => setError(requestError.message || 'Could not load journal profiles.'))
    researchApi.getArticleTypes()
      .then(({ article_types: types }) => setArticleTypes(types || []))
      .catch((requestError) => setError(requestError.message || 'Could not load article types.'))
    if (!document?.document_id) return undefined
    const refreshJobs = () => researchApi.getConversions(document.document_id)
      .then(({ jobs: currentJobs }) => setJobs(currentJobs || []))
      .catch((requestError) => setError(requestError.message || 'Could not refresh conversion status.'))
    refreshJobs()
    const timer = window.setInterval(refreshJobs, 1500)
    return () => window.clearInterval(timer)
  }, [document?.document_id])

  const visibleJournals = useMemo(() => journalList.filter((journal) => (
    `${journal.journal_name || ''} ${journal.publisher || ''} ${journal.journal_id || ''}`
      .toLowerCase().includes(search.trim().toLowerCase())
  )), [journalList, search])

  const start = async () => {
    if (!document?.document_id || selected.length === 0) return
    setError('')
    setIsStarting(true)
    try {
      const result = await researchApi.startConversion(document.document_id, { journal_ids: selected, article_type: articleType })
      setJobs([...(result.jobs || []), ...jobs])
      setSelected([])
    } catch (requestError) {
      setError(requestError.message || 'Conversion could not be started.')
    } finally {
      setIsStarting(false)
    }
  }

  const toggleJournal = (journalId) => {
    setSelected((current) => (current.includes(journalId) ? current.filter((id) => id !== journalId) : [...current, journalId]))
  }

  const downloadJob = async (jobId, format) => {
    try {
      const blob = await researchApi.downloadConversion(jobId, format)
      downloadBlob(blob, format === 'docx' ? 'converted.docx' : 'converted.pdf')
    } catch (requestError) {
      setError(requestError.message || 'Download failed.')
    }
  }

  const retryJob = async (jobId) => {
    setError('')
    try {
      const job = await researchApi.retryConversion(jobId)
      setJobs((current) => current.map((item) => item.job_id === jobId ? job : item))
    } catch (requestError) {
      setError(requestError.message || 'Could not retry this conversion.')
    }
  }

  if (!document?.document_id) return <NoAnalysis setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">MULTI-JOURNAL CONVERSION</p>
          <h1>Convert for journals<span className="period">.</span></h1>
          <p className="subtitle">Generate journal-targeted exports. Conversions are advisory reconstructions and do not overwrite your source manuscript.</p>
          <p className="supporting-text">{document.title || document.filename || document.document_id} · {document.filename || 'Analyzed manuscript'} · Ready for conversion</p>
        </div>
        <button type="button" className="primary-button" onClick={start} disabled={isStarting || selected.length === 0}>
          {isStarting ? <Loader2 size={16} className="spin" /> : <FileDown size={16} />}
          Convert {selected.length > 0 ? `(${selected.length})` : ''}
        </button>
      </section>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">TARGETS</p><h2>Select journals</h2></div></div>
        <label className="muted-label" htmlFor="conversion-article-type">Article type</label>
        <select id="conversion-article-type" className="filter-select" value={articleType} onChange={(event) => setArticleType(event.target.value)}>
          {articleTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
        </select>
        <input className="text-input" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search journals or publishers" aria-label="Search journals" />
        <div className="chip-row">
          {visibleJournals.map((journal) => {
            const active = selected.includes(journal.journal_id)
            return (
              <button key={journal.journal_id} type="button"
                className={`journal-chip ${active ? 'active' : ''}`}
                onClick={() => toggleJournal(journal.journal_id)}>
                {active ? <Check size={14} /> : <PlusIcon size={14} />}{journal.journal_name || journal.journal_id}
              </button>
            )
          })}
        </div>
        {selected.length > 0 && (
          <div className="data-table">
            <h3>Requirements comparison</h3>
            {journalList.filter((journal) => selected.includes(journal.journal_id)).map((journal) => (
              <div className="data-row" key={journal.journal_id}>
                <span className="data-main">{journal.journal_name || journal.journal_id}
                  <small>{journal.publisher || 'Publisher unspecified'} · {journal.template_name || 'Generic profile'}</small>
                  <small>{journal.page_size || 'Page size unknown'} · {journal.columns || 1} column(s) · {journal.font || 'Font unspecified'} {journal.font_size || ''} pt</small>
                  <small>{journal.word_limit ? `Word limit: ${journal.word_limit}` : 'Word limit unknown'} · Citation style: {journal.citation_style || 'unknown'}</small>
                  <small>{journal.guideline?.verification_status || 'unverified'} profile; check the venue's current instructions.</small>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">JOBS</p><h2>Conversion history</h2></div></div>
        {jobs.length === 0 ? (
          <p className="supporting-text">No conversions yet. Select a journal and start a new job.</p>
        ) : (
          <div className="data-table">
            {jobs.map((job) => (
              <div className="data-row" key={job.job_id}>
                <span className={`status-chip ${job.status}`}>{job.status}</span>
                <span className="data-main">{job.journal_id}<small>{job.article_type || 'research article'} · {job.job_id}</small></span>
                <span className="data-meta">
                  {job.status === 'completed' ? (
                    <span className="button-row small-actions">
                      <button type="button" className="outline-button" onClick={() => downloadJob(job.job_id, 'docx')}>DOCX</button>
                      <button type="button" className="outline-button" onClick={() => downloadJob(job.job_id, 'pdf')}>PDF</button>
                      <button type="button" className="outline-button" onClick={() => downloadJob(job.job_id, 'compliance_json')}>Report</button>
                    </span>
                  ) : job.status === 'failed' ? (
                    <span className="button-row small-actions">
                      <span className="supporting-text">{job.error || 'Conversion failed.'}</span>
                      <button type="button" className="outline-button" onClick={() => retryJob(job.job_id)}>Retry</button>
                    </span>
                  ) : (
                    <span className="supporting-text">{job.status === 'running' ? 'Formatting and validating…' : 'Waiting to start…'}</span>
                  )}
                </span>
                {job.status === 'completed' && job.result?.compliance_summary && (
                  <span className="supporting-text">Compliance: {job.result.compliance_summary.overall_status}; {job.result.warnings?.length || 0} formatting warning(s)</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Collaboration                                                        */
/* ------------------------------------------------------------------ */
const COLLABORATION_TABS = [
  { id: 'people', label: 'Collaborators', icon: Users },
  { id: 'comments', label: 'Comments', icon: ClipboardCheck },
  { id: 'versions', label: 'Versions', icon: FileText },
  { id: 'reviews', label: 'Reviews', icon: ShieldCheck },
]

export function CollaborationPage({ document, setActive }) {
  const [tab, setTab] = useState('people')
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">COLLABORATIVE REVIEW</p>
          <h1>Collaborate<span className="period">.</span></h1>
          <p className="subtitle">Invite reviewers and editors, leave comments, manage versions, and record review decisions.</p>
        </div>
        <div className="tabs-row">
          {COLLABORATION_TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" className={`tab-button ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>
              <Icon size={14} />{label}
            </button>
          ))}
        </div>
      </section>
      {!document?.document_id ? <NoAnalysis setActive={setActive} /> : (
        <>
          {tab === 'people' && <PeopleTab documentId={document.document_id} />}
          {tab === 'comments' && <CommentsTab documentId={document.document_id} />}
          {tab === 'versions' && <VersionsTab documentId={document.document_id} />}
          {tab === 'reviews' && <ReviewsTab documentId={document.document_id} />}
        </>
      )}
    </>
  )
}

function PeopleTab({ documentId }) {
  const [collaborators, setCollaborators] = useState([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('reviewer')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const refresh = async () => {
    try {
      const result = await researchApi.getCollaborators(documentId)
      setCollaborators(result.collaborators || [])
    } catch (requestError) {
      setError(requestError.message || 'Could not load collaborators.')
    }
  }
  useEffect(() => { refresh() }, [documentId])

  const invite = async () => {
    setError(''); setMessage('')
    try {
      const result = await researchApi.inviteCollaborator(documentId, { email, role })
      setMessage(`Invitation sent to ${result.email} (${result.role}, ${result.status}).`)
      setEmail('')
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Invitation failed.')
    }
  }

  const updateRole = async (collaboratorId, nextRole) => {
    try {
      await researchApi.updateCollaborator(documentId, collaboratorId, { role: nextRole })
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Update failed.')
    }
  }

  const remove = async (collaboratorId) => {
    try {
      await researchApi.removeCollaborator(documentId, collaboratorId)
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Remove failed.')
    }
  }

  return (
    <>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {message && <div className="status-box success-box" role="status">{message}</div>}
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">INVITE</p><h2>Add a collaborator</h2></div></div>
        <div className="form-row">
          <input type="email" className="text-input" placeholder="person@example.org" value={email} onChange={(event) => setEmail(event.target.value)} />
          <select className="filter-select" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="viewer">Viewer</option>
            <option value="reviewer">Reviewer</option>
            <option value="editor">Editor</option>
          </select>
          <button type="button" className="primary-button" onClick={invite} disabled={!email.trim()}><Users size={15} /> Invite</button>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">TEAM</p><h2>Collaborators</h2></div></div>
        {collaborators.length === 0 ? (
          <p className="supporting-text">No collaborators yet. Invitations to registered users are accepted automatically.</p>
        ) : (
          <div className="data-table">
            {collaborators.map((collaborator) => (
              <div className="data-row" key={collaborator.collaborator_id}>
                <span className="data-main">{collaborator.email}<small>{collaborator.status} · role: {collaborator.role}</small></span>
                <span className="data-meta">
                  <select className="filter-select compact" value={collaborator.role} onChange={(event) => updateRole(collaborator.collaborator_id, event.target.value)}>
                    {['viewer', 'reviewer', 'editor'].map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                  <button type="button" className="text-button danger" onClick={() => remove(collaborator.collaborator_id)}><X size={13} /> Remove</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">CAPABILITIES</p><h2>Role limits</h2></div></div>
        <ul className="mini-list">
          <li>Viewers can read and view results only.</li>
          <li>Reviewers can comment and submit review decisions.</li>
          <li>Editors can edit, generate exports, manage versions, convert, and comment.</li>
          <li>Only the owner (or an admin) can manage collaborators.</li>
        </ul>
      </section>
    </>
  )
}

function CommentsTab({ documentId }) {
  const [comments, setComments] = useState([])
  const [body, setBody] = useState('')
  const [sectionRef, setSectionRef] = useState('')
  const [error, setError] = useState('')

  const refresh = async () => {
    try {
      setComments((await researchApi.getComments(documentId)).comments || [])
    } catch (requestError) {
      setError(requestError.message || 'Could not load comments.')
    }
  }
  useEffect(() => { refresh() }, [documentId])

  const add = async () => {
    setError('')
    try {
      await researchApi.addComment(documentId, { body, section_ref: sectionRef || null })
      setBody(''); setSectionRef('')
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Comment could not be added.')
    }
  }

  const resolve = async (commentId) => {
    try {
      await researchApi.resolveComment(documentId, commentId, { resolved: true })
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Comment could not be resolved.')
    }
  }

  return (
    <>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">NEW</p><h2>Add a comment</h2></div></div>
        <div className="form-row stacked">
          <input type="text" className="text-input" placeholder="Section reference, e.g. Methods" value={sectionRef} onChange={(event) => setSectionRef(event.target.value)} />
          <textarea className="text-input" rows="3" placeholder="Comment for the author…" value={body} onChange={(event) => setBody(event.target.value)} />
          <div><button type="button" className="primary-button" onClick={add} disabled={!body.trim()}>Add comment</button></div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">THREAD</p><h2>Comments</h2></div></div>
        {comments.length === 0 ? (
          <p className="supporting-text">No comments yet.</p>
        ) : (
          <div className="finding-list">
            {comments.map((comment) => (
              <div className="finding" key={comment.comment_id}>
                <span className={`finding-mark ${comment.status === 'resolved' ? 'good' : 'neutral'}`}>{comment.status === 'resolved' ? <Check size={14} /> : '•'}</span>
                <div>
                  <strong>{comment.section_ref || comment.author_name || 'Comment'}</strong>
                  <span>{comment.body}</span>
                </div>
                {comment.status === 'open' && (
                  <button type="button" className="text-button" onClick={() => resolve(comment.comment_id)}>Resolve</button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

function VersionsTab({ documentId }) {
  const [versions, setVersions] = useState([])
  const [label, setLabel] = useState('')
  const [summary, setSummary] = useState('')
  const [diff, setDiff] = useState(null)
  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const refresh = async () => {
    try {
      const result = await researchApi.getVersions(documentId)
      setVersions(result.versions || [])
      if (!fromVersion && result.versions?.length > 1) { setFromVersion(result.versions[1].version_id); setToVersion(result.versions[0].version_id) }
    } catch (requestError) {
      setError(requestError.message || 'Could not load versions.')
    }
  }
  useEffect(() => { refresh() }, [documentId])

  const create = async () => {
    setError(''); setMessage('')
    try {
      await researchApi.createVersion(documentId, { label: label || null, summary: summary || null })
      setLabel(''); setSummary('')
      await refresh()
      setMessage('A new version snapshot was recorded.')
    } catch (requestError) {
      setError(requestError.message || 'Version could not be created.')
    }
  }

  const runDiff = async () => {
    setError('')
    try {
      setDiff(await researchApi.diffVersions(documentId, fromVersion, toVersion))
    } catch (requestError) {
      setError(requestError.message || 'Diff failed.')
    }
  }

  const restore = async (versionId) => {
    setError('')
    try {
      await researchApi.restoreVersion(documentId, versionId, { summary: 'Restored from collaboration page.' })
      setMessage('Version restored as the working manuscript.')
      await refresh()
    } catch (requestError) {
      setError(requestError.message || 'Restore failed.')
    }
  }

  return (
    <>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {message && <div className="status-box success-box" role="status">{message}</div>}
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">SNAPSHOT</p><h2>Record a version</h2></div></div>
        <div className="form-row stacked">
          <input type="text" className="text-input" placeholder="Label, e.g. After reviewer comments" value={label} onChange={(event) => setLabel(event.target.value)} />
          <input type="text" className="text-input" placeholder="Change summary" value={summary} onChange={(event) => setSummary(event.target.value)} />
          <div><button type="button" className="primary-button" onClick={create}><FileText size={15} /> Record version</button></div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">DIFF</p><h2>Compare versions</h2></div></div>
        {versions.length >= 2 ? (
          <div className="form-row">
            <select className="filter-select" value={fromVersion} onChange={(event) => setFromVersion(event.target.value)}>
              {versions.map((version) => <option key={version.version_id} value={version.version_id}>v{version.version_number} {version.label || ''}</option>)}
            </select>
            <span className="supporting-text">→</span>
            <select className="filter-select" value={toVersion} onChange={(event) => setToVersion(event.target.value)}>
              {versions.map((version) => <option key={version.version_id} value={version.version_id}>v{version.version_number} {version.label || ''}</option>)}
            </select>
            <button type="button" className="primary-button" onClick={runDiff}>Compare</button>
          </div>
        ) : <p className="supporting-text">Create at least two versions to compare.</p>}
        {diff && (
          <div className="comparison-grid">
            <div><label>Changed sections</label><p>{diff.changed_sections?.join(', ') || 'No section-level changes detected.'}</p></div>
            <div>
              <label>Changes</label>
              <ul className="mini-list">
                {(diff.changes || []).slice(0, 20).map((change, index) => <li key={`${index}-${change.type}`}>[{change.type}] {change.before || ''} → {change.after || ''}</li>)}
              </ul>
              {(diff.changes || []).length > 20 && <p className="supporting-text">Showing the first 20 of {diff.changes.length} changes.</p>}
            </div>
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">HISTORY</p><h2>Version list</h2></div></div>
        {versions.length === 0 ? (
          <p className="supporting-text">The initial version of the manuscript is recorded automatically.</p>
        ) : (
          <div className="data-table">
            {versions.map((version) => (
              <div className="data-row" key={version.version_id}>
                <span className="status-chip passed">v{version.version_number}</span>
                <span className="data-main">{version.label || 'Unlabeled version'}<small>{version.change_summary || 'No summary'} · by {version.author_name || 'unknown'} · {version.created_at}</small></span>
                <span className="data-meta">
                  <button type="button" className="text-button" onClick={() => restore(version.version_id)}>Restore</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

function ReviewsTab({ documentId }) {
  const [decisions, setDecisions] = useState([])
  const [decision, setDecision] = useState('revision_requested')
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const refresh = async () => {
    try {
      setDecisions((await researchApi.getReviews(documentId)).decisions || [])
    } catch (requestError) {
      setError(requestError.message || 'Could not load reviews.')
    }
  }
  useEffect(() => { refresh() }, [documentId])

  const submit = async () => {
    setError(''); setMessage('')
    try {
      await researchApi.submitReview(documentId, { decision, comment: comment || null })
      setComment('')
      await refresh()
      setMessage(`Review decision '${decision.replace('_', ' ')}' was recorded.`)
    } catch (requestError) {
      setError(requestError.message || 'Review could not be submitted.')
    }
  }

  return (
    <>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {message && <div className="status-box success-box" role="status">{message}</div>}
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">DECISION</p><h2>Submit a review decision</h2><span className="supporting-text">Decisions are recorded with the author; nothing is applied to the manuscript automatically.</span></div></div>
        <div className="form-row stacked">
          <select className="filter-select" value={decision} onChange={(event) => setDecision(event.target.value)}>
            <option value="approved">Approved</option>
            <option value="revision_requested">Revision requested</option>
            <option value="rejected">Rejected</option>
            <option value="comment">Comment only</option>
          </select>
          <textarea className="text-input" rows="3" placeholder="Review comments…" value={comment} onChange={(event) => setComment(event.target.value)} />
          <div><button type="button" className="primary-button" onClick={submit}><ShieldCheck size={15} /> Submit decision</button></div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><p className="kicker">DECISIONS</p><h2>Review history</h2></div></div>
        {decisions.length === 0 ? (
          <p className="supporting-text">No review decisions yet.</p>
        ) : (
          <div className="data-table">
            {decisions.map((item) => (
              <div className="data-row" key={item.id}>
                <span className={`status-chip ${item.decision === 'approved' ? 'passed' : item.decision === 'rejected' ? 'failed' : 'warning'}`}>{item.decision.replace('_', ' ')}</span>
                <span className="data-main">{item.reviewer_name || 'Reviewer'}<small>{item.comment || 'No comment'}</small></span>
                <span className="data-meta">{item.created_at}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

/* Shared small pieces so the file stays self-contained. */
function StatTile({ label, value, suffix = '', detail, icon: Icon, tone = 'neutral' }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={16} /></div>
      <p className="stat-value">{value}{suffix && <span> {suffix}</span>}</p>
      <p className="stat-label">{label}</p>
      {detail && <p className={`stat-detail ${tone}`}>{detail}</p>}
    </div>
  )
}
function GaugeIcon() { return <Sparkles size={16} /> }
function PlusIcon({ size }) { return <span style={{ fontSize: size }}>+</span> }
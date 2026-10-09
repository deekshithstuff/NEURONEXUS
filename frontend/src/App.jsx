import { useEffect, useMemo, useState } from 'react'
import {
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  FileText,
  FolderOpen,
  Gauge,
  Globe2,
  LogOut,
  Moon,
  MoreHorizontal,
  PanelLeft,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
  Sun,
  UploadCloud,
  X,
  Zap,
} from 'lucide-react'
import AuthScreen from './AuthScreen'
import { researchApi } from './services/api'

const navigation = [
  { label: 'Dashboard', icon: Gauge, id: 'dashboard' },
  { label: 'Upload', icon: UploadCloud, id: 'upload' },
  { label: 'Document Analysis', icon: FileText, id: 'analysis' },
  { label: 'Citations', icon: BookOpen, id: 'citations' },
  { label: 'Journal', icon: Globe2, id: 'journal' },
  { label: 'Quality', icon: BarChart3, id: 'quality' },
  { label: 'Novelty', icon: Sparkles, id: 'novelty' },
  { label: 'Methodology', icon: ClipboardCheck, id: 'methodology' },
  { label: 'Contribution', icon: BarChart3, id: 'contribution' },
  { label: 'Writing', icon: FileText, id: 'writing' },
  { label: 'Improvements', icon: Zap, id: 'improvements' },
  { label: 'Report', icon: ShieldCheck, id: 'report' },
  { label: 'Formatting', icon: FileText, id: 'formatting' },
  { label: 'Export', icon: FolderOpen, id: 'export' },
]

const defaultAnalysis = {
  document_id: '',
  title: '',
  authors: [],
  abstract: '',
  keywords: [],
  sections: [],
  figures: [],
  tables: [],
  equations: [],
  citations: [],
  references: [],
  metadata: {},
}

const citationIssueCategories = [
  'missing_references',
  'uncited_references',
  'duplicate_references',
  'duplicate_reference_numbers',
  'numbering_issues',
  'duplicate_citation_numbers',
  'malformed_references',
  'invalid_structure',
  'missing_dois',
  'invalid_dois',
  'author_year_mismatches',
  'references_wrong_order',
  'style_mismatches',
  'inconsistent_authors',
  'inconsistent_years',
  'inconsistent_title_formatting',
  'inconsistent_doi_formatting',
]

function ThemeToggle({ theme, setTheme }) {
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
      aria-label="Toggle theme"
      title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
    >
      {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
    </button>
  )
}

function ResearchWorkspace({ user, onSignOut }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('paperpilot-theme') || 'light')
  const [active, setActive] = useState('dashboard')
  const [showMobileMenu, setShowMobileMenu] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [selectedJournalId, setSelectedJournalId] = useState(() => localStorage.getItem('paperpilot-journal') || 'nature')
  const [journalList, setJournalList] = useState([])
  const [dashboardSummary, setDashboardSummary] = useState(null)
  const [aiStatus, setAiStatus] = useState({ status: 'limited_analysis', message: 'Checking analysis configuration.' })
  const [manuscripts, setManuscripts] = useState([])
  const [isLoadingManuscripts, setIsLoadingManuscripts] = useState(true)
  const [manuscriptError, setManuscriptError] = useState('')
  const [document, setDocument] = useState(defaultAnalysis)
  const [citationReport, setCitationReport] = useState({ total_citations: 0, total_references: 0 })
  const [qualityAnalysis, setQualityAnalysis] = useState({})
  const [noveltyAnalysis, setNoveltyAnalysis] = useState({})
  const [methodologyAnalysis, setMethodologyAnalysis] = useState({})
  const [contributionAnalysis, setContributionAnalysis] = useState({})
  const [completenessAnalysis, setCompletenessAnalysis] = useState({})
  const [writingAnalysis, setWritingAnalysis] = useState({})
  const [journalMatch, setJournalMatch] = useState({})
  const [improvements, setImprovements] = useState({ suggestions: [] })
  const [report, setReport] = useState({
    title: 'Pre-Submission Readiness Assessment',
    summary: 'Upload or open an analyzed manuscript to calculate readiness.',
    sections: [],
    final_checklist: [],
  })
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [statusMessage, setStatusMessage] = useState('Ready for upload')

  useEffect(() => {
    globalThis.document.documentElement.dataset.theme = theme
    localStorage.setItem('paperpilot-theme', theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem('paperpilot-journal', selectedJournalId)
  }, [selectedJournalId])

  const refreshManuscripts = async () => {
    setIsLoadingManuscripts(true)
    try {
      const [body, summary] = await Promise.all([
        researchApi.getDocuments(),
        researchApi.getDashboardSummary(),
      ])
      setManuscripts(body.documents || [])
      setDashboardSummary(summary)
      setManuscriptError('')
    } catch (error) {
      setManuscriptError(error.message || 'Could not load manuscripts.')
    } finally {
      setIsLoadingManuscripts(false)
    }
  }

  useEffect(() => {
    refreshManuscripts()
    researchApi.getJournals().then((body) => setJournalList(body.journals || [])).catch(() => setJournalList([]))
    researchApi.getAiStatus().then(setAiStatus).catch(() => setAiStatus({ status: 'limited_analysis', message: 'AI provider status unavailable; local analysis remains active.' }))
  }, [])

  const loadAnalysisModules = async (documentId, analysisPayload) => {
    const request = { document_id: documentId, analysis: analysisPayload, journal_id: selectedJournalId }
    const [quality, novelty, methodology, contribution, completeness, journal, writing, improvement] = await Promise.all([
      researchApi.analyze('quality', request),
      researchApi.analyze('novelty', request),
      researchApi.analyze('methodology', request),
      researchApi.analyze('contribution', request),
      researchApi.analyze('completeness', request),
      researchApi.matchJournal({ ...request, journal_id: selectedJournalId }),
      researchApi.analyze('writing', request),
      researchApi.generateImprovement({ ...request, focus: 'research quality' }),
    ])
    const reportDetails = await researchApi.generateReport({
      ...request,
      quality_analysis: quality,
      selected_journal: selectedJournalId,
    })
    setQualityAnalysis(quality)
    setNoveltyAnalysis(novelty)
    setMethodologyAnalysis(methodology)
    setContributionAnalysis(contribution)
    setCompletenessAnalysis(completeness)
    setWritingAnalysis(writing)
    setJournalMatch(journal)
    setImprovements(improvement)
    setReport(reportDetails)
  }

  const openManuscript = async (documentId) => {
    setManuscriptError('')
    try {
      const record = await researchApi.getDocument(documentId)
      const analysis = record.analysis || await researchApi.analyzeDocument(documentId, { journal_id: selectedJournalId })
      const analysisPayload = { ...defaultAnalysis, ...analysis, document_id: documentId, title: analysis.title || record.filename }
      setDocument(analysisPayload)
      const citationData = await researchApi.getCitations(documentId)
      setCitationReport(citationData)
      await loadAnalysisModules(documentId, analysisPayload)
      setActive('analysis')
    } catch (error) {
      setManuscriptError(error.message || 'Could not open this manuscript.')
      setActive('manuscripts')
    }
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!['docx', 'pdf'].includes(extension)) {
      setUploadError('Choose a DOCX or text-based PDF manuscript.')
      return
    }

    setUploadError('')
    setIsUploading(true)
    setStatusMessage('Uploading and analyzing manuscript...')

    try {
      const uploaded = await researchApi.uploadDocument(file)
      const articleId = uploaded.document_id
      const analyzed = await researchApi.analyzeDocument(articleId, { journal_id: selectedJournalId })
      const analysisPayload = { ...defaultAnalysis, ...analyzed, document_id: articleId }
      setDocument(analysisPayload)
      const citationData = await researchApi.getCitations(articleId)
      setCitationReport(citationData)
      await refreshManuscripts()
      setActive('analysis')
      setStatusMessage('Document uploaded, parsed, and analyzed successfully.')

      await loadAnalysisModules(articleId, analysisPayload)
      setActive('report')
    } catch (error) {
      setUploadError(error.message || 'The upload or analysis request failed.')
      setStatusMessage('Upload failed — please retry.')
    } finally {
      setIsUploading(false)
      event.target.value = ''
    }
  }

  const selectedJournal = useMemo(
    () => journalList.find((item) => item.journal_id === selectedJournalId) || journalList[0] || { journal_name: 'No journal selected', journal_id: '' },
    [journalList, selectedJournalId],
  )

  const currentTitle = navigation.find((item) => item.id === active)?.label
    || ({ manuscripts: 'All manuscripts', settings: 'Settings' }[active] || 'Dashboard')
  const userInitials = (user.name || user.email)
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('')

  return (
    <div className="app-shell">
      <aside id="sidebar-navigation" className={showMobileMenu ? 'sidebar mobile-open' : 'sidebar'}>
        <div className="brand">
          <div className="brand-mark">p</div>
          <div>
            <strong>PaperPilot</strong>
            <small>research readiness</small>
          </div>
        </div>

        <div className="workspace-switch">
          <div className="avatar">{userInitials}</div>
          <div>
            <span>{user.name}</span>
            <small>{user.email}</small>
          </div>
          <ChevronDown size={15} />
        </div>

        <p className="nav-label">WORKSPACE</p>
        <nav>
          {navigation.map(({ label, icon: Icon, id }) => (
            <button
              type="button"
              key={id}
              className={active === id ? 'nav-item active' : 'nav-item'}
              onClick={() => {
                setActive(id)
                setShowMobileMenu(false)
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            type="button"
            className={active === 'manuscripts' ? 'nav-item active' : 'nav-item'}
            onClick={() => {
              setActive('manuscripts')
              setShowMobileMenu(false)
            }}
          >
            <FolderOpen size={17} />
            <span>All manuscripts</span>
          </button>
          <button
            type="button"
            className={active === 'settings' ? 'nav-item active' : 'nav-item'}
            onClick={() => {
              setActive('settings')
              setShowMobileMenu(false)
            }}
          >
            <Settings2 size={17} />
            <span>Settings</span>
          </button>
          <div className="sidebar-footer">
            <div className="avatar small">AI</div>
            <div>
              <span>AI services</span>
              <small className="status-dot">{aiStatus.status === 'configured' ? `${aiStatus.provider} enabled` : 'Limited analysis'}</small>
            </div>
            <MoreHorizontal size={17} />
          </div>
        </div>
      </aside>
      {showMobileMenu && (
        <button
          type="button"
          className="mobile-menu-backdrop"
          aria-label="Close navigation"
          onClick={() => setShowMobileMenu(false)}
        />
      )}

      <main className="main-content">
        <header className="topbar">
          <button
            type="button"
            className="mobile-menu"
            aria-label={showMobileMenu ? 'Close menu' : 'Open menu'}
            aria-controls="sidebar-navigation"
            aria-expanded={showMobileMenu}
            onClick={() => setShowMobileMenu(!showMobileMenu)}
          >
            <PanelLeft size={18} />
          </button>
          <div className="breadcrumbs">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{currentTitle}</strong>
          </div>
          <div className="top-actions">
            <button type="button" className="icon-button" onClick={() => setShowHelp(!showHelp)} title="Help">
              <CircleHelp size={18} />
            </button>
            <ThemeToggle theme={theme} setTheme={setTheme} />
            <div className="top-avatar" title={user.email}>{userInitials}</div>
            <button type="button" className="signout-button" onClick={onSignOut} title="Sign out">
              <LogOut size={16} />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        {showHelp && (
          <div className="help-popover">
            <strong>Need a hand?</strong>
            <span>The system flags evidence gaps and improvement opportunities while keeping you in control.</span>
            <button type="button" onClick={() => setShowHelp(false)}><X size={14} /></button>
          </div>
        )}

        <div className="page-container">
          {active === 'dashboard' && (
            <Dashboard
              manuscripts={manuscripts}
              dashboardSummary={dashboardSummary}
              aiStatus={aiStatus}
              isLoadingManuscripts={isLoadingManuscripts}
              manuscriptError={manuscriptError}
              setActive={setActive}
              onOpenManuscript={openManuscript}
              onUpload={handleFileUpload}
              isUploading={isUploading}
              statusMessage={statusMessage}
              uploadError={uploadError}
            />
          )}

          {active === 'manuscripts' && (
            <ManuscriptsPage
              manuscripts={manuscripts}
              isLoading={isLoadingManuscripts}
              error={manuscriptError}
              onRefresh={refreshManuscripts}
              onOpen={openManuscript}
              onUpload={() => setActive('upload')}
            />
          )}
          {active === 'settings' && (
            <SettingsPage
              theme={theme}
              setTheme={setTheme}
              selectedJournalId={selectedJournalId}
              setSelectedJournalId={setSelectedJournalId}
              journalList={journalList}
            />
          )}

          {active === 'upload' && (
            <UploadPage onUpload={handleFileUpload} isUploading={isUploading} statusMessage={statusMessage} uploadError={uploadError} />
          )}

          {active === 'analysis' && <AnalysisPage document={document} setActive={setActive} citationReport={citationReport} />}
          {active === 'citations' && <CitationPage citationReport={citationReport} document={document} setActive={setActive} />}
          {active === 'journal' && (
            <JournalPage
              document={document}
              selectedJournalId={selectedJournalId}
              setSelectedJournalId={setSelectedJournalId}
              journalList={journalList}
              journalMatch={journalMatch}
              setJournalMatch={setJournalMatch}
              setActive={setActive}
            />
          )}
          {active === 'quality' && <QualityPage qualityAnalysis={qualityAnalysis} completenessAnalysis={completenessAnalysis} setActive={setActive} />}
          {active === 'novelty' && <NoveltyPage noveltyAnalysis={noveltyAnalysis} setActive={setActive} />}
          {active === 'methodology' && <MethodologyPage methodologyAnalysis={methodologyAnalysis} setActive={setActive} />}
          {active === 'contribution' && <ContributionPage contributionAnalysis={contributionAnalysis} setActive={setActive} />}
          {active === 'writing' && <WritingPage writingAnalysis={writingAnalysis} setActive={setActive} />}
          {active === 'improvements' && <ImprovementsPage improvements={improvements} setActive={setActive} />}
          {active === 'report' && <ReportPage report={report} setActive={setActive} />}
          {active === 'formatting' && <FormattingPage document={document} selectedJournalId={selectedJournalId} selectedJournal={selectedJournal} setActive={setActive} />}
          {active === 'export' && (
            <ExportPage
              document={document}
              selectedJournal={selectedJournal}
              selectedJournalId={selectedJournalId}
              setActive={setActive}
            />
          )}
        </div>
      </main>
    </div>
  )
}

function ManuscriptsPage({ manuscripts, isLoading, error, onRefresh, onOpen, onUpload }) {
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(25)
  const filteredManuscripts = manuscripts.filter((manuscript) => (
    `${manuscript.title} ${manuscript.filename} ${manuscript.document_id}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
  ))

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">YOUR LIBRARY</p>
          <h1>All manuscripts<span className="period">.</span></h1>
          <p className="subtitle">Browse uploaded manuscripts and open their analysis.</p>
        </div>
        <div className="button-row">
          <button type="button" className="outline-button" onClick={onRefresh} disabled={isLoading}>Refresh</button>
          <button type="button" className="primary-button" onClick={onUpload}>Upload manuscript <Plus size={16} /></button>
        </div>
      </section>
      <label className="manuscript-search">
        <span>Search manuscripts</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title, filename, or ID"
        />
      </label>
      <ManuscriptList
        manuscripts={filteredManuscripts.slice(0, visibleCount)}
        isLoading={isLoading}
        error={error}
        onOpen={onOpen}
        emptyMessage={search ? 'No manuscripts match your search.' : 'No manuscripts yet. Upload a DOCX to start your library.'}
      />
      {!isLoading && !error && filteredManuscripts.length > visibleCount && (
        <button type="button" className="outline-button load-more" onClick={() => setVisibleCount(visibleCount + 25)}>
          Show more ({filteredManuscripts.length - visibleCount} remaining)
        </button>
      )}
    </>
  )
}

function ManuscriptList({ manuscripts, isLoading, error, onOpen, emptyMessage = 'No manuscripts yet. Upload a DOCX to start your library.' }) {
  if (isLoading) return <div className="status-box">Loading manuscripts...</div>
  if (error) return <div className="status-box error-box" role="alert">{error}</div>
  if (manuscripts.length === 0) {
    return <div className="status-box">{emptyMessage}</div>
  }

  return (
    <div className="manuscript-list">
      {manuscripts.map((manuscript) => (
        <button
          type="button"
          className="manuscript-row"
          key={manuscript.document_id}
          onClick={() => onOpen(manuscript.document_id)}
        >
          <div className="doc-type"><FileText size={18} /></div>
          <div className="doc-name">
            <strong>{manuscript.title || manuscript.filename}</strong>
            <span>{manuscript.document_id} · {manuscript.filename}</span>
          </div>
          <span className={`status ${manuscript.status === 'analyzed' ? 'green' : 'blue'}`}>
            {manuscript.status}
          </span>
          <ChevronRight size={17} className="row-arrow" />
        </button>
      ))}
    </div>
  )
}

function SettingsPage({ theme, setTheme, selectedJournalId, setSelectedJournalId, journalList }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">PREFERENCES</p>
          <h1>Settings<span className="period">.</span></h1>
          <p className="subtitle">Choose how PaperPilot looks and which journal to use by default.</p>
        </div>
      </section>
      <section className="panel settings-panel">
        <div className="settings-field">
          <div>
            <strong>Appearance</strong>
            <span>Choose a light or dark color theme.</span>
          </div>
          <select aria-label="Appearance theme" value={theme} onChange={(event) => setTheme(event.target.value)}>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
        <div className="settings-field">
          <div>
            <strong>Default journal</strong>
            <span>Used when analyzing newly uploaded manuscripts.</span>
          </div>
          <select
            aria-label="Default journal"
            value={selectedJournalId}
            onChange={(event) => setSelectedJournalId(event.target.value)}
          >
            {journalList.length === 0 && <option value={selectedJournalId}>Nature</option>}
            {journalList.map((journal) => (
              <option key={journal.journal_id} value={journal.journal_id}>{journal.journal_name}</option>
            ))}
          </select>
        </div>
        <p className="settings-note">Your preferences are saved in this browser.</p>
      </section>
    </>
  )
}

function Dashboard({ manuscripts, dashboardSummary, aiStatus, isLoadingManuscripts, manuscriptError, setActive, onOpenManuscript, onUpload, isUploading, statusMessage, uploadError }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">WORKSPACE OVERVIEW</p>
          <h1>Research readiness dashboard<span className="period">.</span></h1>
          <p className="subtitle">Track manuscript status, AI quality checks, and publication readiness from one place.</p>
        </div>
        <label className="primary-button upload-trigger">
          <Plus size={17} />
          Upload manuscript
          <input type="file" accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={onUpload} />
        </label>
      </section>

      <section className="upload-banner">
        <div className="upload-icon"><UploadCloud size={23} /></div>
        <div>
          <strong>{statusMessage}</strong>
          <span>{uploadError || 'Upload a DOCX or text-based PDF and the system will structure the manuscript, check citations, and run the research quality evaluation.'}</span>
        </div>
        <label className="outline-button">
          {isUploading ? 'Processing...' : 'Upload DOCX / PDF'}
          <ArrowUpRight size={15} />
          <input type="file" accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={onUpload} />
        </label>
      </section>

      <section className="stats-grid">
        <Stat label="Manuscripts" value={dashboardSummary?.manuscript_count ?? '—'} detail="stored documents" icon={FileText} />
        <Stat label="Readiness" value={dashboardSummary?.readiness_average ?? '—'} suffix={dashboardSummary?.readiness_average == null ? '' : '/100'} detail={dashboardSummary?.analyzed_count ? `average across ${dashboardSummary.analyzed_count} analyzed` : 'No analyzed manuscripts'} icon={Gauge} green />
        <Stat label="Open suggestions" value={dashboardSummary?.open_suggestions ?? '—'} detail={`${dashboardSummary?.high_priority_suggestions ?? 0} critical or high priority`} icon={Sparkles} />
      </section>

      <section className="section-heading">
        <div>
          <p className="kicker">RECENT FILES</p>
          <h2>Recent manuscripts</h2>
        </div>
        <button type="button" className="text-button" onClick={() => setActive('manuscripts')}>View all <ArrowUpRight size={15} /></button>
      </section>

      <ManuscriptList
        manuscripts={manuscripts.slice(0, 5)}
        isLoading={isLoadingManuscripts}
        error={manuscriptError}
        onOpen={onOpenManuscript}
      />

      <section className="section-heading modules-heading">
        <div>
          <p className="kicker">INTELLIGENCE LAYERS</p>
          <h2>Review modules</h2>
        </div>
        <span className="muted-label">Select a module to explore</span>
      </section>

      <div className="module-grid">
        <ModuleCard title="Research quality" eyebrow="01 / Completeness" text="Core sections detected across analyzed manuscripts." value={dashboardSummary?.dimension_averages?.research_completeness ?? '—'} unit="/100" tone="lavender" icon={BarChart3} onClick={() => setActive('quality')} />
        <ModuleCard title="Novelty framing" eyebrow="02 / Internal analysis" text="Measures clarity of novelty claims; no external similarity search is configured." value={dashboardSummary?.dimension_averages?.novelty_framing ?? '—'} unit="/100" tone="mint" icon={Sparkles} onClick={() => setActive('novelty')} />
        <ModuleCard title="Methodology" eyebrow="03 / Reproducibility" text="Dataset, setup, metrics, baselines, and reproducibility evidence." value={dashboardSummary?.dimension_averages?.methodology ?? '—'} unit="/100" tone="peach" icon={ClipboardCheck} onClick={() => setActive('methodology')} />
      </div>
      <p className="muted-label">AI status: {aiStatus.message}</p>
    </>
  )
}

function UploadPage({ onUpload, isUploading, statusMessage, uploadError }) {
  return (
    <section className="panel upload-panel">
      <p className="kicker">UPLOAD</p>
      <h1>Upload manuscript</h1>
      <p className="subtitle">DOCX and text-based PDF are supported. Scanned PDFs require OCR, which is not enabled.</p>
      <label className="dropzone">
        <UploadCloud size={32} />
        <span>Drag & drop your manuscript here</span>
        <strong>or click to browse</strong>
        <input type="file" accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={onUpload} />
      </label>
      <div className="status-box">
        <strong>{isUploading ? 'Processing...' : 'Status'}</strong>
        <p>{uploadError || statusMessage}</p>
      </div>
    </section>
  )
}

function AnalysisPage({ document, setActive, citationReport }) {
  const counts = {
    sections: document.sections?.length || 0,
    figures: document.figures?.length || 0,
    tables: document.tables?.length || 0,
    equations: document.equations?.length || 0,
    citations: document.citations?.length || 0,
    references: document.references?.length || 0,
  }

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">DOCUMENT INTELLIGENCE</p>
          <h1>Document analysis<span className="period">.</span></h1>
          <p className="subtitle">Detected manuscript structure, metadata, and publication-ready signals.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('citations')}>Check citations <ArrowUpRight size={16} /></button>
      </section>

      <section className="analysis-hero">
        <div className="analysis-score">
          <span className="score-ring">92%</span>
          <div>
            <span className="eyebrow">{document.document_id}</span>
            <h2>{document.title}</h2>
            <p>{document.abstract || 'The manuscript abstract is available after upload and analysis.'}</p>
          </div>
        </div>
        <div className="analysis-meta">
          <div><span>Authors</span><strong>{(document.authors || []).join(', ') || 'Not detected'}</strong></div>
          <div><span>Keywords</span><strong>{(document.keywords || []).join(', ') || 'Not detected'}</strong></div>
          <div><span>Citation report</span><strong>{citationReport.total_citations} citations / {citationReport.total_references} references</strong></div>
        </div>
      </section>

      <section className="stats-grid compact-grid">
        <Stat label="Sections" value={counts.sections} detail="manuscript headings" icon={FileText} />
        <Stat label="Figures" value={counts.figures} detail="visual elements" icon={BarChart3} />
        <Stat label="Tables" value={counts.tables} detail="data panels" icon={BookOpen} />
        <Stat label="Equations" value={counts.equations} detail="math objects" icon={Gauge} />
        <Stat label="Citations" value={counts.citations} detail="in-text references" icon={Sparkles} />
        <Stat label="References" value={counts.references} detail="bibliography entries" icon={ShieldCheck} />
      </section>

      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="kicker">SECTION MAP</p>
              <h2>Detected structure</h2>
            </div>
          </div>
          <div className="finding-list">
            {(document.sections || []).map((section) => (
              <div className="finding" key={`${section.heading}-${section.type}`}>
                <span className="finding-mark good"><Check size={14} /></span>
                <div>
                  <strong>{section.heading}</strong>
                  <span>{section.type}</span>
                </div>
                <ChevronRight size={16} />
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="kicker">KEY METADATA</p>
              <h2>Document snapshot</h2>
            </div>
          </div>
          <div className="info-list">
            <p><strong>Title:</strong> {document.title}</p>
            <p><strong>Authors:</strong> {(document.authors || []).join(', ') || 'Not detected'}</p>
            <p><strong>Abstract:</strong> {document.abstract || 'No abstract detected.'}</p>
            <p><strong>Keywords:</strong> {(document.keywords || []).join(', ') || 'No keywords detected.'}</p>
          </div>
        </section>
      </div>
    </>
  )
}

function CitationPage({ citationReport, document, setActive }) {
  if (!document?.document_id) return <AnalysisRequired setActive={setActive} />
  const allIssues = citationIssueCategories.flatMap((key) => (
    (citationReport[key] || []).map((issue, index) => ({ key, issue, index }))
  ))
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">REFERENCE INTEGRITY</p>
          <h1>Citation check<span className="period">.</span></h1>
          <p className="subtitle">Inspect unresolved, duplicated, or uncited references before submission.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('journal')}>Match journal <ArrowUpRight size={16} /></button>
      </section>

      <section className="stats-grid compact-grid">
        <Stat label="Total citations" value={citationReport.total_citations || 0} detail="in-text references" icon={BookOpen} />
        <Stat label="Total references" value={citationReport.total_references || 0} detail="bibliography entries" icon={FileText} />
        <Stat label="Missing refs" value={citationReport.missing_references?.length || 0} detail="needs review" icon={ShieldCheck} />
        <Stat label="Uncited refs" value={citationReport.uncited_references?.length || 0} detail="unused entries" icon={Sparkles} />
      </section>

      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading">
            <div><p className="kicker">ISSUES</p><h2>Reference problems</h2></div>
          </div>
          <div className="finding-list">
            {allIssues.length === 0 ? (
              <div className="finding"><span className="finding-mark good"><Check size={14} /></span><div><strong>No major citation issues detected</strong><span>Reference integrity looks consistent in the current draft.</span></div></div>
            ) : (
              allIssues.map(({ key, issue, index }) => (
                <div className="finding" key={`${key}-${index}`}>
                  <span className="finding-mark warning">!</span>
                  <div>
                    <strong>{issue.citation || issue.type?.replaceAll('_', ' ') || key.replaceAll('_', ' ')}</strong>
                    <span>{issue.message} {issue.suggestion}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div><p className="kicker">BIBLIOGRAPHY</p><h2>Detected references</h2></div>
          </div>
          <div className="finding-list">
            {(document.references || []).length === 0 ? (
              <div className="finding"><span className="finding-mark neutral">•</span><div><strong>No references detected</strong><span>Upload and analyze a manuscript to populate this list.</span></div></div>
            ) : (
              (document.references || []).slice(0, 8).map((ref) => (
                <div className="finding" key={ref.id || ref.raw_text}>
                  <span className="finding-mark good"><Check size={14} /></span>
                  <div><strong>[{ref.id}]</strong><span>{ref.raw_text}</span></div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </>
  )
}

function JournalPage({ document, selectedJournalId, setSelectedJournalId, journalList, journalMatch, setJournalMatch, setActive }) {
  const [matchError, setMatchError] = useState('')
  const handleSelect = async (event) => {
    const nextJournal = event.target.value
    setSelectedJournalId(nextJournal)
    if (!document?.document_id) {
      setJournalMatch({})
      return
    }
    try {
      const match = await researchApi.matchJournal({
        document_id: document.document_id,
        analysis: document,
        journal_id: nextJournal,
      })
      setJournalMatch(match)
      setMatchError('')
    } catch (error) {
      setMatchError(error.message || 'Journal matching could not be completed.')
    }
  }

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">SCOPE SUITABILITY</p>
          <h1>Journal fit analysis<span className="period">.</span></h1>
          <p className="subtitle">Assess manuscript topic alignment against the selected profile's configured scope.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('quality')}>Review quality <ArrowUpRight size={16} /></button>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="kicker">JOURNAL MATCH</p><h2>Selected journal</h2></div>
        </div>
        <div className="journal-select-row">
          <select value={selectedJournalId} onChange={handleSelect}>
            {journalList.map((journal) => (
              <option key={journal.journal_id} value={journal.journal_id}>{journal.journal_name}</option>
            ))}
          </select>
          <div className="score-badge">{journalMatch.score == null ? 'Not evaluated' : `${Math.round(journalMatch.score * 100)}% match`}</div>
        </div>
        {matchError && <div className="status-box error-box" role="alert">{matchError}</div>}
        <div className="finding-list">
          <div className="finding">
            <span className="finding-mark good"><Check size={14} /></span>
            <div><strong>Relevant topics</strong><span>{(journalMatch.relevant_topics || []).join(', ') || 'Run a match after opening a manuscript.'}</span></div>
          </div>
          <div className="finding">
            <span className="finding-mark warning">!</span>
            <div><strong>Scope gaps</strong><span>{(journalMatch.scope_gaps || []).join(' ') || (journalMatch.score == null ? 'Not evaluated.' : 'No scope gaps were detected by the configured term matcher.')}</span></div>
          </div>
          <div className="finding">
            <span className="finding-mark neutral">•</span>
            <div><strong>Explanation</strong><span>{journalMatch.explanation || 'Open an analyzed manuscript to calculate topic alignment.'}</span></div>
          </div>
        </div>
      </section>
    </>
  )
}

function AnalysisRequired({ setActive }) {
  return (
    <section className="status-box">
      <strong>No manuscript analysis loaded.</strong>
      <p>Upload a DOCX or open a saved manuscript to view evidence-based results.</p>
      <button type="button" className="outline-button" onClick={() => setActive('upload')}>Upload manuscript</button>
    </section>
  )
}

function QualityPage({ qualityAnalysis, completenessAnalysis, setActive }) {
  if (!qualityAnalysis?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">RESEARCH INTELLIGENCE</p>
          <h1>Research quality analysis<span className="period">.</span></h1>
          <p className="subtitle">A structured assessment of completeness, evidence, writing quality, and risk.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('novelty')}>Explore novelty <ArrowUpRight size={16} /></button>
      </section>
      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">QUALITY</p><h2>Findings</h2></div></div>
          <div className="finding-list">
            <div className="finding"><span className="finding-mark good"><Check size={14} /></span><div><strong>Research gap</strong><span>{qualityAnalysis.research_gap}</span></div></div>
            <div className="finding"><span className="finding-mark good"><Check size={14} /></span><div><strong>Technical contribution</strong><span>{qualityAnalysis.technical_contribution}</span></div></div>
            <div className="finding"><span className="finding-mark warning">!</span><div><strong>Methodology issues</strong><span>{(qualityAnalysis.methodology_issues || []).join(' ')}</span></div></div>
            <div className="finding"><span className="finding-mark neutral">•</span><div><strong>Missing sections</strong><span>{(qualityAnalysis.missing_sections || []).join(', ') || 'None detected'}</span></div></div>
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">ACTIONS</p><h2>Suggestions</h2></div></div>
          <ul className="mini-list">
            {(qualityAnalysis.suggestions || []).map((suggestion) => <li key={suggestion}>{suggestion}</li>)}
          </ul>
        </section>
        {completenessAnalysis?.document_id && (
          <section className="panel">
            <div className="panel-heading"><div><p className="kicker">SELECTED JOURNAL PROFILE</p><h2>Research completeness</h2></div><span className="score-badge">{completenessAnalysis.score}/100</span></div>
            <p className="supporting-text">{completenessAnalysis.analysis_scope}</p>
            <div className="finding-list">
              <div className="finding">
                <span className={`finding-mark ${completenessAnalysis.word_limit_exceeded ? 'warning' : 'good'}`}>
                  {completenessAnalysis.word_limit_exceeded ? '!' : <Check size={14} />}
                </span>
                <div>
                  <strong>Manuscript length</strong>
                  <span>
                    {completenessAnalysis.word_limit
                      ? `${completenessAnalysis.word_count} / ${completenessAnalysis.word_limit} words`
                      : `${completenessAnalysis.word_count} words; no profile limit configured`}
                  </span>
                </div>
              </div>
              {completenessAnalysis.abstract_word_limit && (
                <div className="finding">
                  <span className={`finding-mark ${completenessAnalysis.abstract_limit_exceeded ? 'warning' : 'good'}`}>
                    {completenessAnalysis.abstract_limit_exceeded ? '!' : <Check size={14} />}
                  </span>
                  <div>
                    <strong>Abstract length</strong>
                    <span>{completenessAnalysis.abstract_word_count} / {completenessAnalysis.abstract_word_limit} words</span>
                  </div>
                </div>
              )}
              {completenessAnalysis.page_limit && (
                <div className="finding">
                  <span className="finding-mark neutral">•</span>
                  <div><strong>Page limit</strong><span>Configured limit: {completenessAnalysis.page_limit} pages; page count is not assessed from the parsed DOCX.</span></div>
                </div>
              )}
              {(completenessAnalysis.missing_required || []).map((section) => (
                <div className="finding" key={`required-${section}`}>
                  <span className="finding-mark warning">!</span>
                  <div><strong>Missing required section</strong><span>{section.replaceAll('_', ' ')}</span></div>
                </div>
              ))}
              {(completenessAnalysis.missing_figure_captions || []).map((figure) => (
                <div className="finding" key={`figure-${figure}`}>
                  <span className="finding-mark warning">!</span>
                  <div><strong>Missing figure caption</strong><span>{figure}</span></div>
                </div>
              ))}
              {(completenessAnalysis.missing_table_captions || []).map((table) => (
                <div className="finding" key={`table-${table}`}>
                  <span className="finding-mark warning">!</span>
                  <div><strong>Missing table caption</strong><span>{table}</span></div>
                </div>
              ))}
              {(completenessAnalysis.unnumbered_equations || []).map((equation) => (
                <div className="finding" key={`equation-${equation}`}>
                  <span className="finding-mark warning">!</span>
                  <div><strong>Equation numbering needs review</strong><span>{equation}</span></div>
                </div>
              ))}
              {!(completenessAnalysis.missing_required || []).length
                && !(completenessAnalysis.missing_figure_captions || []).length
                && !(completenessAnalysis.missing_table_captions || []).length
                && !(completenessAnalysis.unnumbered_equations || []).length
                && !completenessAnalysis.word_limit_exceeded
                && !completenessAnalysis.abstract_limit_exceeded
                && <div className="finding"><span className="finding-mark good"><Check size={14} /></span><div><strong>No configured completeness gaps detected</strong><span>Optional sections are not treated as required.</span></div></div>}
            </div>
          </section>
        )}
      </div>
    </>
  )
}

function NoveltyPage({ noveltyAnalysis, setActive }) {
  if (!noveltyAnalysis?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">INTERNAL CLAIM ANALYSIS</p>
          <h1>Novelty analysis<span className="period">.</span></h1>
          <p className="subtitle">Novelty score: {noveltyAnalysis.novelty_score}/100. External scholarly search is not configured; this is not a plagiarism or global originality check.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('methodology')}>Review methodology <ArrowUpRight size={16} /></button>
      </section>
      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">ORIGINALITY STATUS</p><h2>External comparison</h2></div></div>
          <p className="supporting-text">{noveltyAnalysis.analysis_scope}</p>
          <p className="supporting-text">Originality score: {noveltyAnalysis.originality_score ?? 'Not configured'}</p>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">RECOMMENDATION</p><h2>What to improve</h2></div></div>
          <p className="supporting-text">{noveltyAnalysis.explanation}</p>
          <ul className="mini-list">
            {(noveltyAnalysis.improvement_suggestions || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>
    </>
  )
}

function MethodologyPage({ methodologyAnalysis, setActive }) {
  if (!methodologyAnalysis?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">REPRODUCIBILITY</p>
          <h1>Methodology review<span className="period">.</span></h1>
          <p className="subtitle">Assess whether the manuscript provides enough technical detail to be trusted and repeated.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('improvements')}>See improvements <ArrowUpRight size={16} /></button>
      </section>
      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">DETECTED</p><h2>Method details present</h2></div></div>
          <ul className="mini-list">
            {(methodologyAnalysis.detected_information || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">GAPS</p><h2>Missing / weak</h2></div></div>
          <p className="supporting-text">{methodologyAnalysis.potential_weakness}</p>
          <ul className="mini-list">
            {(methodologyAnalysis.missing_information || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
          <p className="supporting-text"><strong>Action:</strong> {methodologyAnalysis.actionable_suggestion}</p>
        </section>
      </div>
    </>
  )
}

function ContributionPage({ contributionAnalysis, setActive }) {
  if (!contributionAnalysis?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">TECHNICAL EVIDENCE</p>
          <h1>Contribution analysis<span className="period">.</span></h1>
          <p className="subtitle">Evidence-presence assessment, not a determination of scientific importance.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('methodology')}>Review methodology <ArrowUpRight size={16} /></button>
      </section>
      <section className="analysis-hero">
        <div className="analysis-score">
          <div className="score-ring">{contributionAnalysis.technical_contribution_score}<small>/100</small></div>
          <div><p className="kicker">TECHNICAL CONTRIBUTION SCORE</p><p>{contributionAnalysis.analysis_scope}</p></div>
        </div>
      </section>
      <div className="detail-grid two-col">
        <section className="panel"><h2>Evidence detected</h2><ul className="mini-list">{(contributionAnalysis.strengths || []).map((item) => <li key={item}>{item}</li>)}</ul></section>
        <section className="panel"><h2>Missing evidence</h2><ul className="mini-list">{(contributionAnalysis.recommendations || []).map((item) => <li key={item}>{item}</li>)}</ul></section>
      </div>
    </>
  )
}

function WritingPage({ writingAnalysis, setActive }) {
  if (!writingAnalysis?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">ACADEMIC WRITING</p>
          <h1>Writing quality<span className="period">.</span></h1>
          <p className="subtitle">Rule-based checks only. Grammar and spelling proofing are not configured.</p>
        </div>
      </section>
      <section className="stats-grid compact-grid">
        <Stat label="Writing signals" value={writingAnalysis.score ?? '—'} suffix="/100" detail="heuristic indicators" icon={FileText} />
        <Stat label="Flagged sentences" value={writingAnalysis.sentence_findings?.length ?? 0} detail="review individually" icon={Sparkles} />
        <Stat label="Other issues" value={writingAnalysis.issues?.length ?? 0} detail="rule-based checks" icon={ClipboardCheck} />
      </section>
      {(writingAnalysis.sentence_findings || []).length === 0 ? (
        <div className="status-box">No sentence-level issues were detected by the configured checks. This is not a grammar or spelling verification.</div>
      ) : (
        <div className="improvement-list">
          {writingAnalysis.sentence_findings.map((finding, index) => (
            <section className="panel improvement-card" key={`${finding.original}-${index}`}>
              <div className="comparison-grid">
                <div><label>Original sentence</label><p>{finding.original}</p></div>
                <div><label>Suggested improvement</label><p>{finding.suggested_improvement}</p></div>
              </div>
              <div className="finding-list">
                <div className="finding"><div><strong>Problem</strong><span>{finding.problem}</span></div></div>
                <div className="finding"><div><strong>Reason</strong><span>{finding.reason}</span></div></div>
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  )
}

function FormattingPage({ document, selectedJournalId, selectedJournal, setActive }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [isChecking, setIsChecking] = useState(false)

  const checkFormatting = async () => {
    if (!document?.document_id) return
    setError('')
    setIsChecking(true)
    try {
      setResult(await researchApi.formatDocument(document.document_id, { journal_id: selectedJournalId }))
    } catch (requestError) {
      setError(requestError.message || 'Formatting check failed.')
    } finally {
      setIsChecking(false)
    }
  }

  if (!document?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">JOURNAL RULE CHECK</p>
          <h1>Formatting review<span className="period">.</span></h1>
          <p className="subtitle">{selectedJournal?.journal_name || 'Selected profile'} · {selectedJournal?.profile_basis || 'Generic profile; verify publisher instructions.'}</p>
        </div>
        <button type="button" className="primary-button" onClick={checkFormatting} disabled={isChecking}>{isChecking ? 'Checking...' : 'Check formatting rules'}</button>
      </section>
      {error && <div className="status-box error-box" role="alert">{error}</div>}
      {result && (
        <div className="detail-grid two-col">
          <section className="panel"><h2>Applied rule values</h2><pre className="rules-output">{JSON.stringify(result.applied_rules, null, 2)}</pre></section>
          <section className="panel"><h2>Warnings</h2>{result.warnings?.length ? <ul className="mini-list">{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : <p className="supporting-text">No formatter warnings were reported.</p>}</section>
        </div>
      )}
      {!result && !error && <div className="status-box">Run the profile check to see the rules currently recognized by the formatter.</div>}
    </>
  )
}

function ImprovementsPage({ improvements, setActive }) {
  if (!improvements?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">RESEARCHER CONTROL</p>
          <h1>AI improvement suggestions<span className="period">.</span></h1>
          <p className="subtitle">Suggestions are advisory and do not modify the uploaded manuscript.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('report')}>Open readiness report <ArrowUpRight size={16} /></button>
      </section>
      <div className="improvement-list">
        {(improvements.suggestions || []).map((item) => (
          <div key={item.id} className="panel improvement-card">
            <div className="improvement-header">
              <span>{item.section}</span>
            </div>
            <div className="comparison-grid">
              <div>
                <label>Original</label>
                <p>{item.original}</p>
              </div>
              <div>
                <label>Suggested improvement</label>
                <p>{item.suggested}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function ReportPage({ report, setActive }) {
  if (!report?.document_id) return <AnalysisRequired setActive={setActive} />
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">PRE-SUBMISSION ASSESSMENT</p>
          <h1>{report.title}<span className="period">.</span></h1>
          <p className="subtitle">Overall readiness: {report.overall_readiness}/100. {report.summary}</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('export')}>Generate final manuscript <ArrowUpRight size={16} /></button>
      </section>
      <div className="detail-grid">
        <section className="panel report-panel">
          <div className="panel-heading"><div><p className="kicker">REPORT</p><h2>Assessment sections</h2></div></div>
          <div className="finding-list">
            {(report.sections || []).map((section) => (
              <div className="finding" key={section.name}>
                <span className="finding-mark good"><Check size={14} /></span>
                <div><strong>{section.name}</strong><span>{section.details}</span></div>
              </div>
            ))}
          </div>
        </section>
        <section className="panel report-panel">
          <div className="panel-heading"><div><p className="kicker">CHECKLIST</p><h2>Final checklist</h2></div></div>
          <ul className="mini-list">
            {(report.final_checklist || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>
    </>
  )
}

function ExportPage({ document, selectedJournal, selectedJournalId, setActive }) {
  const [exportStatus, setExportStatus] = useState('idle')
  const [exportMessage, setExportMessage] = useState('Format and generate the journal-aligned submission package.')
  const [exportError, setExportError] = useState('')
  const [exportWarnings, setExportWarnings] = useState([])

  const runExport = async () => {
    if (!document?.document_id) {
      setExportError('Upload and analyze a manuscript before exporting.')
      return
    }
    setExportError('')
    setExportStatus('working')
    setExportMessage('Applying journal template and building submission package...')
    try {
      await researchApi.formatDocument(document.document_id, { journal_id: selectedJournalId })
      const generated = await researchApi.generateDocument(document.document_id, { journal_id: selectedJournalId })
      setExportWarnings(generated.formatting_warnings || [])
      setExportStatus('ready')
      setExportMessage(`Submission package is ready. ${generated.pdf_rendering?.message || ''}`)
    } catch (error) {
      setExportStatus('error')
      setExportError(error.message || 'Export failed.')
      setExportMessage('Export could not be completed.')
    }
  }

  const downloadFile = async (format) => {
    try {
      const names = {
        pdf: 'final_manuscript.pdf',
        report: 'readiness_report.pdf',
        zip: 'submission_package.zip',
        docx: 'final_manuscript.docx',
      }
      const fileName = names[format] || `manuscript.${format}`
      const blob = await researchApi.download(document.document_id, format)
      const url = URL.createObjectURL(blob)
      const link = globalThis.document.createElement('a')
      link.href = url
      link.download = fileName
      link.rel = 'noopener'
      link.style.display = 'none'
      globalThis.document.body.appendChild(link)
      link.click()
      setTimeout(() => {
        link.remove()
        URL.revokeObjectURL(url)
      }, 1500)
    } catch (error) {
      setExportError(error.message || `Could not download ${format.toUpperCase()}.`)
    }
  }

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">FINAL MANUSCRIPT</p>
          <h1>Generate & export<span className="period">.</span></h1>
          <p className="subtitle">Create a journal-aligned manuscript package and download the final outputs.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('dashboard')}>Back to overview <ArrowUpRight size={16} /></button>
      </section>
      <section className="panel export-panel">
        <div className="panel-heading"><div><p className="kicker">OUTPUT</p><h2>Publication package</h2></div></div>
        <div className={exportStatus === 'ready' ? 'status-box success-box' : 'status-box'}>
          <strong>{exportStatus === 'working' ? 'Generating...' : exportStatus === 'ready' ? 'Ready for export' : 'Generate outputs'}</strong>
          <p>{exportError || exportMessage}</p>
          <p>Manuscript: {document.title || 'Untitled'} · Journal: {selectedJournal?.journal_name || 'Not selected'}</p>
        </div>
        {exportWarnings.length > 0 && (
          <div className="status-box" role="status">
            <strong>Formatting warnings</strong>
            <ul className="mini-list">{exportWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          </div>
        )}
        <div className="button-row export-buttons">
          <button type="button" className="primary-button" onClick={runExport} disabled={exportStatus === 'working'}>
            {exportStatus === 'ready' ? 'Regenerate package' : 'Generate submission package'}
          </button>
          <button type="button" className="outline-button" onClick={() => downloadFile('docx')} disabled={exportStatus !== 'ready'}>Download DOCX</button>
          <button type="button" className="outline-button" onClick={() => downloadFile('pdf')} disabled={exportStatus !== 'ready'}>Download PDF</button>
          <button type="button" className="outline-button" onClick={() => downloadFile('report')} disabled={exportStatus !== 'ready'}>Readiness report</button>
          <button type="button" className="outline-button" onClick={() => downloadFile('zip')} disabled={exportStatus !== 'ready'}>Submission ZIP</button>
        </div>
      </section>
    </>
  )
}

function ModuleCard({ title, eyebrow, text, value, unit, tone, icon: Icon, onClick }) {
  return (
    <button type="button" className={`module-card ${tone}`} onClick={onClick}>
      <div className="module-top">
        <span className="module-icon"><Icon size={18} /></span>
        <ArrowUpRight size={16} />
      </div>
      <p className="eyebrow">{eyebrow}</p>
      <h3>{title}</h3>
      <p>{text}</p>
      <div className="module-value"><strong>{value}</strong><span>{unit}</span></div>
    </button>
  )
}

function Stat({ label, value, suffix = '', detail, icon: Icon, green = false }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={17} /></div>
      <div>
        <span className="stat-label">{label}</span>
        <div className="stat-number">{value}<small>{suffix}</small></div>
        <span className={green ? 'stat-detail green-text' : 'stat-detail'}>{detail}</span>
      </div>
    </div>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [authNotice, setAuthNotice] = useState('')

  useEffect(() => {
    if (!researchApi.hasStoredAuth()) {
      setIsCheckingSession(false)
      return undefined
    }
    researchApi.getCurrentUser()
      .then(setUser)
      .catch(() => {
        researchApi.clearAuth()
        setUser(null)
      })
      .finally(() => setIsCheckingSession(false))
    return undefined
  }, [])

  const signOut = async () => {
    let notice = ''
    try {
      await researchApi.signOut()
    } catch (error) {
      notice = `Signed out on this device, but server session revocation failed: ${error.message}`
    } finally {
      researchApi.clearAuth()
      setUser(null)
      setAuthNotice(notice)
    }
  }

  if (isCheckingSession) {
    return <main className="auth-loading" role="status">Checking your session…</main>
  }
  if (!user) {
    return <AuthScreen onAuthenticated={setUser} notice={authNotice} />
  }
  return <ResearchWorkspace user={user} onSignOut={signOut} />
}

export default App

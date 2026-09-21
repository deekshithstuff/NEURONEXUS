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
  Moon,
  MoreHorizontal,
  PanelLeft,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Sun,
  UploadCloud,
  X,
  Zap,
} from 'lucide-react'
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
  { label: 'Improvements', icon: Zap, id: 'improvements' },
  { label: 'Report', icon: ShieldCheck, id: 'report' },
  { label: 'Export', icon: FolderOpen, id: 'export' },
]

const defaultAnalysis = {
  document_id: 'DOC-001',
  title: 'Federated learning for clinical imaging',
  authors: ['A. Lee', 'B. Patel'],
  abstract: 'This study evaluates a federated clinical imaging model for decision support with limited labeled data.',
  keywords: ['federated learning', 'medical imaging', 'clinical AI'],
  sections: [
    { heading: 'Abstract', type: 'abstract' },
    { heading: 'Introduction', type: 'introduction' },
    { heading: 'Methodology', type: 'methodology' },
    { heading: 'Results', type: 'results' },
    { heading: 'References', type: 'references' },
  ],
  figures: [{ id: 'Figure 1', caption: 'Model overview' }],
  tables: [{ id: 'Table 1', content: [['Metric', 'Value']] }],
  equations: [{ id: 'Equation 1' }],
  citations: [{ text: '[1]', citation_type: 'numeric', reference_ids: ['1'] }],
  references: [{ id: '1', raw_text: 'Smith J. et al. Clinical imaging. Nature. 2024.' }],
  metadata: {},
}

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

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('paperpilot-theme') || 'light')
  const [active, setActive] = useState('dashboard')
  const [showHelp, setShowHelp] = useState(false)
  const [selectedJournalId, setSelectedJournalId] = useState('nature')
  const [journalList, setJournalList] = useState([])
  const [document, setDocument] = useState(defaultAnalysis)
  const [citationReport, setCitationReport] = useState({
    total_citations: 1,
    total_references: 1,
    missing_references: [],
    uncited_references: [],
    duplicate_references: [],
    numbering_issues: [],
  })
  const [qualityAnalysis, setQualityAnalysis] = useState({
    research_gap: 'The manuscript motivates a clinical-AI problem and outlines a deep-learning approach, but the gap statement should be more explicit.',
    technical_contribution: 'The work centers on a domain-specific model with evidence of predictive performance.',
    methodology_issues: ['Dataset provenance and baseline support should be clearer.'],
    missing_sections: ['related_work'],
    writing_issues: ['Clarify the contribution statement.'],
    suggestions: ['Strengthen the gap statement and methodology details.'],
  })
  const [noveltyAnalysis, setNoveltyAnalysis] = useState({
    similar_papers: [{ title: 'Clinical imaging with deep CNNs for decision support', similarity: 0.82, overlap: ['clinical imaging'] }],
    comparative_summary: 'The manuscript overlaps with recent clinical-AI methods; a stronger differentiation narrative is recommended.',
    potential_differentiators: ['Dataset specificity', 'Application constraints'],
  })
  const [methodologyAnalysis, setMethodologyAnalysis] = useState({
    detected_information: ['dataset', 'baseline', 'evaluation'],
    missing_information: ['dataset size', 'experimental setup'],
    potential_weakness: 'The methodology section would benefit from more reproducibility detail.',
    actionable_suggestion: 'Add dataset size, splits, baseline models, and hyperparameters.',
  })
  const [contributionAnalysis, setContributionAnalysis] = useState({
    problem: 'The manuscript addresses clinical decision support and model adaptation under limited labels.',
    research_gap: 'The work closes a gap in generalizable pipeline design for clinical imaging.',
    contribution: 'The manuscript proposes a practical ML method with domain-specific evaluation.',
  })
  const [journalMatch, setJournalMatch] = useState({
    journal_id: 'nature',
    score: 0.82,
    relevant_topics: ['medical imaging', 'clinical AI'],
    scope_gaps: ['Needs stronger statement of novelty within the journal scope.'],
    explanation: 'Strong alignment with applied AI and clinical methods, but novelty framing should be clearer.',
  })
  const [improvements, setImprovements] = useState({
    suggestions: [
      {
        id: 'improvement-1',
        original: 'Existing work relies on handcrafted features.',
        suggested: 'Existing clinical AI pipelines often depend on handcrafted features and limited benchmark coverage, leaving a clear need for a more scalable and generalizable approach.',
      },
    ],
  })
  const [report, setReport] = useState({
    title: 'Pre-Submission Readiness Assessment',
    summary: 'A transparent assessment of readiness without implying guaranteed publication.',
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
    researchApi.getJournals().then((body) => setJournalList(body.journals || [])).catch(() => setJournalList([]))
  }, [])

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setUploadError('Only DOCX files are supported.')
      return
    }

    setUploadError('')
    setIsUploading(true)
    setStatusMessage('Uploading and analyzing manuscript...')

    try {
      const uploaded = await researchApi.uploadDocument(file)
      const articleId = uploaded.document_id
      const analyzed = await researchApi.analyzeDocument(articleId, { journal_id: selectedJournalId })
      const structure = await researchApi.getStructure(articleId)
      setDocument({ ...defaultAnalysis, ...structure, document_id: articleId, title: structure.title || defaultAnalysis.title })
      const citationData = await researchApi.getCitations(articleId)
      setCitationReport(citationData)
      setActive('analysis')
      setStatusMessage('Document uploaded, parsed, and analyzed successfully.')

      const [quality, novelty, methodology, contribution, journal, writing, improvement, reportDetails] = await Promise.all([
        researchApi.analyze('quality', { document_id: articleId, analysis: structure }),
        researchApi.analyze('novelty', { document_id: articleId, analysis: structure }),
        researchApi.analyze('methodology', { document_id: articleId, analysis: structure }),
        researchApi.analyze('contribution', { document_id: articleId, analysis: structure }),
        researchApi.matchJournal({ document_id: articleId, analysis: structure, journal_id: selectedJournalId }),
        researchApi.analyze('writing', { document_id: articleId, analysis: structure }),
        researchApi.generateImprovement({ document_id: articleId, analysis: structure, focus: 'research quality' }),
        researchApi.generateReport({ document_id: articleId, analysis: structure, quality_analysis: quality, selected_journal: selectedJournalId }),
      ])

      setQualityAnalysis(quality)
      setNoveltyAnalysis(novelty)
      setMethodologyAnalysis(methodology)
      setContributionAnalysis(contribution)
      setJournalMatch(journal)
      setImprovements(improvement)
      setReport(reportDetails)
      setActive('report')
    } catch (error) {
      setUploadError(error.message || 'The upload or analysis request failed.')
      setStatusMessage('Upload failed — please retry.')
    } finally {
      setIsUploading(false)
    }
  }

  const selectedJournal = useMemo(
    () => journalList.find((item) => item.journal_id === selectedJournalId) || journalList[0] || { journal_name: 'Nature', journal_id: selectedJournalId },
    [journalList, selectedJournalId],
  )

  const currentTitle = navigation.find((item) => item.id === active)?.label || 'Dashboard'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">p</div>
          <div>
            <strong>PaperPilot</strong>
            <small>research readiness</small>
          </div>
        </div>

        <div className="workspace-switch">
          <div className="avatar">AR</div>
          <div>
            <span>Alex Rivera</span>
            <small>Personal workspace</small>
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
              onClick={() => setActive(id)}
            >
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button type="button" className="nav-item">
            <FolderOpen size={17} />
            <span>All manuscripts</span>
          </button>
          <button type="button" className="nav-item">
            <Settings2 size={17} />
            <span>Settings</span>
          </button>
          <div className="sidebar-footer">
            <div className="avatar small">AI</div>
            <div>
              <span>AI services</span>
              <small className="status-dot">All systems operational</small>
            </div>
            <MoreHorizontal size={17} />
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button type="button" className="mobile-menu" aria-label="Open menu">
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
            <div className="top-avatar">AR</div>
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
              document={document}
              setActive={setActive}
              onUpload={handleFileUpload}
              isUploading={isUploading}
              statusMessage={statusMessage}
              uploadError={uploadError}
            />
          )}

          {active === 'upload' && (
            <UploadPage onUpload={handleFileUpload} isUploading={isUploading} statusMessage={statusMessage} uploadError={uploadError} />
          )}

          {active === 'analysis' && <AnalysisPage document={document} setActive={setActive} citationReport={citationReport} />}
          {active === 'citations' && <CitationPage citationReport={citationReport} document={document} setActive={setActive} />}
          {active === 'journal' && (
            <JournalPage
              selectedJournalId={selectedJournalId}
              setSelectedJournalId={setSelectedJournalId}
              journalList={journalList}
              journalMatch={journalMatch}
              setActive={setActive}
            />
          )}
          {active === 'quality' && <QualityPage qualityAnalysis={qualityAnalysis} setActive={setActive} />}
          {active === 'novelty' && <NoveltyPage noveltyAnalysis={noveltyAnalysis} setActive={setActive} />}
          {active === 'methodology' && <MethodologyPage methodologyAnalysis={methodologyAnalysis} setActive={setActive} />}
          {active === 'improvements' && <ImprovementsPage improvements={improvements} setActive={setActive} />}
          {active === 'report' && <ReportPage report={report} setActive={setActive} />}
          {active === 'export' && <ExportPage document={document} selectedJournal={selectedJournal} setActive={setActive} />}
        </div>
      </main>
    </div>
  )
}

function Dashboard({ document, setActive, onUpload, isUploading, statusMessage, uploadError }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">THURSDAY, SEPTEMBER 17, 2026</p>
          <h1>Research readiness dashboard<span className="period">.</span></h1>
          <p className="subtitle">Track manuscript status, AI quality checks, and publication readiness from one place.</p>
        </div>
        <label className="primary-button upload-trigger">
          <Plus size={17} />
          Upload manuscript
          <input type="file" accept=".docx" hidden onChange={onUpload} />
        </label>
      </section>

      <section className="upload-banner">
        <div className="upload-icon"><UploadCloud size={23} /></div>
        <div>
          <strong>{statusMessage}</strong>
          <span>{uploadError || 'Upload a DOCX and the system will structure the manuscript, check citations, and run the research quality evaluation.'}</span>
        </div>
        <label className="outline-button">
          {isUploading ? 'Processing...' : 'Upload DOCX'}
          <ArrowUpRight size={15} />
          <input type="file" accept=".docx" hidden onChange={onUpload} />
        </label>
      </section>

      <section className="stats-grid">
        <Stat label="Manuscripts" value="4" detail="1 in review" icon={FileText} />
        <Stat label="Readiness" value="76" suffix="/100" detail="Improving" icon={Gauge} green />
        <Stat label="Open suggestions" value="12" detail="4 high priority" icon={Sparkles} />
      </section>

      <section className="section-heading">
        <div>
          <p className="kicker">RECENT FILES</p>
          <h2>Recent manuscripts</h2>
        </div>
        <button type="button" className="text-button" onClick={() => setActive('analysis')}>View all <ArrowUpRight size={15} /></button>
      </section>

      <div className="manuscript-list">
        {[document].map((doc) => (
          <button type="button" className="manuscript-row" key={doc.document_id} onClick={() => setActive('analysis')}>
            <div className="doc-type"><FileText size={18} /></div>
            <div className="doc-name">
              <strong>{doc.title}</strong>
              <span>{doc.document_id} · Updated 18 min ago</span>
            </div>
            <span className="status green">In review</span>
            <div className="score"><strong>76</strong><span>readiness</span></div>
            <ChevronRight size={17} className="row-arrow" />
          </button>
        ))}
      </div>

      <section className="section-heading modules-heading">
        <div>
          <p className="kicker">INTELLIGENCE LAYERS</p>
          <h2>Review modules</h2>
        </div>
        <span className="muted-label">Select a module to explore</span>
      </section>

      <div className="module-grid">
        <ModuleCard title="Research quality" eyebrow="01 / Completeness" text="Structured review of completeness, evidence, and clarity." value="76" unit="/100" tone="lavender" icon={BarChart3} onClick={() => setActive('quality')} />
        <ModuleCard title="Novelty signals" eyebrow="02 / Similarity search" text="Compare your contribution against relevant scholarly papers." value="0.18" unit="overlap" tone="mint" icon={Sparkles} onClick={() => setActive('novelty')} />
        <ModuleCard title="Methodology" eyebrow="03 / Reproducibility" text="Check datasets, baselines, metrics, and experimental coverage." value="4" unit="gaps" tone="peach" icon={ClipboardCheck} onClick={() => setActive('methodology')} />
      </div>
    </>
  )
}

function UploadPage({ onUpload, isUploading, statusMessage, uploadError }) {
  return (
    <section className="panel upload-panel">
      <p className="kicker">UPLOAD</p>
      <h1>Upload DOCX manuscript</h1>
      <label className="dropzone">
        <UploadCloud size={32} />
        <span>Drag & drop your manuscript here</span>
        <strong>or click to browse</strong>
        <input type="file" accept=".docx" onChange={onUpload} />
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
            {(citationReport.missing_references || []).length === 0 && (citationReport.uncited_references || []).length === 0 && (citationReport.duplicate_references || []).length === 0 && (citationReport.numbering_issues || []).length === 0 ? (
              <div className="finding"><span className="finding-mark good"><Check size={14} /></span><div><strong>No major citation issues detected</strong><span>Reference integrity looks consistent in the current draft.</span></div></div>
            ) : (
              <>
                {(citationReport.missing_references || []).map((issue, idx) => (
                  <div className="finding" key={`missing-${idx}`}>
                    <span className="finding-mark warning">!</span>
                    <div><strong>{issue.citation || 'Citation issue'}</strong><span>{issue.message}</span></div>
                  </div>
                ))}
                {(citationReport.uncited_references || []).map((issue, idx) => (
                  <div className="finding" key={`uncited-${idx}`}>
                    <span className="finding-mark warning">!</span>
                    <div><strong>{issue.citation || 'Uncited reference'}</strong><span>{issue.message}</span></div>
                  </div>
                ))}
                {(citationReport.duplicate_references || []).map((issue, idx) => (
                  <div className="finding" key={`duplicate-${idx}`}>
                    <span className="finding-mark neutral">•</span>
                    <div><strong>Duplicate reference</strong><span>{issue.message}</span></div>
                  </div>
                ))}
                {(citationReport.numbering_issues || []).map((issue, idx) => (
                  <div className="finding" key={`number-${idx}`}>
                    <span className="finding-mark warning">!</span>
                    <div><strong>{issue.citation || 'Citation numbering issue'}</strong><span>{issue.message}</span></div>
                  </div>
                ))}
              </>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div><p className="kicker">EXAMPLE</p><h2>Reference review</h2></div>
          </div>
          <div className="finding-list">
            <div className="finding">
              <span className="finding-mark warning">!</span>
              <div><strong>Citation [12]</strong><span>Missing corresponding reference</span></div>
            </div>
            <div className="finding">
              <span className="finding-mark warning">!</span>
              <div><strong>Reference [8]</strong><span>Not cited in manuscript</span></div>
            </div>
            <div className="finding">
              <span className="finding-mark neutral">•</span>
              <div><strong>Reference [17]</strong><span>Duplicate entry detected</span></div>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}

function JournalPage({ selectedJournalId, setSelectedJournalId, journalList, journalMatch, setActive }) {
  const handleSelect = (event) => setSelectedJournalId(event.target.value)

  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">SCOPE SUITABILITY</p>
          <h1>Journal fit analysis<span className="period">.</span></h1>
          <p className="subtitle">Assess topic alignment and scope gaps using a similarity-based suitability review.</p>
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
          <div className="score-badge">{Math.round((journalMatch.score || 0.82) * 100)}% match</div>
        </div>
        <div className="finding-list">
          <div className="finding">
            <span className="finding-mark good"><Check size={14} /></span>
            <div><strong>Relevant topics</strong><span>{(journalMatch.relevant_topics || []).join(', ')}</span></div>
          </div>
          <div className="finding">
            <span className="finding-mark warning">!</span>
            <div><strong>Scope gaps</strong><span>{(journalMatch.scope_gaps || []).join(' ') || 'No major gaps detected.'}</span></div>
          </div>
          <div className="finding">
            <span className="finding-mark neutral">•</span>
            <div><strong>Explanation</strong><span>{journalMatch.explanation}</span></div>
          </div>
        </div>
      </section>
    </>
  )
}

function QualityPage({ qualityAnalysis, setActive }) {
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
      </div>
    </>
  )
}

function NoveltyPage({ noveltyAnalysis, setActive }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">SIMILARITY EVIDENCE</p>
          <h1>Novelty analysis<span className="period">.</span></h1>
          <p className="subtitle">Review related work similarity and the evidence needed to strengthen differentiation.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('methodology')}>Review methodology <ArrowUpRight size={16} /></button>
      </section>
      <div className="detail-grid two-col">
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">SIMILAR PAPERS</p><h2>Related research</h2></div></div>
          <div className="finding-list">
            {(noveltyAnalysis.similar_papers || []).map((paper, idx) => (
              <div className="finding" key={`${paper.title}-${idx}`}>
                <span className="finding-mark neutral">{idx + 1}</span>
                <div><strong>{paper.title}</strong><span>{paper.venue} · {paper.year} · similarity {paper.similarity}</span></div>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><div><p className="kicker">RECOMMENDATION</p><h2>What to improve</h2></div></div>
          <p className="supporting-text">{noveltyAnalysis.comparative_summary}</p>
          <ul className="mini-list">
            {(noveltyAnalysis.potential_differentiators || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>
    </>
  )
}

function MethodologyPage({ methodologyAnalysis, setActive }) {
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

function ImprovementsPage({ improvements, setActive }) {
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">RESEARCHER CONTROL</p>
          <h1>AI improvement suggestions<span className="period">.</span></h1>
          <p className="subtitle">Review and decide whether each suggestion should be accepted, rejected, or edited.</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setActive('report')}>Open readiness report <ArrowUpRight size={16} /></button>
      </section>
      <div className="improvement-list">
        {(improvements.suggestions || []).map((item) => (
          <div key={item.id} className="panel improvement-card">
            <div className="improvement-header">
              <span>{item.section}</span>
              <div className="button-row">
                <button type="button" className="chip accept">Accept</button>
                <button type="button" className="chip reject">Reject</button>
                <button type="button" className="chip edit">Edit</button>
              </div>
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
  return (
    <>
      <section className="page-intro">
        <div>
          <p className="kicker">PRE-SUBMISSION ASSESSMENT</p>
          <h1>{report.title}<span className="period">.</span></h1>
          <p className="subtitle">{report.summary}</p>
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

function ExportPage({ document, selectedJournal, setActive }) {
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
        <div className="status-box success-box">
          <strong>Ready for export</strong>
          <p>Manuscript: {document.title} · Journal: {selectedJournal?.journal_name || 'Nature'}</p>
        </div>
        <div className="button-row export-buttons">
          <button type="button" className="primary-button">Download DOCX</button>
          <button type="button" className="outline-button">Download PDF</button>
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

export default App

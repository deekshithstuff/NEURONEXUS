import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  ArrowUpRight, BarChart3, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp,
  ClipboardCheck, FileText, FolderOpen, Gauge, Globe2, Moon, MoreHorizontal,
  PanelLeft, Plus, Search, Settings2, ShieldCheck, Sparkles, Sun, UploadCloud,
  X, Zap
} from 'lucide-react'
import './style.css'

const nav = [
  { label: 'Overview', icon: Gauge, id: 'dashboard' },
  { label: 'Document', icon: FileText, id: 'analysis' },
  { label: 'Citations', icon: BookOpen, id: 'citations', badge: '3' },
  { label: 'Journal fit', icon: Globe2, id: 'journal' },
  { label: 'Research quality', icon: BarChart3, id: 'quality' },
  { label: 'Novelty', icon: Sparkles, id: 'novelty' },
  { label: 'Methodology', icon: ClipboardCheck, id: 'methodology' },
  { label: 'Improvements', icon: Zap, id: 'improvements' },
  { label: 'Readiness report', icon: ShieldCheck, id: 'report' },
]

const docs = [
  { title: 'Federated learning for clinical imaging', meta: 'DOC-001 · Updated 18 min ago', status: 'In review', score: '76', color: 'green' },
  { title: 'Edge inference in low-resource settings', meta: 'DOC-002 · Updated yesterday', status: 'Needs attention', score: '61', color: 'amber' },
  { title: 'Multimodal retrieval benchmarks', meta: 'DOC-003 · Updated Sep 11', status: 'Ready', score: '88', color: 'blue' },
]

const moduleCards = [
  { id: 'quality', title: 'Research quality', eyebrow: '01 / Completeness', text: 'A structured review of the argument, evidence, and experimental story.', value: '76', unit: '/100', icon: BarChart3, tone: 'lavender' },
  { id: 'novelty', title: 'Novelty signals', eyebrow: '02 / Similarity search', text: 'Compare your contribution against relevant scholarly work.', value: '0.18', unit: 'overlap', icon: Sparkles, tone: 'mint' },
  { id: 'methodology', title: 'Methodology', eyebrow: '03 / Reproducibility', text: 'Check datasets, baselines, parameters, and evaluation coverage.', value: '4', unit: 'gaps', icon: ClipboardCheck, tone: 'peach' },
]

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('paperpilot-theme') || 'light')
  const [active, setActive] = useState('dashboard')
  const [uploaded, setUploaded] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('paperpilot-theme', theme)
  }, [theme])

  const title = nav.find((item) => item.id === active)?.label || 'Overview'
  const navigate = (id) => setActive(id)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><span>p</span></div><div><strong>paperpilot</strong><small>research readiness</small></div></div>
        <div className="workspace-switch"><div className="avatar">AR</div><div><span>Alex Rivera</span><small>Personal workspace</small></div><ChevronDown size={15} /></div>
        <p className="nav-label">WORKSPACE</p>
        <nav>{nav.map(({ label, icon: Icon, id, badge }) => <button key={id} className={active === id ? 'nav-item active' : 'nav-item'} onClick={() => navigate(id)}><Icon size={17} /><span>{label}</span>{badge && <em>{badge}</em>}</button>)}</nav>
        <div className="sidebar-bottom"><button className="nav-item"><FolderOpen size={17} /><span>All manuscripts</span></button><button className="nav-item"><Settings2 size={17} /><span>Settings</span></button><div className="sidebar-footer"><div className="avatar small">AI</div><div><span>AI services</span><small className="status-dot"> All systems operational</small></div><MoreHorizontal size={17} /></div></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><button className="mobile-menu"><PanelLeft size={18} /></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="top-actions"><button className="icon-button" onClick={() => setShowHelp(!showHelp)} title="Help"><CircleHelp size={18} /></button><button className="theme-toggle" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} aria-label="Toggle theme">{theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}</button><div className="top-avatar">AR</div></div></header>
        {showHelp && <div className="help-popover"><strong>Need a hand?</strong><span>PaperPilot flags evidence gaps and suggests improvements. You stay in control of every change.</span><button onClick={() => setShowHelp(false)}><X size={14} /></button></div>}
        <div className="page-container">{active === 'dashboard' ? <Dashboard navigate={navigate} uploaded={uploaded} setUploaded={setUploaded} /> : <WorkspacePage active={active} navigate={navigate} />}</div>
      </main>
    </div>
  )
}

function Dashboard({ navigate, uploaded, setUploaded }) {
  const handleFile = (event) => {
    const file = event.target.files?.[0]
    if (file && file.name.toLowerCase().endsWith('.docx')) setUploaded(true)
  }
  return <>
    <section className="page-intro"><div><p className="kicker">THURSDAY, SEPTEMBER 17, 2026</p><h1>Good morning, Alex<span className="period">.</span></h1><p className="subtitle">Your research is getting closer to ready. Here’s where things stand.</p></div><label className="primary-button"><Plus size={17} /> New manuscript<input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={handleFile} /></label></section>
    {!uploaded && <section className="upload-banner"><div className="upload-icon"><UploadCloud size={23} /></div><div><strong>Start with your manuscript</strong><span>Upload a DOCX and PaperPilot will map its structure, citations, and research story.</span></div><label className="outline-button">Upload DOCX <ArrowUpRight size={15} /><input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={handleFile} /></label></section>}
    <section className="stats-grid"><Stat label="Manuscripts" value={uploaded ? '4' : '3'} detail="1 in review" icon={FileText} /><Stat label="Avg. readiness" value="75" suffix="/100" detail="↑ 8 pts this month" icon={Gauge} green /><Stat label="Open suggestions" value="12" detail="4 high priority" icon={Sparkles} /></section>
    <section className="section-heading"><div><p className="kicker">YOUR WORKSPACE</p><h2>Recent manuscripts</h2></div><button className="text-button" onClick={() => navigate('analysis')}>View all <ArrowUpRight size={15} /></button></section>
    <div className="manuscript-list">{docs.map((doc) => <Manuscript key={doc.title} doc={doc} onClick={() => navigate('analysis')} />)}</div>
    <section className="section-heading modules-heading"><div><p className="kicker">INTELLIGENCE LAYERS</p><h2>Review modules</h2></div><span className="muted-label">Select a module to explore</span></section>
    <div className="module-grid">{moduleCards.map((card) => <button className={`module-card ${card.tone}`} key={card.id} onClick={() => navigate(card.id)}><div className="module-top"><span className="module-icon"><card.icon size={18} /></span><ArrowUpRight size={16} /></div><p className="eyebrow">{card.eyebrow}</p><h3>{card.title}</h3><p>{card.text}</p><div className="module-value"><strong>{card.value}</strong><span>{card.unit}</span></div></button>)}</div>
  </>
}

function Stat({ label, value, suffix, detail, icon: Icon, green }) { return <div className="stat-card"><div className="stat-icon"><Icon size={17} /></div><div><span className="stat-label">{label}</span><div className="stat-number">{value}<small>{suffix}</small></div><span className={green ? 'stat-detail green-text' : 'stat-detail'}>{detail}</span></div></div> }
function Manuscript({ doc, onClick }) { return <button className="manuscript-row" onClick={onClick}><div className="doc-type"><FileText size={18} /></div><div className="doc-name"><strong>{doc.title}</strong><span>{doc.meta}</span></div><span className={`status ${doc.color}`}>{doc.status}</span><div className="score"><strong>{doc.score}</strong><span>readiness</span></div><ChevronRight size={17} className="row-arrow" /></button> }

function WorkspacePage({ active, navigate }) {
  const config = {
    analysis: { kicker: 'DOCUMENT INTELLIGENCE', title: 'Document analysis', sub: 'A grounded map of what is present in your manuscript.', stat: '92%', statLabel: 'structure detected', next: 'Check citations', nextId: 'citations' },
    citations: { kicker: 'REFERENCE INTEGRITY', title: 'Citation check', sub: 'Resolve the small details that can undermine a strong paper.', stat: '3', statLabel: 'issues to review', next: 'Match a journal', nextId: 'journal' },
    journal: { kicker: 'SCOPE SUITABILITY', title: 'Journal fit', sub: 'Understand how your work aligns with the selected journal’s scope.', stat: '0.84', statLabel: 'scope similarity', next: 'Review quality', nextId: 'quality' },
    quality: { kicker: 'RESEARCH INTELLIGENCE', title: 'Research quality', sub: 'A structured assessment of completeness, evidence, and clarity.', stat: '76', statLabel: 'readiness score', next: 'Explore novelty', nextId: 'novelty' },
    novelty: { kicker: 'SIMILARITY EVIDENCE', title: 'Novelty analysis', sub: 'Signals from related work, never a claim of guaranteed originality.', stat: '0.18', statLabel: 'highest overlap', next: 'Review methodology', nextId: 'methodology' },
    methodology: { kicker: 'REPRODUCIBILITY', title: 'Methodology review', sub: 'Check that another researcher could understand and repeat the work.', stat: '4', statLabel: 'gaps identified', next: 'See improvements', nextId: 'improvements' },
    improvements: { kicker: 'RESEARCHER CONTROL', title: 'AI improvements', sub: 'Review each suggested change before anything touches your manuscript.', stat: '12', statLabel: 'suggestions ready', next: 'Open readiness report', nextId: 'report' },
    report: { kicker: 'PRE-SUBMISSION ASSESSMENT', title: 'Readiness report', sub: 'A transparent assessment of what is ready and what deserves another pass.', stat: '76', statLabel: 'current readiness', next: 'Generate final manuscript', nextId: 'export' },
    export: { kicker: 'FINAL MANUSCRIPT', title: 'Generate & export', sub: 'Create a polished deliverable from the changes you approved.', stat: 'DOCX', statLabel: 'available format', next: 'Back to overview', nextId: 'dashboard' },
  }[active] || {};
  return <><section className="page-intro"><div><p className="kicker">{config.kicker}</p><h1>{config.title}<span className="period">.</span></h1><p className="subtitle">{config.sub}</p></div><button className="primary-button" onClick={() => navigate(config.nextId)}>{config.next} <ArrowUpRight size={16} /></button></section><section className="analysis-hero"><div className="analysis-score"><span className="score-ring">{config.stat}</span><div><span className="eyebrow">FEDERATED LEARNING FOR CLINICAL IMAGING</span><h2>{config.statLabel}</h2><p>Analysis is based on the manuscript currently in review. Evidence is shown with its reason and source.</p></div></div><div className="analysis-meta"><div><span>Last analyzed</span><strong>Today, 09:42</strong></div><div><span>Journal target</span><strong>Nature Machine Intelligence</strong></div><div><span>Document</span><strong>DOC-001</strong></div></div></section><section className="detail-grid"><InsightPanel active={active} /><ActionPanel active={active} navigate={navigate} /></section></>
}

function InsightPanel({ active }) { const rows = active === 'citations' ? [['Citation [12]', 'Missing corresponding reference', 'warning'], ['Reference [8]', 'Not cited in manuscript', 'warning'], ['Reference [17]', 'Duplicate entry detected', 'neutral']] : active === 'methodology' ? [['Dataset source', 'Detected in Section 3', 'good'], ['Evaluation metrics', 'Detected: F1, AUROC', 'good'], ['Baseline comparison', 'Needs stronger evidence', 'warning']] : [['Research gap', 'Clearly stated in introduction', 'good'], ['Experimental completeness', 'Results present; ablation is absent', 'warning'], ['Technical contribution', 'Supported by manuscript evidence', 'good']]; return <section className="panel"><div className="panel-heading"><div><p className="kicker">KEY FINDINGS</p><h2>What we found</h2></div><button className="icon-button"><MoreHorizontal size={18} /></button></div><div className="finding-list">{rows.map(([label, value, tone]) => <div className="finding" key={label}><span className={`finding-mark ${tone}`}>{tone === 'good' ? <Check size={14} /> : tone === 'warning' ? '!' : '·'}</span><div><strong>{label}</strong><span>{value}</span></div><ChevronRight size={16} /></div>)}</div><button className="panel-link">View full evidence <ArrowUpRight size={15} /></button></section> }
function ActionPanel({ active, navigate }) { return <section className="panel action-panel"><p className="kicker">NEXT BEST ACTION</p><h2>{active === 'report' ? 'Ready to make the call?' : 'Keep the review moving.'}</h2><p>{active === 'improvements' ? 'Accept, reject, or edit suggestions one by one. Your research stays yours.' : 'The fastest path to a submission-ready manuscript is a thoughtful pass through each layer.'}</p><div className="action-steps"><div className="step done"><span><Check size={14} /></span><div><strong>Document mapped</strong><small>Structure and references detected</small></div></div><div className="step current"><span>2</span><div><strong>{active === 'citations' ? 'Resolve citation issues' : 'Review flagged evidence'}</strong><small>3 minutes estimated</small></div></div><div className="step"><span>3</span><div><strong>Generate readiness report</strong><small>Make an informed decision</small></div></div></div><button className="primary-button full" onClick={() => navigate(active === 'report' ? 'export' : 'improvements')}>{active === 'report' ? 'Generate final manuscript' : 'Continue review'} <ArrowUpRight size={16} /></button></section> }

createRoot(document.getElementById('app')).render(<App />)

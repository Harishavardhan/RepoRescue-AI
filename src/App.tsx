import { FormEvent, useMemo, useState } from 'react'

type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
type Finding = { key: string; severity: Severity; title: string; explanation: string; fix: string }
type Inspection = {
  repository: { owner: string; name: string; default_branch?: string; description?: string; file_count: number }
  demo: boolean
  findings: Finding[]
  inspected_files: string[]
}

const severityLabels: Record<Severity, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low', info: 'Info' }
const severityWeight: Record<Severity, number> = { critical: 25, high: 16, medium: 9, low: 4, info: 1 }

function Icon({ name }: { name: 'mark' | 'arrow' | 'check' | 'folder' | 'spark' | 'shield' }) {
  const paths = {
    mark: <><path d="M9 3.6 14.4 9 9 14.4 3.6 9 9 3.6Z" /><path d="m7.2 9 1.3 1.3 2.5-2.5" /></>,
    arrow: <><path d="M5 12h12" /><path d="m13 6 6 6-6 6" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    folder: <><path d="M3 7.5h6l1.6 2H21v8.5H3z" /><path d="M3 7.5V6h6l1.6 2" /></>,
    spark: <><path d="m12 3 1.2 5.8L19 10l-5.8 1.2L12 17l-1.2-5.8L5 10l5.8-1.2z" /><path d="m19 15 .5 2.5L22 18l-2.5.5L19 21l-.5-2.5L16 18l2.5-.5z" /></>,
    shield: <><path d="M12 3 20 6v5c0 5-3.2 8.5-8 10-4.8-1.5-8-5-8-10V6z" /><path d="m8 12 2.5 2.5L16 9" /></>,
  }
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function App() {
  const [url, setUrl] = useState('https://github.com/')
  const [demo, setDemo] = useState(false)
  const [result, setResult] = useState<Inspection | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const score = useMemo(() => {
    if (!result) return 0
    const penalty = result.findings.reduce((total, item) => total + severityWeight[item.severity], 0)
    return Math.max(0, Math.min(100, 100 - penalty))
  }, [result])
  const counts = useMemo(() => ({
    high: result?.findings.filter((finding) => finding.severity === 'critical' || finding.severity === 'high').length ?? 0,
    medium: result?.findings.filter((finding) => finding.severity === 'medium').length ?? 0,
    low: result?.findings.filter((finding) => finding.severity === 'low' || finding.severity === 'info').length ?? 0,
  }), [result])

  async function inspect(event?: FormEvent, demoOverride?: boolean) {
    event?.preventDefault()
    const usingDemo = demoOverride ?? demo
    if (!usingDemo && !/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?\/?$/.test(url.trim())) {
      setError('Enter a public GitHub repository URL, such as https://github.com/owner/repository.')
      return
    }
    setLoading(true); setError('')
    try {
      const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
      const response = await fetch(`${base}/api/inspect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ github_url: url.trim(), demo: usingDemo }) })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'The inspection could not be completed.')
      setResult(body as Inspection)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The inspection could not be completed.')
    } finally { setLoading(false) }
  }

  function loadDemo() { setDemo(true); setUrl('https://github.com/reporescue/sample'); void inspect(undefined, true) }

  return <div className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark"><Icon name="mark" /></span><span>RepoRescue <em>AI</em></span></div><div className="topbar-note"><span className="live-dot" /> AI-powered repository review</div></header>
    <main className="container">
      <section className="hero"><div className="eyebrow"><Icon name="spark" /> ENGINEERING HEALTH CHECK</div><h1>Understand your repo.<br /><span>Fix what matters.</span></h1><p>RepoRescue AI scans a public GitHub repository and turns hidden maintenance risks into a clear, prioritized action plan.</p></section>
      <section className="inspect-card"><form onSubmit={inspect}><label htmlFor="repo-url">Repository URL</label><div className="input-row"><div className="url-input"><span>⌘</span><input id="repo-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repository" /></div><button className="primary-button" disabled={loading}>{loading ? <><span className="spinner" /> Inspecting…</> : <>Inspect repository <Icon name="arrow" /></>}</button></div><div className="form-footer"><label className="toggle-label"><button type="button" className={`toggle ${demo ? 'active' : ''}`} onClick={() => setDemo(!demo)} aria-pressed={demo}><span /></button><span><strong>Demo mode</strong><small>Use a sample repository to explore the experience</small></span></label><button type="button" className="demo-link" onClick={loadDemo}><Icon name="spark" /> Try demo</button></div></form></section>
      {error && <div className="error-banner"><strong>Inspection failed</strong><span>{error}</span><button onClick={() => setError('')}>×</button></div>}
      {result ? <section className="results" aria-live="polite">
        <div className="results-heading"><div><div className="eyebrow"><Icon name="shield" /> INSPECTION COMPLETE {result.demo && <span className="demo-badge">DEMO</span>}</div><h2>{result.repository.owner} / <strong>{result.repository.name}</strong></h2><p>{result.repository.description || 'Repository health overview and recommended next steps.'}</p></div><div className={`score-ring score-${score >= 75 ? 'good' : score >= 50 ? 'warn' : 'risk'}`}><strong>{score}</strong><span>/ 100</span><small>health score</small></div></div>
        <div className="metric-grid"><div className="metric"><span>FILES REVIEWED</span><strong>{result.repository.file_count}</strong><small><Icon name="folder" /> on {result.repository.default_branch || 'default branch'}</small></div><div className="metric"><span>FINDINGS</span><strong>{result.findings.length}</strong><small><Icon name="spark" /> across your repo</small></div><div className="metric"><span>PRIORITY ITEMS</span><strong>{counts.high}</strong><small className="text-high"><span className="mini-dot" /> need attention first</small></div><div className="metric"><span>STATUS</span><strong className="status-good"><Icon name="check" /> Ready</strong><small>Review your action plan</small></div></div>
        <div className="findings-header"><div><h3>Action plan</h3><p>Prioritized findings with practical fixes.</p></div><div className="legend"><span><i className="dot dot-high" /> {counts.high} high</span><span><i className="dot dot-medium" /> {counts.medium} medium</span><span><i className="dot dot-low" /> {counts.low} low</span></div></div>
        <div className="finding-list">{result.findings.map((finding) => <article className="finding-card" key={finding.key}><div className={`severity severity-${finding.severity}`}><i /> {severityLabels[finding.severity]}</div><div className="finding-content"><h4>{finding.title}</h4><p>{finding.explanation}</p><div className="fix"><span><Icon name="check" /> Suggested fix</span><p>{finding.fix}</p></div></div></article>)}</div>
        {result.inspected_files.length > 0 && <details className="files"><summary><Icon name="folder" /> View inspected files <span>{result.inspected_files.length}</span></summary><div>{result.inspected_files.map((file) => <code key={file}>{file}</code>)}</div></details>}
      </section> : <section className="empty-state"><div className="empty-icon"><Icon name="shield" /></div><h2>Your repository health report will appear here</h2><p>Paste a GitHub URL above, or use demo mode to see how RepoRescue turns codebase signals into next steps.</p></section>}
    </main><footer><span>RepoRescue AI</span><span>Built for calmer codebases <span className="footer-heart">✦</span></span></footer>
  </div>
}

export default App

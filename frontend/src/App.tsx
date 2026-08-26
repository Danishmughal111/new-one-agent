import { useEffect, useState } from 'react'
import { Activity, ArrowUpRight, BriefcaseBusiness, Building2, Check, ChevronRight, CircleAlert, Clock3, Command, FileText, Gauge, LayoutGrid, LoaderCircle, Play, Search, Settings2, Sparkles, Users, Workflow } from 'lucide-react'
import { Agent, Article, BloggerStatus, ConnectionState, Product, WorkflowResult, Activity as ActivityItem, bloggerAuthUrl, disconnectBlogger, loadWorkspace, runWorkflow } from './api'

type View = 'company' | 'trendera' | 'employees' | 'content' | 'products'

const navItems: { id: View; label: string; icon: typeof Building2 }[] = [
  { id: 'company', label: 'Company', icon: Building2 }, { id: 'trendera', label: 'TrendEra', icon: Sparkles },
  { id: 'employees', label: 'Employees', icon: Users }, { id: 'products', label: 'Products', icon: LayoutGrid },
  { id: 'content', label: 'Content', icon: FileText },
]

function Empty({ title, detail }: { title: string; detail: string }) { return <div className="empty"><div className="empty-icon"><CircleAlert size={18} /></div><strong>{title}</strong><span>{detail}</span></div> }

function StatusPill({ state }: { state: ConnectionState }) {
  const copy = state === 'connected' ? 'Connected' : state === 'unavailable' ? 'Backend unavailable' : 'Awaiting backend'
  return <span className={`status-pill ${state}`}><span className="status-dot" />{copy}</span>
}

const affiliateStatusLabels: Record<string, string> = { found: 'Found', cached: 'Cached', manual: 'Manual', not_found: 'Not Found', failed: 'Failed' }
function affiliateStatusLabel(status: string | null | undefined) { return status ? affiliateStatusLabels[status] || status : 'Not Found' }

function WorkflowResultPanel({ result }: { result: WorkflowResult | null }) {
  if (!result) return null
  const label = result.status === 'success' ? 'Success' : result.status === 'partial_success' ? 'Partial success' : 'Failed'
  const url = result.blogger_result?.url
  return <div className={`result-panel ${result.status === 'success' ? 'ok' : result.status === 'partial_success' ? 'partial' : 'fail'}`}>
    <div className="result-head"><strong>{label}</strong><span>{result.published ? 'Published live' : result.publish_status === 'draft' ? 'Saved as draft' : result.publish_status === 'failed' ? 'Publish failed' : ''}</span></div>
    {result.selected_product && <div className="result-row"><span>Selected product</span><strong>{result.selected_product}</strong></div>}
    {result.discovery_status && <div className="result-row"><span>Discovery</span><strong>{result.discovery_status}</strong></div>}
    {result.duplicate_check && <div className="result-row"><span>Duplicate check</span><strong>{result.duplicate_check}</strong></div>}
    {result.research && <div className="result-row"><span>Research</span><strong>{result.research.status} · {result.research.sources_succeeded}/{result.research.sources_attempted} sources</strong></div>}
    {result.opportunity && <div className="result-row"><span>Opportunity</span><strong>{result.opportunity.score} · {result.opportunity.rating}</strong></div>}
    {result.seo_score != null && <div className="result-row"><span>SEO score</span><strong>{result.seo_score}{result.primary_keyword ? ` · ${result.primary_keyword}` : ''}</strong></div>}
    {result.labels && result.labels.length > 0 && <div className="result-row"><span>Labels</span><strong>{result.labels.join(', ')}</strong></div>}
    {result.affiliate_status && (
      <div className="result-row affiliate-row">
        <span>Affiliate</span>
        <strong>{affiliateStatusLabel(result.affiliate_status)}</strong>
        {result.affiliate_provider && <em>{result.affiliate_provider}</em>}
        {result.affiliate_product_name && <em>· {result.affiliate_product_name}</em>}
        {result.affiliate_match_score != null && <em>· score {result.affiliate_match_score}</em>}
        <em>· CTA {result.affiliate_cta_inserted ? 'Yes' : 'No'}</em>
        {result.affiliate_url && <a href={result.affiliate_url} target="_blank" rel="noreferrer">{result.affiliate_url} <ArrowUpRight size={12} /></a>}
      </div>
    )}
    <div className="result-row"><span>Article generation</span><strong>{result.article_generated ? 'Success' : 'Failed'}</strong></div>
    <div className="result-row"><span>Image generation</span><strong>{result.image_generated ? 'Success' : 'Failed'}</strong></div>
    <div className="result-row"><span>Blogger publishing</span><strong>{result.published ? 'Published' : result.publish_status === 'failed' ? 'Failed' : 'Not published'}</strong></div>
    {url && <div className="result-row"><span>Published URL</span><a href={url} target="_blank" rel="noreferrer">{url} <ArrowUpRight size={12} /></a></div>}
    {result.error && <div className="result-error"><CircleAlert size={14} /><span>{result.error}</span></div>}
  </div>
}

export function App() {
  const [view, setView] = useState<View>('company')
  const [agents, setAgents] = useState<Agent[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [connection, setConnection] = useState<ConnectionState>('unconfigured')
  const [error, setError] = useState('')
  const [runState, setRunState] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle')
  const [publishNow, setPublishNow] = useState(false)
  const [blogger, setBlogger] = useState<BloggerStatus | null>(null)
  const [runResult, setRunResult] = useState<WorkflowResult | null>(null)

  useEffect(() => {
    loadWorkspace().then(data => { setAgents(data.agents); setProducts(data.products); setArticles(data.articles); setActivity(data.activity); setBlogger(data.blogger); setConnection(data.connection) })
      .catch((err: Error) => { setError(err.message); setConnection(import.meta.env.VITE_API_BASE_URL ? 'unavailable' : 'unconfigured') })
  }, [])

  async function refreshWorkspace() {
    try {
      const data = await loadWorkspace()
      setAgents(data.agents); setProducts(data.products); setArticles(data.articles); setActivity(data.activity); setBlogger(data.blogger); setConnection(data.connection)
    } catch { /* keep existing data on refresh failure */ }
  }

  async function handleRun() {
    if (runState === 'running' || !import.meta.env.VITE_API_BASE_URL) return
    setRunState('running'); setError(''); setRunResult(null)
    try {
      const result = await runWorkflow(publishNow)
      setRunResult(result)
      setRunState(result.status === 'success' ? 'completed' : 'failed')
      if (result.status !== 'success') setError(result.error || 'Workflow did not complete successfully')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start workflow')
      setRunState('failed')
    }
    await refreshWorkspace()
  }

  function handleConnectBlogger() {
    const url = bloggerAuthUrl()
    if (url) window.location.href = url
  }

  async function handleDisconnectBlogger() {
    try { await disconnectBlogger(); setBlogger({ connected: false }) } catch (err) { setError(err instanceof Error ? err.message : 'Unable to disconnect Blogger') }
  }

  const title = view === 'company' ? 'Company overview' : view === 'trendera' ? 'TrendEra department' : view === 'employees' ? 'AI employees' : view === 'products' ? 'Product discovery' : 'Content library'

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">T</div><div><div className="brand-name">TrendEra</div><div className="brand-sub">Company OS</div></div></div>
      <div className="workspace-label">Workspace</div>
      <nav>{navItems.map(item => { const Icon = item.icon; return <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} onClick={() => setView(item.id)}><Icon size={17} /><span>{item.label}</span>{item.id === 'trendera' && <span className="nav-badge">01</span>}</button> })}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><Workflow size={17} /><span>Workflows</span></button><button className="nav-item"><Activity size={17} /><span>Activity</span></button><button className="nav-item"><Settings2 size={17} /><span>Settings</span></button></div>
      <div className="operator-card"><div className="operator-avatar">OS</div><div><strong>Operator view</strong><span>Workspace access</span></div><ChevronRight size={15} /></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>TrendEra Company OS</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="top-actions"><div className="search"><Search size={16} /><span>Search workspace</span><kbd>⌘ K</kbd></div><div className="top-avatar">H</div></div></header>
      <div className="content-wrap">
        <div className="page-heading"><div><div className="eyebrow">Tuesday, August 25, 2026 <span className="eyebrow-line" /> Internal workspace</div><h1>{title}</h1></div><StatusPill state={connection} /></div>
        {error && <div className="error-banner"><CircleAlert size={17} /><span>{error}</span></div>}
        {view === 'company' && <CompanyView agents={agents} activity={activity} onOpenTrendEra={() => setView('trendera')} />}
        {view === 'trendera' && <TrendEraView agents={agents} products={products} articles={articles} runState={runState} runResult={runResult} blogger={blogger} publishNow={publishNow} setPublishNow={setPublishNow} handleRun={handleRun} onConnectBlogger={handleConnectBlogger} onDisconnectBlogger={handleDisconnectBlogger} onOpenProducts={() => setView('products')} onOpenContent={() => setView('content')} />}
        {view === 'employees' && <CollectionView type="employees" agents={agents} />}
        {view === 'products' && <CollectionView type="products" products={products} />}
        {view === 'content' && <CollectionView type="content" articles={articles} />}
      </div>
    </main>
  </div>
}

function CompanyView({ agents, activity, onOpenTrendEra }: { agents: Agent[]; activity: ActivityItem[]; onOpenTrendEra: () => void }) { return <>
  <section className="hero-panel"><div className="hero-copy"><span className="hero-kicker"><span className="live-dot" /> Company operating system</span><h2>A company that keeps<br /><em>moving forward.</em></h2><p>One workspace for your AI employees, departments, and the work they move through every day.</p><button className="primary-button" onClick={onOpenTrendEra}>Enter TrendEra <ArrowUpRight size={16} /></button></div><div className="hero-orbit"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Sparkles size={24} /><span>OS</span></div><div className="orbit-node node-a">T</div><div className="orbit-node node-b">AI</div><div className="orbit-node node-c">+</div></div></section>
  <div className="section-grid three"><section className="card department-card"><div className="card-header"><div><span className="section-label">Active department</span><h3>TrendEra</h3></div><span className="mini-status"><span className="status-dot" /> Ready</span></div><p>Product discovery, research, content, creative, QA, and publishing in one operating loop.</p><button className="text-button" onClick={onOpenTrendEra}>Open department <ChevronRight size={15} /></button></section><section className="card metric-card"><span className="section-label">AI employees</span><div className="metric-value">{agents.length || '—'}</div><p>{agents.length ? 'employees reporting from the backend' : 'Connect the backend to see your workforce'}</p></section><section className="card metric-card"><span className="section-label">Current work</span><div className="metric-value">—</div><p>Live workflow data will appear here</p></section></div>
  <section className="lower-grid"><section className="card"><div className="card-header"><div><span className="section-label">Company activity</span><h3>What is happening</h3></div><Activity size={18} className="muted-icon" /></div>{activity.length ? <div className="activity-list">{activity.slice(0, 5).map(item => <div className="activity-row" key={item.id}><span className="timeline-dot" /><div><strong>{item.message}</strong><span>{item.created_at || 'Recent activity'}</span></div></div>)}</div> : <Empty title="No activity yet" detail="Activity will appear here as your AI employees do work." />}</section><section className="card pulse-card"><div className="card-header"><div><span className="section-label">System pulse</span><h3>Operational view</h3></div><Gauge size={18} className="muted-icon" /></div><div className="pulse-row"><span>Company status</span><strong><span className="status-dot" /> Awaiting connection</strong></div><div className="pulse-row"><span>Departments</span><strong>TrendEra</strong></div><div className="pulse-row"><span>Automation</span><strong>Manual trigger ready</strong></div></section></section>
</> }

function TrendEraView({ agents, products, articles, runState, runResult, blogger, publishNow, setPublishNow, handleRun, onConnectBlogger, onDisconnectBlogger, onOpenProducts, onOpenContent }: { agents: Agent[]; products: Product[]; articles: Article[]; runState: string; runResult: WorkflowResult | null; blogger: BloggerStatus | null; publishNow: boolean; setPublishNow: (value: boolean) => void; handleRun: () => void; onConnectBlogger: () => void; onDisconnectBlogger: () => void; onOpenProducts: () => void; onOpenContent: () => void }) { return <>
  <section className="department-banner"><div><span className="hero-kicker"><span className="live-dot" /> Department 01 · Always ready</span><h2>TrendEra turns signals<br /><em>into stories.</em></h2><p>An AI business unit for discovering products, understanding them, and publishing useful content.</p></div><div className="run-box"><span className="section-label">Autonomous workflow</span><strong>Start one complete run</strong><span className="run-help">Discovery through Blogger, with every stage visible.</span><label className="toggle-row"><input type="checkbox" checked={publishNow} onChange={e => setPublishNow(e.target.checked)} /><span className="toggle" /> Publish live</label><button className="primary-button full" onClick={handleRun} disabled={runState === 'running' || !import.meta.env.VITE_API_BASE_URL}>{runState === 'running' ? <><LoaderCircle size={16} className="spin" /> Workflow running</> : <><Play size={15} fill="currentColor" /> Run workflow</>}</button>{!import.meta.env.VITE_API_BASE_URL && <small>Connect an API to enable runs.</small>}<WorkflowResultPanel result={runResult} /></div></section>
  <section className="workflow card"><div className="card-header"><div><span className="section-label">Operating loop</span><h3>From discovery to publishing</h3></div><span className="workflow-state"><Clock3 size={14} /> {runState === 'running' ? 'Running' : runState === 'completed' ? 'Completed' : runState === 'failed' ? 'Failed' : 'Idle'}</span></div><div className="steps">{['Product discovery','Product research','Article generation','Image generation','Quality assurance','Blogger publishing'].map((step, i) => <div className="step" key={step}><div className="step-icon">{i === 0 ? <Check size={15} /> : i + 1}</div><span>{step}</span>{i < 5 && <div className="step-line" />}</div>)}</div></section>
  <section className="card blogger-card"><div className="card-header"><div><span className="section-label">Blogger</span><h3>Publishing connection</h3></div><span className={`mini-status ${blogger?.connected ? 'connected' : ''}`}><span className="status-dot" />{blogger?.connected ? 'Connected' : 'Not connected'}</span></div>{blogger?.connected ? <div className="blogger-body"><div className="blogger-meta"><span><strong>Blog</strong> {blogger.blog_name || blogger.blog_id || 'Connected blog'}</span>{blogger.email && <span><strong>Account</strong> {blogger.email}</span>}</div><div className="blogger-actions"><button className="primary-button" onClick={onConnectBlogger}>Reconnect</button><button className="text-button" onClick={onDisconnectBlogger}>Disconnect</button></div></div> : <div className="blogger-body"><p>Connect Google Blogger to enable live publishing.</p><button className="primary-button" onClick={onConnectBlogger}>Connect Blogger</button></div>}</section>
  <div className="section-grid two"><section className="card"><div className="card-header"><div><span className="section-label">AI employees</span><h3>People doing the work</h3></div><Users size={18} className="muted-icon" /></div>{agents.length ? <div className="agent-list">{agents.slice(0, 4).map(agent => <div className="agent-row" key={agent.id}><div className="agent-avatar">{agent.name.slice(0, 2).toUpperCase()}</div><div><strong>{agent.name}</strong><span>{agent.role || 'TrendEra employee'}</span></div><span className="agent-status">{agent.status || 'Ready'}</span></div>)}</div> : <Empty title="No employees connected" detail="Agent profiles will appear when the backend exposes them." />}</section><section className="card"><div className="card-header"><div><span className="section-label">Output</span><h3>Recent work</h3></div><BriefcaseBusiness size={18} className="muted-icon" /></div><div className="output-links"><button onClick={onOpenProducts}><span><LayoutGrid size={16} /> Products discovered</span><strong>{products.length || '—'} <ChevronRight size={15} /></strong></button><button onClick={onOpenContent}><span><FileText size={16} /> Articles created</span><strong>{articles.length || '—'} <ChevronRight size={15} /></strong></button></div></section></div>
</> }

function CollectionView({ type, agents = [], products = [], articles = [] }: { type: 'employees' | 'products' | 'content'; agents?: Agent[]; products?: Product[]; articles?: Article[] }) { const rows = type === 'employees' ? agents : type === 'products' ? products : articles; return <section className="card collection-card"><div className="collection-toolbar"><div><span className="section-label">TrendEra workspace</span><h3>{type === 'employees' ? 'AI employees' : type === 'products' ? 'Discovered products' : 'Articles and publishing'}</h3></div><div className="search compact"><Search size={15} /><span>Search</span></div></div>{rows.length ? <div className="table-list">{rows.map((row: Agent | Product | Article) => <div className="table-row" key={row.id}><div className="table-primary"><div className="list-avatar">{('name' in row ? row.name : row.title).slice(0, 1).toUpperCase()}</div><div><strong>{'name' in row ? row.name : row.title}</strong><span>{'role' in row ? row.role || 'Employee' : 'product_name' in row ? row.product_name || 'Product' : 'category' in row ? row.category || 'Product' : 'Article'}</span></div></div><span className="table-status">{'status' in row ? row.status || 'Ready' : 'Ready'}</span><ChevronRight size={16} className="muted-icon" /></div>)}</div> : <Empty title={type === 'employees' ? 'No employees yet' : type === 'products' ? 'No products discovered' : 'No articles yet'} detail="Connect the TrendEra backend to populate this workspace with real data." />}</section> }

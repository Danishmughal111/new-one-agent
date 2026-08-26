export type ConnectionState = 'connected' | 'unconfigured' | 'unavailable'

export type Agent = { id: string; name: string; role?: string; status?: string; current_task?: string }
export type Product = { id: string; name: string; description?: string | null; category?: string | null; image_url?: string | null; created_at?: string; updated_at?: string }
export type Article = { id: string; product_id: string; product_name?: string | null; title: string; status?: string; blogger_url?: string | null; published_at?: string | null; created_at?: string; updated_at?: string }
export type Activity = { id: string; message: string; created_at?: string; type?: string }
export type BloggerStatus = { connected: boolean; blog_id?: string | null; blog_name?: string | null; email?: string | null; connected_at?: string | null }
export type SourceRef = { name?: string; url?: string | null; type?: string; fetched?: boolean }
export type WorkflowResult = { status: 'success' | 'partial_success' | 'failed' | 'skipped' | string; error?: string | null; product_id?: string | null; article_id?: string | null; image_url?: string | null; article_generated?: boolean; image_generated?: boolean; image_status?: string | null; published?: boolean; publish_status?: string | null; selected_product?: string | null; research_status?: string | null; duplicate_check?: string | null; discovery_status?: string | null; research?: { status?: string; sources_attempted?: number; sources_succeeded?: number; sources?: SourceRef[]; missing_information?: string[] } | null; opportunity?: { score?: number; total?: number; rating?: string; factors?: Record<string, number> } | null; seo_score?: number | null; primary_keyword?: string | null; labels?: string[] | null; sources?: SourceRef[] | null; affiliate_status?: string | null; affiliate_provider?: string | null; affiliate_product_name?: string | null; affiliate_match_score?: number | null; affiliate_url?: string | null; affiliate_cta_inserted?: boolean; blogger_result?: { id?: string; url?: string | null; status?: string | null; published?: boolean } | null }

const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error('API is not configured. Set VITE_API_BASE_URL to connect TrendEra.')
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) throw new Error((await response.text()) || `Request failed with ${response.status}`)
  return response.json() as Promise<T>
}

export async function loadWorkspace() {
  const [agents, products, articles, activity, blogger] = await Promise.all([
    request<Agent[]>('/agents'),
    request<Product[]>('/trendera/products'),
    request<Article[]>('/trendera/articles'),
    request<Activity[]>('/activity'),
    request<BloggerStatus>('/auth/blogger/status'),
  ])
  return { agents, products, articles, activity, blogger, connection: 'connected' as ConnectionState }
}

export async function runWorkflow(publishNow: boolean): Promise<WorkflowResult> {
  return request<WorkflowResult>('/trendera/run', { method: 'POST', body: JSON.stringify({ publish_now: publishNow }) })
}

export async function getBloggerStatus(): Promise<BloggerStatus> {
  return request<BloggerStatus>('/auth/blogger/status')
}

export async function disconnectBlogger(): Promise<{ connected: boolean }> {
  return request('/auth/blogger/disconnect', { method: 'POST' })
}

export function bloggerAuthUrl(): string {
  if (!baseUrl) return ''
  return `${baseUrl}/auth/blogger`
}

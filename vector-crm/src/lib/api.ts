import type {
  AnalyticsData,
  AuthResponse,
  Campaign,
  CampaignMetrics,
  CompanyFacets,
  Company,
  DashboardData,
  Enrollment,
  Meeting,
  Paginated,
  PeopleFacets,
  Person,
  PersonDetail,
  PipelineRun,
  SearchResults,
  User,
  Variant,
} from './types'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8787'

export const TOKEN_KEY = 'vector_token'
export const USER_KEY = 'vector_user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function setStoredUser(user: User | null) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(USER_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

function buildQuery(params?: object): string {
  if (!params) return ''
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      value.forEach((v) => sp.append(key, String(v)))
    } else {
      sp.append(key, String(value))
    }
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) }
  if (opts.body) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, headers })
  } catch {
    throw new ApiError(0, 'Network error — is the API server running?')
  }

  if (res.status === 401) {
    setToken(null)
    setStoredUser(null)
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new ApiError(401, 'Session expired. Please sign in again.')
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const data = await res.json()
      message = data.detail || data.error || data.message || message
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ---------- Auth ----------

export function login(email: string, password: string) {
  return request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function me() {
  return request<User>('/api/auth/me')
}

// ---------- Companies ----------

export interface CompanyQuery {
  q?: string
  sort?: 'icp' | 'intent' | 'recent' | 'stage'
  tier?: string[]
  signal?: string[]
  industry?: string[]
  size?: string[]
  stage?: string[]
}

export function getCompanies(params: CompanyQuery = {}) {
  return request<Paginated<Company>>(`/api/companies${buildQuery(params)}`)
}

export function companyFacets() {
  return request<CompanyFacets>('/api/companies/facets')
}

export function getCompany(slug: string) {
  return request<Company>(`/api/companies/${encodeURIComponent(slug)}`)
}

// ---------- People ----------

export interface PeopleQuery {
  q?: string
  role?: string[]
  email_status?: string[]
  tier?: string[]
  company?: string
  status?: string[]
  page?: number
  page_size?: number
}

export function getPeople(params: PeopleQuery = {}) {
  return request<Paginated<Person>>(`/api/people${buildQuery(params)}`)
}

export function peopleFacets() {
  return request<PeopleFacets>('/api/people/facets')
}

export function getPerson(id: string) {
  return request<PersonDetail>(`/api/people/${encodeURIComponent(id)}`)
}

// ---------- Meetings ----------
// The one human-driven write surface: an operator books, holds, and writes up
// their own meetings. Closer fills in the summary from the notes later.

export interface MeetingInput {
  title: string
  kind: string
  occurred_at: string
  duration_min: number
  attendees?: string
  location?: string
  notes?: string
  status?: string
  sentiment?: string
}

export function getMeetings(personId: string) {
  return request<Paginated<Meeting>>(`/api/people/${encodeURIComponent(personId)}/meetings`)
}

export function createMeeting(personId: string, body: MeetingInput) {
  return request<Meeting>(`/api/people/${encodeURIComponent(personId)}/meetings`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateMeeting(meetingId: string, body: Partial<MeetingInput> & { summary?: string }) {
  return request<Meeting>(`/api/meetings/${encodeURIComponent(meetingId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deleteMeeting(meetingId: string) {
  return request<void>(`/api/meetings/${encodeURIComponent(meetingId)}`, { method: 'DELETE' })
}

// ---------- Campaigns ----------

export function getCampaigns() {
  return request<Paginated<Campaign>>('/api/campaigns')
}

export function getCampaign(id: string) {
  return request<Campaign>(`/api/campaigns/${encodeURIComponent(id)}`)
}

export interface EnrollmentQuery {
  channel?: 'email' | 'linkedin'
  q?: string
  status?: string[]
  /** true = only those held for approval, false = only released. */
  held?: boolean
}

export function getCampaignEnrollments(id: string, params: EnrollmentQuery = {}) {
  return request<Paginated<Enrollment>>(
    `/api/campaigns/${encodeURIComponent(id)}/enrollments${buildQuery(params)}`,
  )
}

export function patchSendMode(id: string, sendMode: string) {
  return request<Campaign>(`/api/campaigns/${encodeURIComponent(id)}/send-mode`, {
    method: 'PATCH',
    body: JSON.stringify({ send_mode: sendMode }),
  })
}

export interface LaunchResult {
  released: number
  items: Enrollment[]
  metrics: CampaignMetrics
}

/** Release held first touches: specific enrollments, or everyone held. */
export function launchEnrollments(
  campaignId: string,
  body: { enrollment_ids?: number[]; all?: boolean; channel?: string },
) {
  return request<LaunchResult>(`/api/campaigns/${encodeURIComponent(campaignId)}/launch`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export interface VariantPatch {
  subject_template?: string | null
  body_template?: string
  name?: string
  angle?: string
  is_paused?: boolean
}

export function patchVariant(variantId: string, body: VariantPatch) {
  return request<Variant>(`/api/campaigns/variants/${encodeURIComponent(variantId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function patchCampaignStatus(id: string, status: string) {
  return request<Campaign>(`/api/campaigns/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

// ---------- Dashboard / Analytics / Search ----------

export function getDashboard() {
  return request<DashboardData>('/api/dashboard')
}

export function getAnalytics() {
  return request<AnalyticsData>('/api/analytics')
}

export function search(q: string) {
  return request<SearchResults>(`/api/search${buildQuery({ q })}`)
}

// ---------- Pipeline (read-only; runs are triggered from the backend) ----------

export function getRuns() {
  return request<Paginated<PipelineRun>>('/api/pipeline/runs')
}

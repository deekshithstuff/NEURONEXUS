export const API_BASE = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000')
const AUTH_TOKEN_KEY = 'neuronexus-auth-token'

async function request(path, options = {}) {
  const { responseType, ...fetchOptions } = options
  const headers = new Headers(fetchOptions.headers || {})
  const token = globalThis.sessionStorage?.getItem(AUTH_TOKEN_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const errorBody = await response.json()
      if (errorBody?.detail) message = Array.isArray(errorBody.detail) ? errorBody.detail.map((item) => item.msg || item).join(', ') : errorBody.detail
      else if (errorBody?.message) message = errorBody.message
    } catch {
      // Ignore parse failures and keep the default status message.
    }
    throw new Error(message)
  }
  if (responseType === 'blob') return response.blob()
  const type = response.headers.get('content-type') || ''
  return type.includes('application/json') ? response.json() : response.blob()
}

async function authenticate(path, payload) {
  const result = await request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  globalThis.sessionStorage.setItem(AUTH_TOKEN_KEY, result.access_token)
  return result.user
}

export const researchApi = {
  getAuthConfig: () => request('/api/auth/config'),
  getCurrentUser: async () => (await request('/api/auth/me')).user,
  registerAccount: (payload) => authenticate('/api/auth/register', payload),
  signIn: (payload) => authenticate('/api/auth/login', payload),
  signInWithGoogle: (credential) => authenticate('/api/auth/google', { credential }),
  signOut: () => request('/api/auth/logout', { method: 'POST' }),
  hasStoredAuth: () => Boolean(globalThis.sessionStorage?.getItem(AUTH_TOKEN_KEY)),
  clearAuth: () => globalThis.sessionStorage.removeItem(AUTH_TOKEN_KEY),
  getAiStatus: () => request('/api/ai/status'),
  getPlagiarismStatus: () => request('/api/plagiarism/status'),
  startPlagiarismScan: (id, payload) => request(`/api/documents/${id}/plagiarism/scan`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getPlagiarismScan: (scanId) => request(`/api/plagiarism/scans/${scanId}`),
  getPlagiarismScans: (id) => request(`/api/documents/${id}/plagiarism/scans`),
  downloadPlagiarismReport: (scanId) => request(`/api/plagiarism/scans/${scanId}/download`, { responseType: 'blob' }),
  getDashboardSummary: () => request('/api/documents/dashboard/summary'),
  getDocuments: () => request('/api/documents'),
  uploadDocument: (file) => {
    const body = new FormData()
    body.append('file', file)
    return request('/api/documents/upload', { method: 'POST', body })
  },
  getDocument: (id) => request(`/api/documents/${id}`),
  analyzeDocument: (id, payload = {}) => request(`/api/documents/${id}/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getStructure: (id) => request(`/api/documents/${id}/structure`),
  getSavedAnalysis: (id, module) => request(`/api/documents/${id}/analysis/${module}`),
  checkCitations: (document) => request('/api/citations/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(document) }),
  getCitations: (id) => request(`/api/citations/${id}`),
  getJournals: () => request('/api/journals'),
  getJournalRules: (id) => request(`/api/journals/${id}/rules`),
  analyze: (module, payload) => request(`/api/${module}/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  matchJournal: (payload) => request('/api/journal/match', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  generateImprovement: (payload) => request('/api/improvement/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  generateReport: (payload) => request('/api/report/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  formatDocument: (id, payload) => request(`/api/documents/${id}/format`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  generateDocument: (id, payload) => request(`/api/documents/${id}/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  download: (id, format) => request(`/api/documents/${id}/download/${format}`),
  getArticleTypes: () => request('/api/compliance/article-types'),
  getCompliance: (id, params = {}) => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== null && value !== undefined && value !== ''))
    ).toString()
    return request(`/api/documents/${id}/compliance${query ? `?${query}` : ''}`)
  },
  getWordLimit: (id, params = {}) => request(`/api/documents/${id}/compliance/word-limit?${new URLSearchParams(params)}`),
  getAnalytics: (id, params = {}) => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== null && value !== undefined && value !== ''))
    ).toString()
    return request(`/api/documents/${id}/analytics${query ? `?${query}` : ''}`)
  },
  exportAnalytics: (id, params = {}) => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== null && value !== undefined && value !== ''))
    ).toString()
    return request(`/api/documents/${id}/analytics/export${query ? `?${query}` : ''}`, { responseType: 'blob' })
  },
  getConversions: (id) => request(`/api/documents/${id}/conversions`),
  startConversion: (id, payload) => request(`/api/documents/${id}/conversions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getConversionJob: (jobId) => request(`/api/conversions/${jobId}`),
  downloadConversion: (jobId, format) => request(`/api/conversions/${jobId}/download/${format}`, { responseType: 'blob' }),
  getCollaborators: (id) => request(`/api/documents/${id}/collaborators`),
  inviteCollaborator: (id, payload) => request(`/api/documents/${id}/collaborators`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  updateCollaborator: (id, collaboratorId, payload) => request(`/api/documents/${id}/collaborators/${collaboratorId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  removeCollaborator: (id, collaboratorId) => request(`/api/documents/${id}/collaborators/${collaboratorId}`, { method: 'DELETE' }),
  getInvitations: () => request('/api/collaboration/invitations'),
  acceptInvitation: (collaboratorId) => request(`/api/collaboration/invitations/${collaboratorId}/accept`, { method: 'POST' }),
  getSharedDocuments: () => request('/api/collaboration/shared'),
  getComments: (id, params = {}) => request(`/api/documents/${id}/comments?${new URLSearchParams(params)}`),
  addComment: (id, payload) => request(`/api/documents/${id}/comments`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  resolveComment: (id, commentId, payload = {}) => request(`/api/documents/${id}/comments/${commentId}/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getReviews: (id) => request(`/api/documents/${id}/reviews`),
  submitReview: (id, payload) => request(`/api/documents/${id}/reviews`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getVersions: (id) => request(`/api/documents/${id}/versions`),
  createVersion: (id, payload = {}) => request(`/api/documents/${id}/versions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  diffVersions: (id, fromVersion, toVersion) => request(`/api/documents/${id}/versions/diff?from=${encodeURIComponent(fromVersion)}&to=${encodeURIComponent(toVersion)}`),
  getVersion: (id, versionId) => request(`/api/documents/${id}/versions/${versionId}`),
  restoreVersion: (id, versionId, payload = {}) => request(`/api/documents/${id}/versions/${versionId}/restore`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  getNotifications: (unreadOnly = false) => request(`/api/collaboration/notifications?unread_only=${unreadOnly}`),
  markNotificationsRead: (payload = {}) => request('/api/collaboration/notifications/read', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  assessImprovement: (payload) => request('/api/improvement/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  reviseImprovement: (payload) => request('/api/improvement/revise', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  suggestExperiments: (payload) => request('/api/improvement/experiments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
}

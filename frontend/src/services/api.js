const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
<<<<<<< HEAD
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
=======
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
>>>>>>> 7824d8913e2157f6ebc06f3a0d20be405780bfa0
  const type = response.headers.get('content-type') || ''
  return type.includes('application/json') ? response.json() : response.blob()
}

export const researchApi = {
  uploadDocument: (file) => {
    const body = new FormData()
    body.append('file', file)
    return request('/api/documents/upload', { method: 'POST', body })
  },
  getDocument: (id) => request(`/api/documents/${id}`),
<<<<<<< HEAD
  analyzeDocument: (id, payload = {}) => request(`/api/documents/${id}/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
=======
  analyzeDocument: (id) => request(`/api/documents/${id}/analyze`, { method: 'POST' }),
>>>>>>> 7824d8913e2157f6ebc06f3a0d20be405780bfa0
  getStructure: (id) => request(`/api/documents/${id}/structure`),
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
}

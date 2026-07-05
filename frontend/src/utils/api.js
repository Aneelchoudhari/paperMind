/* API client utility */
const BASE = '';

function getToken() {
  return localStorage.getItem('pm_token');
}

function handleUnauthorized() {
  localStorage.removeItem('pm_token');
  // Redirect to login if not already there
  if (!window.location.pathname.startsWith('/auth')) {
    window.location.href = '/auth';
  }
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(BASE + path, { ...options, headers });

  if (res.status === 204) return null;

  // Auto-logout on expired/invalid token — but NOT on auth routes themselves
  // (wrong password on /auth/login also returns 401, that's not a session expiry)
  if (res.status === 401 && !path.startsWith('/auth/')) {
    handleUnauthorized();
    throw new Error('Session expired. Please sign in again.');
  }

  const data = await res.json().catch(() => ({ error: { code: 'PARSE_ERROR', message: 'Invalid response' } }));
  if (!res.ok) {
    const err = data?.error || data?.detail;
    throw new Error(typeof err === 'string' ? err : err?.message || `HTTP ${res.status}`);
  }
  return data;
}

export const api = {
  // Auth
  register: (body) => apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body) => apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  me: () => apiFetch('/auth/me'),

  // Papers
  uploadPaper: (formData) => apiFetch('/papers', { method: 'POST', body: formData }),
  listPapers: (params = {}) => apiFetch('/papers?' + new URLSearchParams(params)),
  getPaper: (id) => apiFetch(`/papers/${id}`),
  getPaperStatus: (id) => apiFetch(`/papers/${id}/status`),
  deletePaper: (id) => apiFetch(`/papers/${id}`, { method: 'DELETE' }),
  getRelated: (id) => apiFetch(`/papers/${id}/related`),

  // Search
  search: (body) => apiFetch('/search', { method: 'POST', body: JSON.stringify(body) }),

  // QA
  qa: (body) => apiFetch('/qa', { method: 'POST', body: JSON.stringify(body) }),

  // Analytics
  analytics: () => apiFetch('/analytics/overview'),

  // History
  history: (limit = 20) => apiFetch(`/users/me/history?limit=${limit}`),
};

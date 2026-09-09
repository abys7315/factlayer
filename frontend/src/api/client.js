/**
 * API client for Fact Knowledge Layer backend.
 * Features automatic failover between Vite proxy (/api/v1) and direct backend (http://localhost:8000/api/v1).
 */

const PROXY_API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const DIRECT_API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://factlayer-backend.onrender.com/api/v1' : 'http://localhost:8000/api/v1');

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const err = await response.json();
      errorDetail = err.detail || err.message || JSON.stringify(err);
    } catch {
      errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

async function request(path, options = {}) {
  // Try proxy first; on connection refusal / network error, fall back directly to backend port 8000
  try {
    const res = await fetch(`${PROXY_API_BASE}${path}`, options);
    return await handleResponse(res);
  } catch (proxyErr) {
    try {
      const directRes = await fetch(`${DIRECT_API_BASE}${path}`, options);
      return await handleResponse(directRes);
    } catch {
      throw proxyErr;
    }
  }
}

export const api = {
  // Stats
  async getDashboardStats() {
    return request('/documents/stats/overview');
  },

  // Documents
  async listDocuments(skip = 0, limit = 50) {
    return request(`/documents?skip=${skip}&limit=${limit}`);
  },

  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    return request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async getDocument(docId) {
    return request(`/documents/${docId}`);
  },

  async getDocumentStatus(docId) {
    return request(`/documents/${docId}/status`);
  },

  async deleteDocument(docId) {
    return request(`/documents/${docId}`, {
      method: 'DELETE',
    });
  },

  // Facts
  async listFacts(params = {}) {
    const query = new URLSearchParams();
    if (params.document_id) query.append('document_id', params.document_id);
    if (params.entity_id) query.append('entity_id', params.entity_id);
    if (params.entity_name) query.append('entity_name', params.entity_name);
    if (params.attribute) query.append('attribute', params.attribute);
    if (params.category) query.append('category', params.category);
    if (params.min_confidence !== undefined) query.append('min_confidence', params.min_confidence);
    if (params.skip !== undefined) query.append('skip', params.skip);
    if (params.limit !== undefined) query.append('limit', params.limit);

    return request(`/facts?${query.toString()}`);
  },

  async getFact(factId) {
    return request(`/facts/${factId}`);
  },

  async getFactEvidence(factId) {
    return request(`/facts/${factId}/evidence`);
  },

  // Relationships
  async listRelationships(params = {}) {
    const query = new URLSearchParams();
    if (params.type) query.append('type', params.type);
    if (params.fact_id) query.append('fact_id', params.fact_id);
    if (params.document_id) query.append('document_id', params.document_id);
    if (params.min_confidence !== undefined) query.append('min_confidence', params.min_confidence);
    if (params.skip !== undefined) query.append('skip', params.skip);
    if (params.limit !== undefined) query.append('limit', params.limit);

    return request(`/relationships?${query.toString()}`);
  },

  async getContradictions(params = {}) {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append('skip', params.skip);
    if (params.limit !== undefined) query.append('limit', params.limit);
    return request(`/relationships/contradictions?${query.toString()}`);
  },

  async getSupersedes(params = {}) {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append('skip', params.skip);
    if (params.limit !== undefined) query.append('limit', params.limit);
    return request(`/relationships/supersedes?${query.toString()}`);
  },

  async getRelationship(relId) {
    return request(`/relationships/${relId}`);
  },

  async recomputeRelationships() {
    return request('/relationships/recompute', {
      method: 'POST',
    });
  },

  // Knowledge Graph
  async getGraph(params = {}) {
    const query = new URLSearchParams();
    if (params.fact_id) query.append('fact_id', params.fact_id);
    if (params.entity_name) query.append('entity_name', params.entity_name);
    if (params.document_id) query.append('document_id', params.document_id);
    if (params.doc_id) query.append('doc_id', params.doc_id);
    if (params.relationship_id) query.append('relationship_id', params.relationship_id);
    if (params.rel_id) query.append('rel_id', params.rel_id);
    if (params.relationship_type) query.append('relationship_type', params.relationship_type);
    if (params.preset) query.append('preset', params.preset);
    if (params.limit !== undefined) query.append('limit', params.limit);
    return request(`/graph?${query.toString()}`);
  },

  async getGraphEntities(limit = 50) {
    return request(`/graph/entities?limit=${limit}`);
  },

  async getGraphStats() {
    return request('/graph/stats');
  },

  // Viewer & PDF
  getPdfUrl(docId) {
    return `${PROXY_API_BASE}/viewer/${docId}/pdf`;
  },

  getPageImageUrl(docId, pageNumber = 1, dpi = 150) {
    return `${PROXY_API_BASE}/viewer/${docId}/page/${pageNumber}/image?dpi=${dpi}`;
  },

  async getViewerOverlay(docId, factId = null) {
    const query = factId ? `?fact_id=${factId}` : '';
    return request(`/viewer/${docId}/evidence-overlay${query}`);
  },

  // Real-time Event Stream (SSE)
  getEventSource() {
    try {
      return new EventSource(`${PROXY_API_BASE}/events/stream`);
    } catch {
      return new EventSource(`${DIRECT_API_BASE}/events/stream`);
    }
  },
};

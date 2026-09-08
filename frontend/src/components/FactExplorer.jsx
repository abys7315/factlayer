import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconDatabase,
  IconSearch,
  IconFilter,
  IconEye,
  IconRefreshCw,
  IconSparkles,
  IconShieldCheck,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';

export default function FactExplorer() {
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchEntity, setSearchEntity] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [selectedFactForModal, setSelectedFactForModal] = useState(null);
  const [evidenceList, setEvidenceList] = useState([]);
  const [loadingEvidence, setLoadingEvidence] = useState(false);

  const fetchFacts = async () => {
    try {
      setLoading(true);
      const params = {
        limit: 100,
        min_confidence: minConfidence > 0 ? minConfidence / 100 : undefined,
      };
      if (searchEntity) params.entity_name = searchEntity;
      if (selectedCategory) params.category = selectedCategory;

      const data = await api.listFacts(params);
      setFacts(data.items || []);
    } catch (err) {
      console.error('Failed to load facts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFacts();
  }, [selectedCategory, minConfidence]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchFacts();
  };

  const handleOpenEvidence = async (fact) => {
    setSelectedFactForModal(fact);
    try {
      setLoadingEvidence(true);
      const data = await api.getFactEvidence(fact.id);
      setEvidenceList(data.items || []);
    } catch (err) {
      console.error('Failed to load evidence for fact:', err);
    } finally {
      setLoadingEvidence(false);
    }
  };

  const categories = ['Financial', 'Corporate', 'Operational', 'Legal', 'Executive', 'General'];

  return (
    <div className="fact-explorer-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Autonomous Fact Explorer</h1>
          <p className="page-subtitle">
            Search, filter, and inspect canonical facts extracted from ingested documents with complete normalized attributes.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/graph?from=facts${searchEntity ? `&entity=${encodeURIComponent(searchEntity)}` : ''}`}
            className="btn btn-secondary btn-sm flex items-center gap-1.5"
            title="Explore Facts in Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4 text-purple-400" />
            <span>Explore in Graph</span>
          </Link>
          <button className="btn btn-ghost" onClick={fetchFacts}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="card glass-card p-4">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider">Search Entity or Attribute</label>
            <div className="search-input-wrapper">
              <IconSearch className="search-icon w-4 h-4 text-muted" />
              <input
                type="text"
                placeholder="e.g. Acme Corp, Q3 Revenue, CEO, Net Margin..."
                value={searchEntity}
                onChange={(e) => setSearchEntity(e.target.value)}
                className="input-field pl-9"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider">Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="input-field"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat.toLowerCase()}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary flex-1">
              Apply Filters
            </button>
          </div>
        </form>
      </div>

      {/* Facts Table */}
      <div className="card glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-custom">
            <thead>
              <tr>
                <th>Entity Name</th>
                <th>Attribute Key</th>
                <th>Normalized Value</th>
                <th>Raw Extracted Text</th>
                <th>Validity Interval</th>
                <th>Confidence</th>
                <th>Category</th>
                <th className="text-right">Provenance</th>
              </tr>
            </thead>
            <tbody>
              {facts.length === 0 ? (
                <tr>
                  <td colSpan="8" className="text-center py-12 text-muted">
                    {loading ? 'Searching knowledge repository...' : 'No facts match your query.'}
                  </td>
                </tr>
              ) : (
                facts.map((fact) => (
                  <tr key={fact.id} className="hover:bg-surface-alt/60 transition-colors">
                    <td>
                      <div className="font-semibold text-primary">
                        {fact.entity_name || 'N/A'}
                      </div>
                      <div className="text-[10px] text-muted font-mono">
                        {fact.document_id ? `Doc: ${fact.document_id.substring(0, 8)}...` : ''}
                      </div>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-accent">
                        {fact.attribute}
                      </span>
                    </td>
                    <td>
                      <div className="font-mono text-xs text-emerald-400 font-semibold max-w-[200px] truncate">
                        {typeof fact.normalized_value === 'object'
                          ? JSON.stringify(fact.normalized_value)
                          : String(fact.normalized_value ?? '—')}
                      </div>
                    </td>
                    <td className="text-xs text-secondary max-w-[180px] truncate">
                      "{fact.value_text}"
                    </td>
                    <td>
                      <span className="text-xs font-mono text-muted">
                        {fact.validity_start || 'N/A'}
                        {fact.validity_end ? ` → ${fact.validity_end}` : ''}
                      </span>
                    </td>
                    <td>
                      <span className="confidence-pill font-mono">
                        {((fact.confidence_score || 0.95) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td>
                      <span className="badge-pill text-[10px]">
                        {fact.category || 'General'}
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenEvidence(fact)}
                          title="Inspect Evidence Chain"
                        >
                          <IconShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Evidence</span>
                        </button>
                        <Link
                          to={`/graph?fact_id=${fact.id}&entity=${encodeURIComponent(fact.entity_name || '')}&doc_id=${fact.document_id || ''}&from=facts`}
                          className="btn btn-ghost btn-sm text-purple-400 hover:text-purple-300"
                          title="Explore in Knowledge Graph"
                        >
                          <IconNetwork className="w-3.5 h-3.5" />
                        </Link>
                        {fact.document_id && (
                          <Link
                            to={`/viewer/${fact.document_id}?fact_id=${fact.id}`}
                            className="btn btn-ghost btn-sm text-indigo-400"
                            title="Jump to PDF Bounding Box"
                          >
                            <IconEye className="w-3.5 h-3.5" />
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Evidence Drawer Modal */}
      {selectedFactForModal && (
        <div className="modal-backdrop" onClick={() => setSelectedFactForModal(null)}>
          <div className="modal-content glass-card max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2">
                <IconShieldCheck className="w-5 h-5 text-indigo-400" />
                <div>
                  <h3 className="modal-title">Evidence & Provenance Chain</h3>
                  <p className="modal-subtitle">
                    {selectedFactForModal.entity_name} &bull; {selectedFactForModal.attribute}
                  </p>
                </div>
              </div>
              <button className="btn-close" onClick={() => setSelectedFactForModal(null)}>&times;</button>
            </div>

            <div className="modal-body space-y-4">
              <div className="p-3 rounded-lg bg-surface border border-border">
                <span className="text-xs text-muted block uppercase font-mono">Normalized Value:</span>
                <span className="text-base font-mono text-emerald-400 font-semibold">
                  {typeof selectedFactForModal.normalized_value === 'object'
                    ? JSON.stringify(selectedFactForModal.normalized_value)
                    : String(selectedFactForModal.normalized_value ?? selectedFactForModal.value_text)}
                </span>
              </div>

              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">
                  Source Grounding & Bounding Boxes
                </h4>
                {loadingEvidence ? (
                  <p className="text-xs text-muted">Loading evidence coordinates...</p>
                ) : evidenceList.length === 0 ? (
                  <p className="text-xs text-muted">Direct paragraph extraction grounding.</p>
                ) : (
                  evidenceList.map((ev, idx) => (
                    <div key={ev.id || idx} className="p-3 rounded bg-surface-alt border border-border-subtle space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-accent">Page {ev.page_number} • {ev.block_type || 'Text Block'}</span>
                        <span className="font-mono text-muted">Confidence: {((ev.confidence || 0.95) * 100).toFixed(0)}%</span>
                      </div>
                      <p className="p-2 rounded bg-black/40 text-xs font-mono text-secondary">
                        "{ev.snippet}"
                      </p>
                      {ev.bbox && (
                        <div className="text-[10px] font-mono text-muted">
                          BBox: [{ev.bbox.x0?.toFixed(2)}, {ev.bbox.y0?.toFixed(2)}, {ev.bbox.x1?.toFixed(2)}, {ev.bbox.y1?.toFixed(2)}]
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="modal-footer">
              {selectedFactForModal.document_id && (
                <Link
                  to={`/viewer/${selectedFactForModal.document_id}?fact_id=${selectedFactForModal.id}`}
                  className="btn btn-primary btn-sm"
                >
                  <IconEye className="w-4 h-4" />
                  <span>Open in PDF Viewer</span>
                </Link>
              )}
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedFactForModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

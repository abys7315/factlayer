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
  IconFileText,
  IconExternalLink,
  IconX,
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

  // Format fact values cleanly
  const formatFactDisplay = (fact) => {
    if (!fact) return { text: 'N/A', unit: null };
    let text = (fact.value_text && String(fact.value_text).trim())
      || (fact.object_value && String(fact.object_value).trim())
      || (fact.normalized_value !== null ? String(fact.normalized_value) : 'N/A');

    let unit = fact.unit || fact.currency || null;
    if (unit) {
      const lowerText = text.toLowerCase();
      const lowerUnit = unit.toLowerCase();
      if (lowerText.includes(lowerUnit) || (lowerUnit === '%' && lowerText.includes('per cent'))) {
        unit = null;
      }
    }
    return { text, unit };
  };

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
            className="crystal-btn-trace"
            title="Explore Facts in Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4 text-indigo-600" />
            <span>Explore in Graph</span>
          </Link>
          <button className="crystal-btn-trace" onClick={fetchFacts}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="card p-5 bg-white border border-slate-200 rounded-2xl shadow-xs">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-bold text-slate-600 uppercase tracking-wider">Search Entity or Metric</label>
            <div className="search-input-wrapper">
              <IconSearch className="search-icon w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="e.g. GDP, Baseline Comparison, Acme Corp, Revenue..."
                value={searchEntity}
                onChange={(e) => setSearchEntity(e.target.value)}
                className="input-field pl-9"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-bold text-slate-600 uppercase tracking-wider">Category</label>
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
            <button type="submit" className="crystal-btn-graph w-full justify-center">
              Apply Filters
            </button>
          </div>
        </form>
      </div>

      {/* Facts Table */}
      <div className="card overflow-hidden bg-white border border-slate-200 rounded-2xl shadow-xs">
        <div className="overflow-x-auto">
          <table className="audit-matrix-table" style={{ border: 'none', borderRadius: 0 }}>
            <thead>
              <tr>
                <th style={{ width: '22%' }}>Entity</th>
                <th style={{ width: '18%' }}>Metric / Attribute</th>
                <th style={{ width: '22%' }}>Asserted Fact Value</th>
                <th style={{ width: '12%' }}>Reporting Period</th>
                <th style={{ width: '10%' }}>Confidence</th>
                <th style={{ width: '8%' }}>Category</th>
                <th style={{ width: '8%', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {facts.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-12 text-slate-500">
                    {loading ? 'Searching knowledge repository...' : 'No facts match your query.'}
                  </td>
                </tr>
              ) : (
                facts.map((fact) => {
                  const { text, unit } = formatFactDisplay(fact);
                  const conf = Math.round((fact.confidence_score || 0.95) * 100);
                  return (
                    <tr key={fact.id}>
                      <td>
                        <div style={{ fontWeight: 750, color: '#0F172A', fontSize: '15.5px' }}>
                          {fact.entity_name || 'Organization'}
                        </div>
                        {fact.document_id && (
                          <div style={{ fontSize: '12px', color: '#64748B', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                            Doc: {fact.document_id.substring(0, 8)}...
                          </div>
                        )}
                      </td>
                      <td>
                        <span style={{ fontWeight: 650, color: '#2563EB', fontSize: '14.5px' }}>
                          {fact.attribute}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span style={{ fontWeight: 800, color: '#0F172A', fontSize: '16px' }}>
                            {text}
                          </span>
                          {unit && (
                            <span style={{ fontSize: '12px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', background: '#DBEAFE', color: '#1D4ED8' }}>
                              {unit}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: '13.5px', fontWeight: 600, color: '#475569' }}>
                          {fact.validity_start || 'Current'}
                          {fact.validity_end ? ` → ${fact.validity_end}` : ''}
                        </span>
                      </td>
                      <td>
                        <span className="audit-status-pill aligned" style={{ padding: '3px 10px', fontSize: '13px' }}>
                          {conf}%
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '12.5px', fontWeight: 600, padding: '3px 10px', borderRadius: '6px', background: '#F1F5F9', color: '#475569', textTransform: 'capitalize' }}>
                          {fact.category || 'General'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="flex items-center justify-end gap-2">
                          <button
                            className="btn-trace-action"
                            style={{ padding: '5px 11px', fontSize: '13px' }}
                            onClick={() => handleOpenEvidence(fact)}
                            title="Inspect Evidence Citations"
                          >
                            <IconShieldCheck style={{ width: 14, height: 14, color: '#2563EB' }} />
                            <span>Evidence</span>
                          </button>
                          <Link
                            to={`/graph?fact_id=${fact.id}&entity=${encodeURIComponent(fact.entity_name || '')}&doc_id=${fact.document_id || ''}&from=facts`}
                            className="btn-trace-action"
                            style={{ padding: '4px 7px' }}
                            title="Explore in Knowledge Graph"
                          >
                            <IconNetwork style={{ width: 13, height: 13 }} />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Fact Evidence Inspection Modal */}
      {selectedFactForModal && (
        <div className="modal-backdrop" onClick={() => setSelectedFactForModal(null)}>
          <div className="modal-content trace-modal" style={{ maxHeight: '75vh', maxWidth: '720px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="flex items-center gap-2">
                <IconShieldCheck style={{ width: 18, height: 18, color: '#2563EB' }} />
                <h3 style={{ fontSize: '17px', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                  Ground-Truth Fact Verification
                </h3>
              </div>
              <button className="btn-close" onClick={() => setSelectedFactForModal(null)}>
                <IconX style={{ width: 18, height: 18, color: '#64748B' }} />
              </button>
            </div>
            <div className="modal-body space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Asserted Claim</div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
                  {selectedFactForModal.entity_name} &bull; {selectedFactForModal.attribute}: <span style={{ color: '#2563EB' }}>{formatFactDisplay(selectedFactForModal).text}</span>
                </div>
              </div>

              <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>
                Extracted Document Citations ({evidenceList.length})
              </div>

              {loadingEvidence ? (
                <div className="py-8 text-center text-slate-500">Retrieving document coordinate grounding...</div>
              ) : evidenceList.length === 0 ? (
                <div className="py-8 text-center text-slate-500">No raw citations associated with this fact.</div>
              ) : (
                <div className="space-y-3">
                  {evidenceList.map((ev, idx) => (
                    <div key={idx} className="evidence-card" style={{ padding: '14px' }}>
                      <div className="flex items-center justify-between">
                        <span style={{ fontSize: '12px', fontWeight: 700, color: '#2563EB' }}>
                          Citation #{idx + 1}
                        </span>
                        <span className="trace-context-chip chip-highlight">
                          Page {ev.page_number || 1}
                        </span>
                      </div>
                      <blockquote className="evidence-quote-box" style={{ padding: '10px 14px', fontSize: '13px' }}>
                        “{ev.excerpt || ev.snippet || 'Filing excerpt text.'}”
                      </blockquote>
                      <div className="flex items-center justify-between text-xs text-slate-500 pt-2">
                        <span>Method: <strong>{ev.validation_method || 'Exact Match'}</strong></span>
                        {selectedFactForModal.document_id && (
                          <Link
                            to={`/viewer/${selectedFactForModal.document_id}?page=${ev.page_number || 1}&fact_id=${selectedFactForModal.id}`}
                            className="btn-trace-action"
                            style={{ padding: '3px 8px', fontSize: '11px' }}
                            onClick={() => setSelectedFactForModal(null)}
                          >
                            <span>View in PDF Viewer</span>
                            <IconExternalLink style={{ width: 11, height: 11 }} />
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn-trace-primary" onClick={() => setSelectedFactForModal(null)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

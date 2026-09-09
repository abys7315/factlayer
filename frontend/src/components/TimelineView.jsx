import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconClock,
  IconRefreshCw,
  IconSparkles,
  IconArrowRight,
  IconCheckCircle,
  IconLayers,
  IconNetwork,
  IconFileText,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function TimelineView() {
  const [supersedes, setSupersedes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRel, setSelectedRel] = useState(null);

  const fetchSupersedes = async () => {
    try {
      setLoading(true);
      const data = await api.getSupersedes({ limit: 100 });
      setSupersedes(data.items || []);
    } catch (err) {
      console.error('Failed to load supersedes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSupersedes();
  }, []);

  // Format fact values cleanly (human-readable string over raw DB float)
  const formatVal = (f) => {
    if (!f) return 'N/A';
    if (f.value_text && String(f.value_text).trim()) return f.value_text;
    if (f.object_value && String(f.object_value).trim()) return f.object_value;
    if (f.normalized_value !== null && f.normalized_value !== undefined) {
      if (typeof f.normalized_value === 'number') {
        return f.normalized_value.toLocaleString(undefined, { maximumFractionDigits: 3 });
      }
      return String(f.normalized_value);
    }
    return 'N/A';
  };

  return (
    <div className="timeline-view-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="crystal-type-badge badge-supersedes">
              Temporal Progression
            </span>
          </div>
          <h1 className="page-title mt-2">Fact History &amp; Supersession Timeline</h1>
          <p className="page-subtitle">
            Track how entity attributes evolve across reporting periods, fiscal years, and document revisions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/graph?preset=supersedes&from=timeline"
            className="crystal-btn-graph"
            title="Visualize supersessions and temporal evolution in the Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4" />
            <span>Explore in Graph</span>
          </Link>
          <button className="crystal-btn-trace" onClick={fetchSupersedes}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Timeline List */}
      <div className="space-y-5">
        {supersedes.length === 0 ? (
          <div className="card p-12 text-center text-muted bg-white rounded-2xl border border-slate-200">
            <IconClock className="w-10 h-10 text-amber-500 mx-auto mb-3" />
            <h3 className="text-base font-bold text-primary">No Superseded Facts Yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              Upload multiple revisions, quarterly filings, or annual reports to visualize attribute timelines over time.
            </p>
          </div>
        ) : (
          supersedes.map((rel) => {
            const conf = Math.round((rel.confidence_score || rel.confidence || 0.95) * 100);
            return (
              <div key={rel.id} className="crystal-rel-card type-supersedes">
                {/* Header */}
                <div className="crystal-card-header">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="crystal-type-badge badge-supersedes">
                      <IconClock style={{ width: 14, height: 14 }} />
                      <span>SUPERSEDES</span>
                    </span>
                    <span style={{ fontSize: '15px', fontWeight: 800, color: '#0F172A' }}>
                      {rel.fact_a?.entity_name || 'Entity'} &bull; <span style={{ color: '#D97706' }}>{rel.fact_a?.attribute || 'Attribute'}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="crystal-conf-badge">
                      {conf}% Confidence
                    </span>
                    <span className="crystal-engine-pill">
                      Engine: <strong>{rel.engine || 'Temporal Reasoner'}</strong>
                    </span>
                  </div>
                </div>

                {/* Visual Timeline Progression */}
                <div className="grid grid-cols-1 md:grid-cols-7 items-center gap-4">
                  {/* Prior State Box */}
                  <div className="md:col-span-3 crystal-fact-box">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag">Prior State</span>
                      {rel.fact_a?.validity_start && (
                        <span className="crystal-fact-period">{rel.fact_a.validity_start}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity">{rel.fact_a?.entity_name || 'N/A'}</div>
                    <div className="crystal-fact-pred">{rel.fact_a?.attribute || 'Metric'}</div>
                    <div className="crystal-fact-val-box source">
                      <div className="crystal-fact-val-text text-source">
                        {formatVal(rel.fact_a)}
                      </div>
                    </div>
                    {rel.fact_a?.document_filename && (
                      <span className="crystal-fact-doc" title={rel.fact_a.document_filename}>
                        <IconFileText style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
                        {rel.fact_a.document_filename}
                      </span>
                    )}
                  </div>

                  {/* Transition Arrow */}
                  <div className="md:col-span-1 flex flex-col items-center justify-center text-center py-2">
                    <div style={{
                      width: 42,
                      height: 42,
                      borderRadius: '50%',
                      background: '#FFFBEB',
                      border: '1.5px solid #FCD34D',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#D97706'
                    }}>
                      <IconArrowRight style={{ width: 20, height: 20 }} />
                    </div>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#D97706', marginTop: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Superseded
                    </span>
                  </div>

                  {/* Superseding State Box */}
                  <div className="md:col-span-3 crystal-fact-box crystal-fact-box-target">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag" style={{ color: '#D97706' }}>Superseding State</span>
                      {rel.fact_b?.validity_start && (
                        <span className="crystal-fact-period" style={{ background: '#FEF3C7', color: '#B45309' }}>{rel.fact_b.validity_start}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity">{rel.fact_b?.entity_name || 'N/A'}</div>
                    <div className="crystal-fact-pred">{rel.fact_b?.attribute || 'Metric'}</div>
                    <div className="crystal-fact-val-box target-supersedes">
                      <div className="crystal-fact-val-text text-supersedes">
                        {formatVal(rel.fact_b)}
                      </div>
                    </div>
                    {rel.fact_b?.document_filename && (
                      <span className="crystal-fact-doc" title={rel.fact_b.document_filename}>
                        <IconFileText style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
                        {rel.fact_b.document_filename}
                      </span>
                    )}
                  </div>
                </div>

                {/* Explanation */}
                <div className="crystal-rationale-box" style={{ borderLeftColor: '#D97706' }}>
                  <div className="crystal-rationale-label" style={{ color: '#B45309' }}>
                    <IconClock style={{ width: 14, height: 14 }} />
                    <span>Temporal Evolution Assessment</span>
                  </div>
                  <p className="crystal-rationale-text">
                    {rel.explanation || 'Target statement supersedes the prior statement based on subsequent fiscal reporting.'}
                  </p>
                </div>

                {/* Footer */}
                <div className="crystal-card-footer">
                  <span className="crystal-uuid-pill">
                    ID: {rel.id ? `${rel.id.substring(0, 8)}...` : 'N/A'}
                  </span>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/graph?relationship_id=${encodeURIComponent(rel.id)}&preset=supersedes&from=timeline`}
                      className="crystal-btn-trace"
                      title="Focus Knowledge Graph on this supersession pair"
                    >
                      <IconNetwork style={{ width: 14, height: 14, color: '#D97706' }} />
                      <span>View in Graph</span>
                    </Link>
                    <button
                      className="crystal-btn-trace"
                      onClick={() => setSelectedRel(rel)}
                    >
                      <IconSparkles style={{ width: 14, height: 14, color: '#2563EB' }} />
                      <span>Inspect Reasoning Trace</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {selectedRel && (
        <ReasoningTraceModal
          relationship={selectedRel}
          onClose={() => setSelectedRel(null)}
        />
      )}
    </div>
  );
}

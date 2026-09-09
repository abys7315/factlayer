import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconAlertTriangle,
  IconSparkles,
  IconShieldCheck,
  IconRefreshCw,
  IconEye,
  IconLayers,
  IconCheckCircle,
  IconNetwork,
  IconFileText,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function ContradictionView() {
  const [contradictions, setContradictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRel, setSelectedRel] = useState(null);
  const [liveSync, setLiveSync] = useState(true);
  const [lastSyncTime, setLastSyncTime] = useState('just now');

  const fetchContradictions = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const data = await api.getContradictions({ limit: 100 });
      setContradictions(data.items || []);
      setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err) {
      console.error('Failed to load contradictions:', err);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    fetchContradictions();
  }, []);

  // Real-Time Live Sync via SSE stream + smart fallback polling
  useEffect(() => {
    if (!liveSync) return;

    let es = null;
    let pollTimer = null;

    try {
      es = api.getEventSource();
      es.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.has_new_relationships) {
            fetchContradictions(true);
          }
        } catch (e) {
          // Keep stream alive
        }
      };
      es.onerror = () => {
        if (es) es.close();
      };
    } catch (err) {
      console.debug('SSE unavailable, using real-time polling fallback');
    }

    pollTimer = setInterval(() => {
      fetchContradictions(true);
    }, 4000);

    return () => {
      if (es) es.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [liveSync]);

  // Format fact values cleanly
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
    <div className="contradictions-view-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="crystal-type-badge badge-contradicts">
              Auditing Workspace
            </span>
            <div className="live-indicator cursor-pointer" onClick={() => setLiveSync(!liveSync)} title="Click to toggle Real-Time Live Sync">
              <span className={`live-dot ${liveSync ? '' : 'bg-gray-400'}`}></span>
              <span>{liveSync ? 'Real-Time Sync Active' : 'Live Sync Paused'}</span>
            </div>
          </div>
          <h1 className="page-title mt-2">Contradiction &amp; Discrepancy Center</h1>
          <p className="page-subtitle">
            Autonomous detection of factual collisions across reports, filings, revisions, and section claims.
            <span className="text-muted ml-2 text-xs font-mono">• Updated {lastSyncTime}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/graph?preset=contradictions&from=contradictions"
            className="crystal-btn-graph"
            title="Visualize all detected contradictions in the Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4" />
            <span>Explore in Graph</span>
          </Link>
          <button className="crystal-btn-trace" onClick={() => fetchContradictions(false)}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Analytical Callout: Why Context Matters */}
      <div className="p-4 rounded-xl bg-blue-50/80 border border-blue-200 flex items-start gap-3.5 shadow-xs">
        <div className="p-2 rounded-lg bg-blue-100 text-blue-600 shrink-0">
          <IconSparkles className="w-5 h-5" />
        </div>
        <div className="space-y-1 text-xs text-secondary leading-relaxed">
          <span className="font-bold text-primary block text-sm">
            Semantic Contradiction vs. Contextual Scope
          </span>
          Our reasoning engine automatically distinguishes true factual contradictions (e.g. conflicting figures for the identical period and organizational scope) from <strong>temporal updates</strong> (SUPERSEDES) or <strong>scoped sub-segment breakdowns</strong> (REFINES).
        </div>
      </div>

      {/* Contradictions List */}
      <div className="space-y-5">
        {contradictions.length === 0 ? (
          <div className="card p-12 text-center text-muted bg-white rounded-2xl border border-slate-200">
            <IconCheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
            <h3 className="text-base font-bold text-primary">No Active Contradictions Detected</h3>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              All extracted facts across your ingested documents are consistent, temporally superseded, or contextually scoped.
            </p>
          </div>
        ) : (
          contradictions.map((rel) => {
            const conf = Math.round((rel.confidence_score || rel.confidence || 0.95) * 100);
            return (
              <div key={rel.id} className="crystal-rel-card type-contradicts">
                {/* Header */}
                <div className="crystal-card-header">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="crystal-type-badge badge-contradicts">
                      <IconAlertTriangle style={{ width: 14, height: 14 }} />
                      <span>Factual Contradiction</span>
                    </span>
                    <span style={{ fontSize: '15px', fontWeight: 800, color: '#0F172A' }}>
                      {rel.fact_a?.entity_name || 'Entity'} &bull; <span style={{ color: '#BE123C' }}>{rel.fact_a?.attribute || 'Metric'}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="crystal-conf-badge">
                      {conf}% Confidence
                    </span>
                    <span className="crystal-engine-pill">
                      Engine: <strong>{rel.engine || 'Comparison Engine'}</strong>
                    </span>
                  </div>
                </div>

                {/* Side-by-Side Comparison */}
                <div className="crystal-comparison-box">
                  {/* Claim A */}
                  <div className="crystal-fact-box">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag">Claim A</span>
                      {rel.fact_a?.validity_start && (
                        <span className="crystal-fact-period">{rel.fact_a.validity_start}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity">{rel.fact_a?.entity_name || 'N/A'}</div>
                    <div className="crystal-fact-pred">{rel.fact_a?.attribute || 'Asserted Metric'}</div>
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

                  {/* Conflicting Claim B */}
                  <div className="crystal-fact-box crystal-fact-box-target">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag" style={{ color: '#BE123C' }}>Conflicting Claim B</span>
                      {rel.fact_b?.validity_start && (
                        <span className="crystal-fact-period" style={{ background: '#FFE4E6', color: '#BE123C' }}>{rel.fact_b.validity_start}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity">{rel.fact_b?.entity_name || 'N/A'}</div>
                    <div className="crystal-fact-pred">{rel.fact_b?.attribute || 'Asserted Metric'}</div>
                    <div className="crystal-fact-val-box target-contradicts">
                      <div className="crystal-fact-val-text text-contradicts">
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

                {/* Analytical Assessment */}
                <div className="crystal-rationale-box" style={{ borderLeftColor: '#E11D48' }}>
                  <div className="crystal-rationale-label" style={{ color: '#BE123C' }}>
                    <IconAlertTriangle style={{ width: 14, height: 14 }} />
                    <span>Reasoning Engine Assessment</span>
                  </div>
                  <p className="crystal-rationale-text">
                    {rel.explanation || 'Values differ significantly across documents for identical entity and attribute scope.'}
                  </p>
                </div>

                {/* Footer */}
                <div className="crystal-card-footer">
                  <span className="crystal-uuid-pill">
                    ID: {rel.id ? `${rel.id.substring(0, 8)}...` : 'N/A'}
                  </span>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/graph?relationship_id=${encodeURIComponent(rel.id)}&preset=contradictions&from=contradictions`}
                      className="crystal-btn-trace"
                      title="Focus Knowledge Graph on this contradiction cluster"
                    >
                      <IconNetwork style={{ width: 14, height: 14, color: '#BE123C' }} />
                      <span>View in Graph</span>
                    </Link>
                    <button
                      className="crystal-btn-trace"
                      onClick={() => setSelectedRel(rel)}
                    >
                      <IconSparkles style={{ width: 14, height: 14, color: '#2563EB' }} />
                      <span>Inspect Full Reasoning Trace</span>
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

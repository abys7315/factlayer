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

  return (
    <div className="contradictions-view-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="type-badge badge-contradicts">Auditing Workspace</span>
            <div className="live-indicator cursor-pointer" onClick={() => setLiveSync(!liveSync)} title="Click to toggle Real-Time Live Sync">
              <span className={`live-dot ${liveSync ? '' : 'bg-gray-400'}`}></span>
              <span>{liveSync ? 'Real-Time Sync Active' : 'Live Sync Paused'}</span>
            </div>
          </div>
          <h1 className="page-title mt-1">Contradiction & Discrepancy Center</h1>
          <p className="page-subtitle">
            Autonomous detection of factual collisions across reports, filings, revisions, and section claims.
            <span className="text-muted ml-2 text-xs font-mono">• Updated {lastSyncTime}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/graph?preset=contradictions&from=contradictions"
            className="btn btn-primary btn-sm flex items-center gap-1.5"
            title="Visualize all detected contradictions in the Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4" />
            <span>Explore in Graph</span>
          </Link>
          <button className="btn btn-ghost" onClick={() => fetchContradictions(false)}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Analytical Callout: Why Context Matters */}
      <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 flex items-start gap-4">
        <div className="p-2.5 rounded-lg bg-blue-100 text-blue-600 shrink-0">
          <IconSparkles className="w-5 h-5" />
        </div>
        <div className="space-y-1 text-xs text-secondary leading-relaxed">
          <span className="font-semibold text-primary block text-sm">
            Semantic Contradiction vs. Contextual Scope
          </span>
          Our reasoning engine automatically distinguishes true factual contradictions (e.g. conflicting revenue for the same FY2023 period and accounting GAAP scope) from <strong>temporal updates</strong> (SUPERSEDES) or <strong>scoped sub-segment breakdowns</strong> (REFINES).
        </div>
      </div>

      {/* Contradictions List */}
      <div className="space-y-4">
        {contradictions.length === 0 ? (
          <div className="card p-12 text-center text-muted">
            <IconCheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-primary">No Active Contradictions Detected</h3>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              All extracted facts across your ingested documents are consistent, temporally superseded, or contextually scoped.
            </p>
          </div>
        ) : (
          contradictions.map((rel) => (
            <div
              key={rel.id}
              className="card p-5 border-rose-200 hover:border-rose-400 transition-all space-y-4 shadow-sm"
            >
              {/* Conflict Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <IconAlertTriangle className="w-4 h-4 text-rose-500" />
                  <span className="font-semibold text-sm text-primary">
                    Conflict on: <span className="text-rose-600 font-mono">{rel.fact_a?.entity_name} &rarr; {rel.fact_a?.attribute}</span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="badge-pill bg-slate-100 text-slate-700 font-mono text-xs">
                    Confidence: {((rel.confidence_score || 0.95) * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs font-mono text-muted">
                    Engine: {rel.engine || 'llm_reasoner'}
                  </span>
                </div>
              </div>

              {/* Side-by-Side Comparison Box */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-muted uppercase font-bold">Claim A</span>
                    <span className="text-xs font-mono text-blue-600">{rel.fact_a?.validity_start || 'N/A'}</span>
                  </div>
                  <div className="text-sm font-semibold text-primary">
                    {rel.fact_a?.entity_name}
                  </div>
                  <div className="p-3 rounded-lg bg-emerald-50 font-mono text-sm text-emerald-700 font-bold border border-emerald-200">
                    {String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}
                  </div>
                  <div className="text-xs text-muted">
                    Raw snippet: <span className="text-secondary italic">"{rel.fact_a?.value_text}"</span>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-rose-600 uppercase font-bold">Conflicting Claim B</span>
                    <span className="text-xs font-mono text-blue-600">{rel.fact_b?.validity_start || 'N/A'}</span>
                  </div>
                  <div className="text-sm font-semibold text-primary">
                    {rel.fact_b?.entity_name}
                  </div>
                  <div className="p-3 rounded-lg bg-rose-100 font-mono text-sm text-rose-700 font-bold border border-rose-300">
                    {String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}
                  </div>
                  <div className="text-xs text-muted">
                    Raw snippet: <span className="text-secondary italic">"{rel.fact_b?.value_text}"</span>
                  </div>
                </div>
              </div>

              {/* Analytical Explanation */}
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-secondary leading-relaxed">
                <span className="font-semibold text-primary block mb-1">Reasoning Engine Assessment:</span>
                {rel.explanation}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <span className="text-[10px] font-mono text-muted">
                  Relationship UUID: {rel.id}
                </span>
                <div className="flex items-center gap-2">
                  <Link
                    to={`/graph?relationship_id=${encodeURIComponent(rel.id)}&preset=contradictions&from=contradictions`}
                    className="btn btn-secondary btn-sm flex items-center gap-1.5 text-rose-600 border-rose-200 hover:bg-rose-50 hover:border-rose-300"
                    title="Focus Knowledge Graph on this contradiction cluster"
                  >
                    <IconNetwork className="w-3.5 h-3.5 text-rose-500" />
                    <span>View in Graph</span>
                  </Link>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setSelectedRel(rel)}
                  >
                    <IconSparkles className="w-3.5 h-3.5 text-blue-600" />
                    <span>Inspect Full Reasoning Trace</span>
                  </button>
                </div>
              </div>
            </div>
          ))
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

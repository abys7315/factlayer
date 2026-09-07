import React, { useState, useEffect } from 'react';
import {
  IconAlertTriangle,
  IconSparkles,
  IconShieldCheck,
  IconRefreshCw,
  IconEye,
  IconLayers,
  IconCheckCircle,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function ContradictionView() {
  const [contradictions, setContradictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRel, setSelectedRel] = useState(null);

  const fetchContradictions = async () => {
    try {
      setLoading(true);
      const data = await api.getContradictions({ limit: 100 });
      setContradictions(data.items || []);
    } catch (err) {
      console.error('Failed to load contradictions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContradictions();
  }, []);

  return (
    <div className="contradictions-view-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="type-badge badge-contradicts">Auditing Workspace</span>
          </div>
          <h1 className="page-title mt-1">Contradiction & Discrepancy Center</h1>
          <p className="page-subtitle">
            Autonomous detection of factual collisions across reports, filings, revisions, and section claims.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={fetchContradictions}>
          <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Analytical Callout: Why Context Matters */}
      <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-start gap-4">
        <div className="p-2.5 rounded-lg bg-indigo-500/20 text-indigo-400 shrink-0">
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
          <div className="card glass-card p-12 text-center text-muted">
            <IconCheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-3 opacity-80" />
            <h3 className="text-base font-semibold text-primary">No Active Contradictions Detected</h3>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              All extracted facts across your ingested documents are consistent, temporally superseded, or contextually scoped.
            </p>
          </div>
        ) : (
          contradictions.map((rel) => (
            <div
              key={rel.id}
              className="card glass-card p-5 border-rose-900/40 hover:border-rose-700/60 transition-all space-y-4"
            >
              {/* Conflict Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <IconAlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="font-semibold text-sm text-primary">
                    Conflict on: <span className="text-rose-400 font-mono">{rel.fact_a?.entity_name} &rarr; {rel.fact_a?.attribute}</span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="confidence-pill font-mono text-xs">
                    Confidence: {((rel.confidence_score || 0.95) * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs font-mono text-muted">
                    Engine: {rel.engine || 'llm_reasoner'}
                  </span>
                </div>
              </div>

              {/* Side-by-Side Comparison Box */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-surface border border-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-muted uppercase">Claim A</span>
                    <span className="text-xs font-mono text-accent">{rel.fact_a?.validity_start || 'N/A'}</span>
                  </div>
                  <div className="text-sm font-semibold text-primary">
                    {rel.fact_a?.entity_name}
                  </div>
                  <div className="p-3 rounded bg-black/50 font-mono text-sm text-emerald-400 font-bold border border-emerald-950">
                    {String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}
                  </div>
                  <div className="text-xs text-muted">
                    Raw snippet: <span className="text-secondary italic">"{rel.fact_a?.value_text}"</span>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-surface border border-rose-900/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-rose-400 uppercase font-bold">Conflicting Claim B</span>
                    <span className="text-xs font-mono text-accent">{rel.fact_b?.validity_start || 'N/A'}</span>
                  </div>
                  <div className="text-sm font-semibold text-primary">
                    {rel.fact_b?.entity_name}
                  </div>
                  <div className="p-3 rounded bg-black/50 font-mono text-sm text-rose-400 font-bold border border-rose-950">
                    {String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}
                  </div>
                  <div className="text-xs text-muted">
                    Raw snippet: <span className="text-secondary italic">"{rel.fact_b?.value_text}"</span>
                  </div>
                </div>
              </div>

              {/* Analytical Explanation */}
              <div className="p-3.5 rounded-lg bg-surface-alt border border-border text-xs text-secondary leading-relaxed">
                <span className="font-semibold text-primary block mb-1">Reasoning Engine Assessment:</span>
                {rel.explanation}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] font-mono text-muted">
                  Relationship UUID: {rel.id}
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSelectedRel(rel)}
                >
                  <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Inspect Full Reasoning Trace</span>
                </button>
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

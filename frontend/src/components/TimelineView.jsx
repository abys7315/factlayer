import React, { useState, useEffect } from 'react';
import {
  IconClock,
  IconRefreshCw,
  IconSparkles,
  IconArrowRight,
  IconCheckCircle,
  IconLayers,
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

  return (
    <div className="timeline-view-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="type-badge badge-supersedes">Temporal Progression</span>
          </div>
          <h1 className="page-title mt-1">Fact History & Supersession Timeline</h1>
          <p className="page-subtitle">
            Track how entity attributes evolve across reporting periods, fiscal years, and document updates.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={fetchSupersedes}>
          <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Timeline List */}
      <div className="space-y-6">
        {supersedes.length === 0 ? (
          <div className="card glass-card p-12 text-center text-muted">
            <IconClock className="w-10 h-10 text-amber-400 mx-auto mb-3 opacity-80" />
            <h3 className="text-base font-semibold text-primary">No Superseded Facts Yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              Upload multiple revisions, quarterly filings, or annual reports to visualize attribute timelines over time.
            </p>
          </div>
        ) : (
          supersedes.map((rel, idx) => (
            <div key={rel.id} className="card glass-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <IconClock className="w-4 h-4 text-amber-400" />
                  <span className="font-semibold text-sm text-primary">
                    {rel.fact_a?.entity_name} &bull; <span className="text-accent">{rel.fact_a?.attribute}</span>
                  </span>
                </div>
                <span className="type-badge badge-supersedes">
                  SUPERSEDES
                </span>
              </div>

              {/* Visual Arrow Timeline Progression */}
              <div className="grid grid-cols-1 md:grid-cols-7 items-center gap-4">
                {/* Previous Value */}
                <div className="md:col-span-3 p-4 rounded-lg bg-surface border border-border space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted font-mono">
                    <span>PRIOR STATE</span>
                    <span>{rel.fact_a?.validity_start || 'Earlier'}</span>
                  </div>
                  <div className="text-sm font-semibold text-secondary">
                    {rel.fact_a?.entity_name}
                  </div>
                  <div className="p-2.5 rounded bg-black/40 font-mono text-sm text-muted">
                    {String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}
                  </div>
                  <span className="text-[10px] text-muted block italic">"{rel.fact_a?.value_text}"</span>
                </div>

                {/* Arrow */}
                <div className="md:col-span-1 flex flex-col items-center justify-center text-center">
                  <div className="p-2 rounded-full bg-amber-500/10 text-amber-400">
                    <IconArrowRight className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono text-muted mt-1">Updated</span>
                </div>

                {/* New Superseding Value */}
                <div className="md:col-span-3 p-4 rounded-lg bg-surface border border-amber-500/30 space-y-1 shadow-lg shadow-amber-500/5">
                  <div className="flex items-center justify-between text-xs text-amber-400 font-mono font-bold">
                    <span>SUPERSEDING STATE</span>
                    <span>{rel.fact_b?.validity_start || 'Latest'}</span>
                  </div>
                  <div className="text-sm font-semibold text-primary">
                    {rel.fact_b?.entity_name}
                  </div>
                  <div className="p-2.5 rounded bg-black/40 font-mono text-sm text-amber-400 font-bold">
                    {String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}
                  </div>
                  <span className="text-[10px] text-muted block italic">"{rel.fact_b?.value_text}"</span>
                </div>
              </div>

              {/* Explanation & Action */}
              <div className="p-3 rounded-lg bg-surface-alt text-xs text-secondary leading-relaxed">
                {rel.explanation}
              </div>

              <div className="flex justify-end pt-1">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSelectedRel(rel)}
                >
                  <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Inspect Reasoning Trace</span>
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

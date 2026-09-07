import React, { useState, useEffect } from 'react';
import {
  IconGitCompare,
  IconFilter,
  IconRefreshCw,
  IconSparkles,
  IconAlertTriangle,
  IconClock,
  IconCheckCircle,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function RelationshipExplorer() {
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState('');
  const [selectedRel, setSelectedRel] = useState(null);

  const fetchRelationships = async () => {
    try {
      setLoading(true);
      const params = { limit: 100 };
      if (selectedType) params.type = selectedType;
      const data = await api.listRelationships(params);
      setRelationships(data.items || []);
    } catch (err) {
      console.error('Failed to load relationships:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRelationships();
  }, [selectedType]);

  const relationshipTypes = [
    'CONTRADICTS',
    'SUPERSEDES',
    'SUPPORTS',
    'CORROBORATES',
    'REFINES',
    'EXTENDS',
  ];

  return (
    <div className="relationship-explorer-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Cross-Document Relationship Engine</h1>
          <p className="page-subtitle">
            Autonomous multi-hypothesis relationship graph linking facts via contradiction, supersession, support, and refinement.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={fetchRelationships}>
          <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Tabs / Pills */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          className={`filter-pill ${selectedType === '' ? 'filter-pill-active' : ''}`}
          onClick={() => setSelectedType('')}
        >
          All Types ({relationships.length})
        </button>
        {relationshipTypes.map((type) => (
          <button
            key={type}
            className={`filter-pill ${selectedType === type ? 'filter-pill-active' : ''}`}
            onClick={() => setSelectedType(type)}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Relationships Grid / Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {relationships.length === 0 ? (
          <div className="col-span-2 p-12 text-center text-muted card glass-card">
            <IconGitCompare className="w-8 h-8 text-indigo-400 mx-auto mb-2 opacity-60" />
            <p className="text-secondary font-medium">No relationships found matching criteria.</p>
            <p className="text-xs text-muted mt-1">Upload multiple documents to generate cross-document links.</p>
          </div>
        ) : (
          relationships.map((rel) => {
            const relType = rel.relationship_type || 'RELATES_TO';
            return (
              <div key={rel.id} className="card glass-card p-5 space-y-4 hover:border-indigo-500/50 transition-all">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`type-badge badge-${relType.toLowerCase()}`}>
                      {relType}
                    </span>
                    <span className="text-xs font-mono text-muted">
                      Engine: <span className="text-accent">{rel.engine || 'llm_reasoner'}</span>
                    </span>
                  </div>
                  <span className="confidence-pill font-mono">
                    {((rel.confidence_score || 0.9) * 100).toFixed(0)}% Conf
                  </span>
                </div>

                {/* Comparison Diff Box */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded bg-surface border border-border space-y-1">
                    <span className="text-[10px] font-mono uppercase text-muted block">Source Fact A</span>
                    <div className="text-xs font-semibold text-primary truncate">
                      {rel.fact_a?.entity_name}
                    </div>
                    <div className="text-[11px] font-mono text-secondary">
                      {rel.fact_a?.attribute}
                    </div>
                    <div className="p-1.5 rounded bg-black/40 font-mono text-xs text-emerald-400 truncate">
                      {String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}
                    </div>
                  </div>

                  <div className="p-3 rounded bg-surface border border-border space-y-1">
                    <span className="text-[10px] font-mono uppercase text-muted block">Target Fact B</span>
                    <div className="text-xs font-semibold text-primary truncate">
                      {rel.fact_b?.entity_name}
                    </div>
                    <div className="text-[11px] font-mono text-secondary">
                      {rel.fact_b?.attribute}
                    </div>
                    <div className={`p-1.5 rounded bg-black/40 font-mono text-xs truncate ${relType === 'CONTRADICTS' ? 'text-rose-400' : 'text-indigo-300'}`}>
                      {String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}
                    </div>
                  </div>
                </div>

                {/* Explanation */}
                <p className="text-xs text-secondary leading-relaxed line-clamp-2">
                  {rel.explanation}
                </p>

                {/* Footer Action */}
                <div className="pt-2 border-t border-border flex items-center justify-between">
                  <span className="text-[10px] text-muted font-mono">
                    ID: {rel.id?.substring(0, 8)}...
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setSelectedRel(rel)}
                  >
                    <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
                    <span>View Reasoning Trace</span>
                  </button>
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

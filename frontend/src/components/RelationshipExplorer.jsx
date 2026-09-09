import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconGitCompare,
  IconFilter,
  IconRefreshCw,
  IconSparkles,
  IconAlertTriangle,
  IconClock,
  IconCheckCircle,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function RelationshipExplorer() {
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState('');
  const [selectedRel, setSelectedRel] = useState(null);
  const [liveSync, setLiveSync] = useState(true);
  const [lastSyncTime, setLastSyncTime] = useState('just now');

  const fetchRelationships = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const params = { limit: 100 };
      if (selectedType) params.type = selectedType;
      const data = await api.listRelationships(params);
      setRelationships(data.items || []);
      setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err) {
      console.error('Failed to load relationships:', err);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRelationships();
  }, [selectedType]);

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
            fetchRelationships(true);
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

    // Smart background poll every 4s to guarantee real-time updates
    pollTimer = setInterval(() => {
      fetchRelationships(true);
    }, 4000);

    return () => {
      if (es) es.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [liveSync, selectedType]);

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
          <div className="flex items-center gap-3">
            <h1 className="page-title">Cross-Document Relationship Engine</h1>
            <div className="live-indicator cursor-pointer" onClick={() => setLiveSync(!liveSync)} title="Click to toggle Real-Time Live Sync">
              <span className={`live-dot ${liveSync ? '' : 'bg-gray-400'}`}></span>
              <span>{liveSync ? 'Real-Time Sync Active' : 'Live Sync Paused'}</span>
            </div>
          </div>
          <p className="page-subtitle mt-1">
            Autonomous multi-hypothesis relationship graph linking facts via contradiction, supersession, support, and refinement.
            <span className="text-muted ml-2 text-xs font-mono">• Updated {lastSyncTime}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/graph?preset=relationships${selectedType ? `&relationship_type=${encodeURIComponent(selectedType)}` : ''}&from=relationships`}
            className="btn btn-primary btn-sm flex items-center gap-1.5"
            title="Visualize these relationships in the Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4" />
            <span>Explore in Graph</span>
          </Link>
          <button className="btn btn-ghost" onClick={() => fetchRelationships(false)}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs / Pills */}
      <div className="crystal-filter-bar">
        <button
          type="button"
          className={`crystal-filter-pill ${selectedType === '' ? 'active' : ''}`}
          onClick={() => setSelectedType('')}
        >
          <span>All Types</span>
          <span style={{ opacity: 0.85, fontSize: '11px', fontFamily: 'monospace' }}>({relationships.length})</span>
        </button>
        {relationshipTypes.map((type) => {
          const typeLower = type.toLowerCase();
          const dotColor =
            type === 'CONTRADICTS' ? '#E11D48' :
            type === 'SUPERSEDES' ? '#D97706' :
            type === 'SUPPORTS' || type === 'CORROBORATES' ? '#16A34A' : '#2563EB';
          return (
            <button
              key={type}
              type="button"
              className={`crystal-filter-pill ${selectedType === type ? `active active-${typeLower}` : ''}`}
              onClick={() => setSelectedType(type)}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: selectedType === type ? '#FFFFFF' : dotColor }}></span>
              <span>{type}</span>
            </button>
          );
        })}
      </div>

      {/* Relationships Grid / Cards */}
      <div className="crystal-rel-grid">
        {relationships.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', padding: '48px 24px', textAlign: 'center', background: '#FFFFFF', borderRadius: '18px', border: '1.5px dashed #CBD5E1' }}>
            <IconGitCompare style={{ width: 36, height: 36, color: '#818cf8', margin: '0 auto 12px auto', opacity: 0.8 }} />
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0F172A', margin: '0 0 6px 0' }}>No relationships found</h3>
            <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>Upload multiple documents to generate cross-document links and conflicts.</p>
          </div>
        ) : (
          relationships.map((rel) => {
            const relType = rel.relationship_type || 'RELATES_TO';
            const relTypeLower = relType.toLowerCase();

            const formatVal = (fact) => {
              if (!fact) return 'N/A';
              if (fact.value_text) return fact.value_text;
              if (fact.object_value) return fact.object_value;
              if (fact.normalized_value !== undefined && fact.normalized_value !== null) {
                if (typeof fact.normalized_value === 'number') {
                  return fact.normalized_value.toLocaleString();
                }
                return String(fact.normalized_value);
              }
              return 'N/A';
            };

            return (
              <div key={rel.id} className={`crystal-rel-card type-${relTypeLower}`}>
                {/* Header */}
                <div className="crystal-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span className={`crystal-type-badge badge-${relTypeLower}`}>
                      {relType}
                    </span>
                    <span className="crystal-engine-pill">
                      Engine: <strong>{rel.engine || 'llm_reasoner'}</strong>
                    </span>
                  </div>
                  <span className="crystal-conf-badge">
                    <IconCheckCircle style={{ width: 14, height: 14 }} />
                    <span>{((rel.confidence_score || 0.9) * 100).toFixed(0)}% Conf</span>
                  </span>
                </div>

                {/* Comparison Diff Box */}
                <div className="crystal-comparison-box">
                  {/* Source Fact A */}
                  <div className="crystal-fact-box">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag">Source Fact A</span>
                      {rel.fact_a?.fiscal_year && (
                        <span className="crystal-fact-period">{rel.fact_a.fiscal_year}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity" title={rel.fact_a?.entity_name}>
                      {rel.fact_a?.entity_name || 'Entity'}
                    </div>
                    <div className="crystal-fact-pred">
                      <span>{rel.fact_a?.attribute || 'Attribute'}</span>
                    </div>
                    <div className="crystal-fact-val-box source">
                      <div className="crystal-fact-val-text text-source">
                        {formatVal(rel.fact_a)}
                        {rel.fact_a?.unit && (
                          <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748B', marginLeft: '5px' }}>
                            {rel.fact_a.unit}
                          </span>
                        )}
                      </div>
                    </div>
                    {rel.fact_a?.document_filename && (
                      <span className="crystal-fact-doc" title={rel.fact_a.document_filename}>
                        📄 {rel.fact_a.document_filename}
                      </span>
                    )}
                  </div>

                  {/* Target Fact B */}
                  <div className="crystal-fact-box crystal-fact-box-target">
                    <div className="crystal-fact-header">
                      <span className="crystal-fact-tag" style={{ color: relType === 'CONTRADICTS' ? '#E11D48' : relType === 'SUPERSEDES' ? '#B45309' : '#047857' }}>
                        Target Fact B
                      </span>
                      {rel.fact_b?.fiscal_year && (
                        <span className="crystal-fact-period">{rel.fact_b.fiscal_year}</span>
                      )}
                    </div>
                    <div className="crystal-fact-entity" title={rel.fact_b?.entity_name}>
                      {rel.fact_b?.entity_name || 'Entity'}
                    </div>
                    <div className="crystal-fact-pred">
                      <span>{rel.fact_b?.attribute || 'Attribute'}</span>
                    </div>
                    <div className={`crystal-fact-val-box target-${relTypeLower}`}>
                      <div className={`crystal-fact-val-text text-${relTypeLower}`}>
                        {formatVal(rel.fact_b)}
                        {rel.fact_b?.unit && (
                          <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748B', marginLeft: '5px' }}>
                            {rel.fact_b.unit}
                          </span>
                        )}
                      </div>
                    </div>
                    {rel.fact_b?.document_filename && (
                      <span className="crystal-fact-doc" title={rel.fact_b.document_filename}>
                        📄 {rel.fact_b.document_filename}
                      </span>
                    )}
                  </div>
                </div>

                {/* Analytical Explanation Rationale */}
                <div className="crystal-rationale-box">
                  <div className="crystal-rationale-label">
                    <IconSparkles style={{ width: 13, height: 13 }} />
                    <span>LLM Reasoning Rationale</span>
                  </div>
                  <p className="crystal-rationale-text">
                    {rel.explanation || 'Cross-document relationship inferred by knowledge reasoning engines.'}
                  </p>
                </div>

                {/* Footer Action */}
                <div className="crystal-card-footer">
                  <span className="crystal-uuid-pill">
                    ID: {rel.id?.substring(0, 8)}...
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Link
                      to={`/graph?relationship_id=${encodeURIComponent(rel.id)}&preset=relationships&from=relationships`}
                      className="crystal-btn-graph"
                      title="Focus Knowledge Graph on this relationship"
                    >
                      <IconNetwork style={{ width: 14, height: 14 }} />
                      <span>View in Graph</span>
                    </Link>
                    <button
                      type="button"
                      className="crystal-btn-trace"
                      onClick={() => setSelectedRel(rel)}
                    >
                      <IconSparkles style={{ width: 14, height: 14, color: '#6366F1' }} />
                      <span>View Reasoning Trace</span>
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

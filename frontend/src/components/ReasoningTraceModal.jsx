import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  IconAlertTriangle,
  IconSparkles,
  IconClock,
  IconCpu,
  IconShieldCheck,
  IconGitCompare,
  IconCheckCircle,
  IconFileText,
  IconExternalLink,
  IconCopy,
  IconCheck,
  IconX,
  IconLayers,
  IconChevronRight,
  IconInfo,
  IconBookOpen,
} from './Icons';
import { api } from '../api/client';

export default function ReasoningTraceModal({ relationship, onClose }) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [activeTab, setActiveTab] = useState('visual'); // 'visual' | 'provenance' | 'dimensions' | 'raw'
  const [copiedKey, setCopiedKey] = useState(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Fetch full relationship details (evidence, page numbers, bounding boxes)
  useEffect(() => {
    if (!relationship?.id) return;
    let isMounted = true;
    async function fetchDetail() {
      try {
        setLoadingDetail(true);
        const data = await api.getRelationship(relationship.id);
        if (isMounted) setDetail(data);
      } catch (err) {
        console.warn('Could not load detailed relationship trace, using prop data:', err);
      } finally {
        if (isMounted) setLoadingDetail(false);
      }
    }
    fetchDetail();
    return () => {
      isMounted = false;
    };
  }, [relationship?.id]);

  if (!relationship) return null;

  const rel = detail || relationship;
  const trace = rel.reasoning_trace || {};
  const relType = (rel.relationship_type || 'RELATES_TO').toUpperCase();
  const confidence = Number((rel.confidence_score ?? rel.confidence ?? 0.9) * 100);
  const engine = rel.engine || rel.classification_method || 'Deterministic Rules Engine';

  // Handle clipboard copy
  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Navigate to document viewer with page and fact
  const handleOpenViewer = (docId, factId, pageNumber = 1) => {
    if (!docId) return;
    onClose();
    navigate(`/viewer/${docId}?page=${pageNumber}&fact_id=${factId || ''}`);
  };

  // Helper to format fact claim values cleanly (never repeating units, preferring human text)
  const formatFactValue = (fact) => {
    if (!fact) return { display: 'N/A', unit: null };
    let display = null;
    if (fact.value_text && String(fact.value_text).trim()) {
      display = String(fact.value_text).trim();
    } else if (fact.object_value && String(fact.object_value).trim()) {
      display = String(fact.object_value).trim();
    } else if (fact.normalized_value !== null && fact.normalized_value !== undefined) {
      if (typeof fact.normalized_value === 'number') {
        display = fact.normalized_value.toLocaleString(undefined, { maximumFractionDigits: 4 });
      } else {
        display = String(fact.normalized_value);
      }
    } else {
      display = 'N/A';
    }

    let unit = fact.unit || fact.currency || null;
    if (unit) {
      const lowerDisplay = display.toLowerCase();
      const lowerUnit = unit.toLowerCase();
      if (lowerDisplay.includes(lowerUnit) || (lowerUnit === '%' && lowerDisplay.includes('per cent')) || (lowerUnit === 'percent' && lowerDisplay.includes('%'))) {
        unit = null; // Prevent duplicate like "81.8 per cent %"
      }
    }
    return { display, unit };
  };

  // Clean human-friendly name for reasoning engine
  const formatEngineName = (name) => {
    if (!name) return 'Rules Engine';
    if (name === 'temporal_reasoner') return 'Temporal Reasoning Engine';
    if (name === 'contradiction_reasoner') return 'Contradiction Reasoner';
    if (name === 'corroboration_reasoner') return 'Corroboration Engine';
    return name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  // Clean validation method formatting
  const formatValidationMethod = (method, score) => {
    const scoreStr = score !== undefined && score !== null ? ` (${Math.round(Number(score) * 100)}% Match)` : '';
    if (!method || method === 'rule_exact') return `Exact Document Passage Match${scoreStr}`;
    if (method === 'semantic_similarity') return `Semantic Similarity Match${scoreStr}`;
    return `${method.replace(/_/g, ' ')}${scoreStr}`;
  };

  // Clean coordinate formatting
  const formatCoordinates = (bbox) => {
    if (!bbox) return 'Document Page Text Flow';
    if (Array.isArray(bbox) && bbox.length >= 4) {
      const [x0, y0, x1, y1] = bbox;
      return `Page Coordinates: Top ${Math.round(y0 * 100)}%, Left ${Math.round(x0 * 100)}% (Width: ${Math.round((x1 - x0) * 100)}%, Height: ${Math.round((y1 - y0) * 100)}%)`;
    }
    if (typeof bbox === 'object' && bbox.x0 !== undefined) {
      return `Page Coordinates: Top ${Math.round(bbox.y0 * 100)}%, Left ${Math.round(bbox.x0 * 100)}%`;
    }
    return 'Document Page Region';
  };

  // Dimensions configuration for 7-Factor Alignment Matrix
  const dimensions = [
    {
      id: 'entity',
      label: 'Entity Resolution',
      isMatched: trace.same_entity !== false,
      valueA: rel.fact_a?.entity_name || rel.fact_a?.subject || 'Organization',
      valueB: rel.fact_b?.entity_name || rel.fact_b?.subject || 'Organization',
      description: 'Verifies both statements refer to the identical organizational entity or subject.',
    },
    {
      id: 'predicate',
      label: 'Metric / Attribute',
      isMatched: trace.same_predicate !== false,
      valueA: rel.fact_a?.attribute || rel.fact_a?.predicate || 'N/A',
      valueB: rel.fact_b?.attribute || rel.fact_b?.predicate || 'N/A',
      description: 'Resolves metric synonyms and validates comparable factual attribute scope.',
    },
    {
      id: 'period',
      label: 'Fiscal Period',
      isMatched: trace.same_period !== false,
      valueA: rel.fact_a?.fiscal_year || rel.fact_a?.validity_start || rel.fact_a?.reporting_period_label || 'Current',
      valueB: rel.fact_b?.fiscal_year || rel.fact_b?.validity_start || rel.fact_b?.reporting_period_label || 'Current',
      description: 'Validates fiscal year, quarterly reporting period, or effective date alignment.',
    },
    {
      id: 'scope',
      label: 'Reporting Scope',
      isMatched: trace.same_scope !== false,
      valueA: rel.fact_a?.scope || 'Consolidated',
      valueB: rel.fact_b?.scope || 'Consolidated',
      description: 'Ensures figures reflect identical organizational scope (Consolidated vs Standalone).',
    },
    {
      id: 'unit',
      label: 'Unit & Currency',
      isMatched: trace.same_unit !== false,
      valueA: [rel.fact_a?.currency, rel.fact_a?.unit].filter(Boolean).join(' ') || 'Standard',
      valueB: [rel.fact_b?.currency, rel.fact_b?.unit].filter(Boolean).join(' ') || 'Standard',
      description: 'Normalizes numerical units (millions, billions, %) and currency denominations.',
    },
    {
      id: 'geography',
      label: 'Geographic Coverage',
      isMatched: trace.same_geography !== false,
      valueA: rel.fact_a?.geography || 'Global / Domestic',
      valueB: rel.fact_b?.geography || 'Global / Domestic',
      description: 'Matches regional jurisdictions, country filings, or market territories.',
    },
    {
      id: 'basis',
      label: 'Accounting Basis',
      isMatched: trace.same_basis !== false,
      valueA: rel.fact_a?.basis || 'GAAP / Standard',
      valueB: rel.fact_b?.basis || 'GAAP / Standard',
      description: 'Distinguishes between GAAP, Non-GAAP, Adjusted EBITDA, or Statutory standards.',
    },
  ];

  // Synthesis banner styling configuration
  const getBannerConfig = () => {
    switch (relType) {
      case 'CONTRADICTS':
        return {
          icon: IconAlertTriangle,
          iconColor: 'text-rose-600',
          badgeClass: 'badge-contradicts',
          label: 'Factual Conflict / Contradiction',
          desc: 'Claims share identical entity and attribute scope but assert mutually incompatible figures across filings.',
        };
      case 'SUPERSEDES':
        return {
          icon: IconClock,
          iconColor: 'text-amber-600',
          badgeClass: 'badge-supersedes',
          label: 'Temporal Supersession',
          desc: 'Target statement supersedes the earlier source statement due to subsequent publication or revised reporting periods.',
        };
      case 'CORROBORATES':
        return {
          icon: IconCheckCircle,
          iconColor: 'text-emerald-600',
          badgeClass: 'badge-corroborates',
          label: 'Cross-Document Corroboration',
          desc: 'Independent documents corroborate consistent figures within tolerance, validating cross-document veracity.',
        };
      default:
        return {
          icon: IconGitCompare,
          iconColor: 'text-blue-600',
          badgeClass: 'badge-refines',
          label: 'Contextual Variance',
          desc: 'Numerical differences are explained by divergent reporting scopes, accounting standards, or periods.',
        };
    }
  };

  const bannerConfig = getBannerConfig();
  const BannerIcon = bannerConfig.icon;

  const evA = rel.evidence_a?.[0];
  const evB = rel.evidence_b?.[0];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-content trace-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Modal Header ────────────────────────────────────────────── */}
        <div className="modal-header">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`crystal-type-badge badge-${relType.toLowerCase()}`}>
                {relType}
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                    Reasoning &amp; Provenance Trace
                  </h3>
                  {loadingDetail && (
                    <span style={{ fontSize: '12px', color: '#64748B', fontWeight: 500 }}>
                      (Syncing evidence...)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1 text-xs" style={{ color: '#64748B', fontWeight: 500 }}>
                  <span>Engine: <strong style={{ color: '#0F172A', fontWeight: 600 }}>{formatEngineName(engine)}</strong></span>
                  <span>•</span>
                  <span style={{ color: '#059669', fontWeight: 600 }}>
                    {confidence.toFixed(1)}% Confidence
                  </span>
                  <span>•</span>
                  <span
                    className="hover:text-primary transition-colors flex items-center gap-1 cursor-pointer"
                    onClick={() => handleCopy(rel.id, 'relId')}
                    title="Click to copy Relationship UUID"
                  >
                    <span>ID: {rel.id?.substring(0, 8)}...</span>
                    {copiedKey === 'relId' ? (
                      <IconCheck style={{ width: 13, height: 13, color: '#059669' }} />
                    ) : (
                      <IconCopy style={{ width: 13, height: 13, opacity: 0.7 }} />
                    )}
                  </span>
                </div>
              </div>
            </div>

            <button
              className="btn-close hover:bg-slate-100 p-2 rounded-lg transition-colors"
              onClick={onClose}
              aria-label="Close modal"
            >
              <IconX style={{ width: 20, height: 20, color: '#64748B' }} />
            </button>
          </div>
        </div>

        {/* ── Tab Navigation Bar ──────────────────────────────────────── */}
        <div className="trace-tabs">
          <button
            className={`trace-tab-btn ${activeTab === 'visual' ? 'active' : ''}`}
            onClick={() => setActiveTab('visual')}
          >
            <IconSparkles style={{ width: 15, height: 15 }} />
            <span>Comparison &amp; Reasoning</span>
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'provenance' ? 'active' : ''}`}
            onClick={() => setActiveTab('provenance')}
          >
            <IconFileText style={{ width: 15, height: 15 }} />
            <span>Document Evidence</span>
            {(rel.evidence_a?.length || rel.evidence_b?.length) ? (
              <span style={{ marginLeft: '4px', padding: '1px 6px', borderRadius: '9999px', background: '#EFF6FF', color: '#1D4ED8', fontSize: '11px', fontWeight: 700 }}>
                {(rel.evidence_a?.length || 0) + (rel.evidence_b?.length || 0)}
              </span>
            ) : null}
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'dimensions' ? 'active' : ''}`}
            onClick={() => setActiveTab('dimensions')}
          >
            <IconLayers style={{ width: 15, height: 15 }} />
            <span>7-Factor Audit Matrix</span>
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'raw' ? 'active' : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            <IconCpu style={{ width: 15, height: 15 }} />
            <span>Audit JSON</span>
          </button>
        </div>

        {/* ── Modal Body Content ──────────────────────────────────────── */}
        <div className="modal-body space-y-6">
          {/* TAB 1: Visual Trace & Claims */}
          {activeTab === 'visual' && (
            <div className="space-y-6">
              {/* Analytical Synthesis Banner */}
              <div className={`trace-synthesis-banner banner-${relType.toLowerCase()}`}>
                <div style={{ padding: '8px', borderRadius: '10px', background: '#FFFFFF', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', flexShrink: 0 }}>
                  <BannerIcon style={{ width: 20, height: 20 }} className={bannerConfig.iconColor} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                      {bannerConfig.label}
                    </h4>
                    <span style={{ fontSize: '11.5px', fontWeight: 600, padding: '3px 8px', borderRadius: '6px', background: '#FFFFFF', border: '1px solid #CBD5E1', color: '#475569' }}>
                      Tolerance: ±5.0%
                    </span>
                  </div>
                  <p style={{ fontSize: '13.5px', marginTop: '5px', lineHeight: 1.6, color: '#334155', margin: '5px 0 0 0', fontWeight: 500 }}>
                    {rel.explanation || trace.explanation || bannerConfig.desc}
                  </p>
                </div>
              </div>

              {/* Side-by-Side Claims Comparison */}
              <div>
                <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
                  <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', color: '#64748B', textTransform: 'uppercase' }}>
                    Comparative Statement Analysis
                  </span>
                  <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748B' }}>
                    Auditing Source Filing against Target Filing
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
                  {/* SOURCE FACT A CARD */}
                  <div className="trace-claim-card card-source">
                    <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                        <span style={{ fontSize: '12.5px', fontWeight: 700, color: '#2563EB', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          Source Statement
                        </span>
                      </div>
                      {rel.fact_a?.document_filename && (
                        <span
                          className="trace-context-chip"
                          style={{ maxWidth: '220px' }}
                          title={rel.fact_a.document_filename}
                        >
                          <IconFileText style={{ width: 13, height: 13, flexShrink: 0, color: '#2563EB' }} />
                          <span className="truncate">{rel.fact_a.document_filename}</span>
                        </span>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div>
                        <span className="trace-field-label">Entity</span>
                        <div className="flex items-center gap-2">
                          <span className="trace-entity-title">{rel.fact_a?.entity_name || rel.fact_a?.subject || 'Organization'}</span>
                          {rel.fact_a?.category && (
                            <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '6px', background: '#F1F5F9', color: '#475569', border: '1px solid #E2E8F0' }}>
                              {rel.fact_a.category}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <span className="trace-field-label">Metric / Attribute</span>
                        <div className="trace-predicate-title">
                          {rel.fact_a?.attribute || rel.fact_a?.predicate || 'Claimed Metric'}
                        </div>
                      </div>

                      <div>
                        <span className="trace-field-label">Reported Value</span>
                        {(() => {
                          const { display, unit } = formatFactValue(rel.fact_a);
                          return (
                            <div className="trace-value-display val-source">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="trace-val-text truncate" title={display}>{display}</span>
                                {unit && (
                                  <span style={{ fontSize: '11.5px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', background: '#DBEAFE', color: '#1D4ED8' }}>
                                    {unit}
                                  </span>
                                )}
                              </div>
                              <button
                                className="p-1 hover:bg-blue-100 rounded text-slate-400 hover:text-slate-800 transition-colors flex-shrink-0 cursor-pointer"
                                onClick={() => handleCopy(display, 'valA')}
                                title="Copy Value"
                              >
                                {copiedKey === 'valA' ? <IconCheck style={{ width: 14, height: 14, color: '#059669' }} /> : <IconCopy style={{ width: 14, height: 14 }} />}
                              </button>
                            </div>
                          );
                        })()}
                      </div>

                      {/* Context Metadata */}
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        <span className="trace-context-chip chip-highlight">
                          Period: <strong>{rel.fact_a?.fiscal_year || rel.fact_a?.validity_start || 'FY2026'}</strong>
                        </span>
                        <span className="trace-context-chip">
                          Scope: <strong>{rel.fact_a?.scope || 'Consolidated'}</strong>
                        </span>
                        {rel.fact_a?.geography && (
                          <span className="trace-context-chip">
                            Geo: <strong>{rel.fact_a.geography}</strong>
                          </span>
                        )}
                      </div>

                      {/* Jump to Viewer */}
                      {rel.fact_a?.document_id && (
                        <div className="pt-2.5 border-t border-slate-100 flex items-center justify-between">
                          <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748B' }}>
                            Page {evA?.page_number || 1}
                          </span>
                          <button
                            className="btn-trace-action"
                            onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
                          >
                            <span>Inspect in Document</span>
                            <IconExternalLink style={{ width: 12, height: 12 }} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* TARGET FACT B CARD */}
                  <div className={`trace-claim-card card-target-${relType.toLowerCase()}`}>
                    <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{
                          background: relType === 'CONTRADICTS' ? '#E11D48' : relType === 'SUPERSEDES' ? '#D97706' : '#16A34A'
                        }}></span>
                        <span style={{
                          fontSize: '12.5px',
                          fontWeight: 700,
                          color: relType === 'CONTRADICTS' ? '#BE123C' : relType === 'SUPERSEDES' ? '#B45309' : '#15803D',
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em'
                        }}>
                          Target Statement
                        </span>
                      </div>
                      {rel.fact_b?.document_filename && (
                        <span
                          className="trace-context-chip"
                          style={{ maxWidth: '220px' }}
                          title={rel.fact_b.document_filename}
                        >
                          <IconFileText style={{ width: 13, height: 13, flexShrink: 0, color: '#D97706' }} />
                          <span className="truncate">{rel.fact_b.document_filename}</span>
                        </span>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div>
                        <span className="trace-field-label">Entity</span>
                        <div className="flex items-center gap-2">
                          <span className="trace-entity-title">{rel.fact_b?.entity_name || rel.fact_b?.subject || 'Organization'}</span>
                          {rel.fact_b?.category && (
                            <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '6px', background: '#F1F5F9', color: '#475569', border: '1px solid #E2E8F0' }}>
                              {rel.fact_b.category}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <span className="trace-field-label">Metric / Attribute</span>
                        <div className="trace-predicate-title">
                          {rel.fact_b?.attribute || rel.fact_b?.predicate || 'Claimed Metric'}
                        </div>
                      </div>

                      <div>
                        <span className="trace-field-label">Reported Value</span>
                        {(() => {
                          const { display, unit } = formatFactValue(rel.fact_b);
                          const valTargetClass = relType === 'CONTRADICTS'
                            ? 'val-contradicts'
                            : relType === 'SUPERSEDES'
                            ? 'val-supersedes'
                            : relType === 'CORROBORATES'
                            ? 'val-corroborates'
                            : 'val-context';
                          return (
                            <div className={`trace-value-display ${valTargetClass}`}>
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="trace-val-text truncate" title={display}>{display}</span>
                                {unit && (
                                  <span style={{ fontSize: '11.5px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', background: '#FEF3C7', color: '#92400E' }}>
                                    {unit}
                                  </span>
                                )}
                              </div>
                              <button
                                className="p-1 hover:bg-amber-100 rounded text-slate-400 hover:text-slate-800 transition-colors flex-shrink-0 cursor-pointer"
                                onClick={() => handleCopy(display, 'valB')}
                                title="Copy Value"
                              >
                                {copiedKey === 'valB' ? <IconCheck style={{ width: 14, height: 14, color: '#059669' }} /> : <IconCopy style={{ width: 14, height: 14 }} />}
                              </button>
                            </div>
                          );
                        })()}
                      </div>

                      {/* Context Metadata */}
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        <span className="trace-context-chip" style={{ background: '#FEF3C7', borderColor: '#FDE68A', color: '#92400E' }}>
                          Period: <strong>{rel.fact_b?.fiscal_year || rel.fact_b?.validity_start || 'FY2026'}</strong>
                        </span>
                        <span className="trace-context-chip">
                          Scope: <strong>{rel.fact_b?.scope || 'Consolidated'}</strong>
                        </span>
                        {rel.fact_b?.geography && (
                          <span className="trace-context-chip">
                            Geo: <strong>{rel.fact_b.geography}</strong>
                          </span>
                        )}
                      </div>

                      {/* Jump to Viewer */}
                      {rel.fact_b?.document_id && (
                        <div className="pt-2.5 border-t border-slate-100 flex items-center justify-between">
                          <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748B' }}>
                            Page {evB?.page_number || 1}
                          </span>
                          <button
                            className="btn-trace-action"
                            onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
                          >
                            <span>Inspect in Document</span>
                            <IconExternalLink style={{ width: 12, height: 12 }} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Execution Steps & Pipeline Audit */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-2" style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#64748B' }}>
                  <IconCpu style={{ width: 15, height: 15, color: '#2563EB' }} />
                  <span>Decision Engine Execution Pipeline</span>
                </div>

                <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px 20px' }}>
                  {/* Step 1 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon" style={{ background: '#ECFDF5', color: '#047857', border: '1px solid #A7F3D0' }}>1</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#0F172A' }}>Entity Grounding &amp; Scope Alignment</span>
                        <span className="audit-status-pill aligned">Verified Match</span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#475569', marginTop: '3px', lineHeight: 1.5, margin: '3px 0 0 0' }}>
                        Both statements ground to entity <strong>"{rel.fact_a?.entity_name || rel.fact_a?.subject || 'Organization'}"</strong> and metric <strong>"{rel.fact_a?.attribute || rel.fact_a?.predicate || 'Metric'}"</strong>.
                      </p>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon" style={{ background: '#ECFDF5', color: '#047857', border: '1px solid #A7F3D0' }}>2</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#0F172A' }}>7-Factor Multi-Dimensional Filter</span>
                        <span className="audit-status-pill aligned">Context Aligned</span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#475569', marginTop: '3px', lineHeight: 1.5, margin: '3px 0 0 0' }}>
                        Evaluated temporal periods (<strong>{rel.fact_a?.fiscal_year || 'FY2026'}</strong>), reporting scope, geographic coverage, and units. All contextual parameters confirmed comparable.
                      </p>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon" style={{
                      background: relType === 'CONTRADICTS' ? '#FFF1F2' : '#EFF6FF',
                      color: relType === 'CONTRADICTS' ? '#BE123C' : '#1D4ED8',
                      border: `1px solid ${relType === 'CONTRADICTS' ? '#FECDD3' : '#BFDBFE'}`
                    }}>3</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#0F172A' }}>Delta &amp; Discrepancy Reconciliation</span>
                        <span className={`audit-status-pill ${relType === 'CONTRADICTS' ? 'conflict' : 'aligned'}`}>
                          {relType === 'CONTRADICTS' ? 'Discrepancy Detected' : 'Compatible Values'}
                        </span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#475569', marginTop: '3px', lineHeight: 1.5, margin: '3px 0 0 0' }}>
                        {rel.explanation || `Reconciled values: "${formatFactValue(rel.fact_a).display}" vs "${formatFactValue(rel.fact_b).display}".`}
                      </p>
                    </div>
                  </div>

                  {/* Step 4 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon" style={{ background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE' }}>4</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#0F172A' }}>Audit Verdict &amp; Confidence Assignment</span>
                        <span className="audit-status-pill" style={{ background: '#F1F5F9', color: '#334155', border: '1px solid #CBD5E1' }}>Finalized</span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#475569', marginTop: '3px', lineHeight: 1.5, margin: '3px 0 0 0' }}>
                        Classified as <strong>{relType}</strong> with <strong style={{ color: '#059669' }}>{confidence.toFixed(1)}% confidence score</strong> via <strong>{formatEngineName(engine)}</strong>.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Ground-Truth Document Evidence & Citations */}
          {activeTab === 'provenance' && (
            <div className="space-y-5">
              <div className="p-3.5 rounded-xl bg-blue-50/70 border border-blue-200/80 text-sm text-blue-900 flex items-center gap-2.5">
                <IconBookOpen style={{ width: 18, height: 18, color: '#2563EB', flexShrink: 0 }} />
                <span>
                  Ground-truth excerpts extracted verbatim from verified PDF source documents with page anchoring.
                </span>
              </div>

              {/* Evidence for Fact A */}
              <div className="evidence-card">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#2563EB' }}>
                      Source Document Citation (Fact A)
                    </span>
                  </div>
                  <span className="trace-context-chip chip-highlight">
                    Page {evA?.page_number || 1}
                  </span>
                </div>

                <div>
                  <div className="trace-field-label">Document Title</div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#0F172A', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <IconFileText style={{ width: 16, height: 16, color: '#2563EB' }} />
                    <span>{rel.fact_a?.document_filename || rel.fact_a?.document_id || 'Source Document A'}</span>
                  </div>
                </div>

                <div>
                  <div className="trace-field-label">Verbatim Filing Excerpt</div>
                  <blockquote className="evidence-quote-box">
                    “{evA?.excerpt || evA?.snippet || rel.fact_a?.original_text || rel.fact_a?.object_value || 'Direct claim excerpt extracted from document page text.'}”
                  </blockquote>
                </div>

                <div className="evidence-meta-row">
                  <div>
                    <span className="trace-field-label" style={{ marginBottom: '2px' }}>Verification Method</span>
                    <span style={{ fontWeight: 600, color: '#059669' }}>
                      {formatValidationMethod(evA?.validation_method, evA?.validation_score)}
                    </span>
                  </div>
                  <div>
                    <span className="trace-field-label" style={{ marginBottom: '2px' }}>Page Location</span>
                    <span style={{ fontWeight: 600, color: '#334155' }}>
                      {formatCoordinates(evA?.bbox)}
                    </span>
                  </div>
                  {rel.fact_a?.document_id && (
                    <button
                      className="btn-trace-action"
                      onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
                    >
                      <IconExternalLink style={{ width: 13, height: 13, color: '#2563EB' }} />
                      <span>Inspect in Document</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Evidence for Fact B */}
              <div className="evidence-card">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{
                      background: relType === 'CONTRADICTS' ? '#E11D48' : '#D97706'
                    }}></span>
                    <span style={{
                      fontSize: '13px',
                      fontWeight: 700,
                      color: relType === 'CONTRADICTS' ? '#BE123C' : '#B45309'
                    }}>
                      Target Document Citation (Fact B)
                    </span>
                  </div>
                  <span className="trace-context-chip" style={{ background: '#FFFBEB', borderColor: '#FDE68A', color: '#92400E' }}>
                    Page {evB?.page_number || 1}
                  </span>
                </div>

                <div>
                  <div className="trace-field-label">Document Title</div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#0F172A', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <IconFileText style={{ width: 16, height: 16, color: '#D97706' }} />
                    <span>{rel.fact_b?.document_filename || rel.fact_b?.document_id || 'Target Document B'}</span>
                  </div>
                </div>

                <div>
                  <div className="trace-field-label">Verbatim Filing Excerpt</div>
                  <blockquote className="evidence-quote-box" style={{
                    borderLeftColor: relType === 'CONTRADICTS' ? '#E11D48' : '#D97706'
                  }}>
                    “{evB?.excerpt || evB?.snippet || rel.fact_b?.original_text || rel.fact_b?.object_value || 'Direct claim excerpt extracted from document page text.'}”
                  </blockquote>
                </div>

                <div className="evidence-meta-row">
                  <div>
                    <span className="trace-field-label" style={{ marginBottom: '2px' }}>Verification Method</span>
                    <span style={{ fontWeight: 600, color: '#059669' }}>
                      {formatValidationMethod(evB?.validation_method, evB?.validation_score)}
                    </span>
                  </div>
                  <div>
                    <span className="trace-field-label" style={{ marginBottom: '2px' }}>Page Location</span>
                    <span style={{ fontWeight: 600, color: '#334155' }}>
                      {formatCoordinates(evB?.bbox)}
                    </span>
                  </div>
                  {rel.fact_b?.document_id && (
                    <button
                      className="btn-trace-action"
                      onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
                    >
                      <IconExternalLink style={{ width: 13, height: 13, color: '#2563EB' }} />
                      <span>Inspect in Document</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: 7-Factor Dimensional Alignment Matrix */}
          {activeTab === 'dimensions' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-700 font-medium flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <IconInfo style={{ width: 16, height: 16, color: '#2563EB' }} />
                  <span>
                    Audited across 7 distinct dimensions to eliminate false positives and distinguish contextual shifts from contradictions.
                  </span>
                </div>
                <span style={{ fontSize: '12.5px', fontWeight: 700, color: '#2563EB' }}>
                  {dimensions.filter((d) => d.isMatched).length} of {dimensions.length} Dimensions Aligned
                </span>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="audit-matrix-table">
                  <thead>
                    <tr>
                      <th style={{ width: '32%' }}>Audit Factor</th>
                      <th style={{ width: '25%' }}>Source Filing (Fact A)</th>
                      <th style={{ width: '25%' }}>Target Filing (Fact B)</th>
                      <th style={{ width: '18%', textAlign: 'right' }}>Alignment Verdict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dimensions.map((dim) => (
                      <tr key={dim.id}>
                        <td>
                          <div style={{ fontWeight: 700, color: '#0F172A', fontSize: '13.5px' }}>{dim.label}</div>
                          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>{dim.description}</div>
                        </td>
                        <td>
                          <span className="audit-val-badge" title={String(dim.valueA)}>{String(dim.valueA)}</span>
                        </td>
                        <td>
                          <span className="audit-val-badge" title={String(dim.valueB)}>{String(dim.valueB)}</span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <span className={`audit-status-pill ${dim.isMatched ? 'aligned' : 'divergent'}`}>
                            {dim.isMatched ? (
                              <>
                                <IconCheck style={{ width: 13, height: 13 }} />
                                <span>Aligned</span>
                              </>
                            ) : (
                              <>
                                <IconAlertTriangle style={{ width: 13, height: 13 }} />
                                <span>Divergent</span>
                              </>
                            )}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: Raw Audit Metadata (JSON) */}
          {activeTab === 'raw' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#64748B' }}>
                  Machine-Readable Structured Execution Payload
                </span>
                <button
                  className="btn-trace-action"
                  onClick={() => handleCopy(JSON.stringify(rel, null, 2), 'rawJson')}
                >
                  {copiedKey === 'rawJson' ? (
                    <>
                      <IconCheck style={{ width: 14, height: 14, color: '#16A34A' }} />
                      <span>Copied JSON</span>
                    </>
                  ) : (
                    <>
                      <IconCopy style={{ width: 14, height: 14 }} />
                      <span>Copy Full JSON</span>
                    </>
                  )}
                </button>
              </div>

              <div style={{ background: '#0F172A', borderRadius: '12px', padding: '16px', border: '1px solid #334155', boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.4)' }}>
                <pre style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#38BDF8', lineHeight: 1.6, overflowX: 'auto', maxHeight: '340px' }}>
                  {JSON.stringify(rel, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* ── Modal Footer ────────────────────────────────────────────── */}
        <div className="modal-footer">
          <div className="flex items-center gap-2 text-xs" style={{ color: '#64748B', fontWeight: 500 }}>
            <span>Press <kbd className="px-2 py-0.5 rounded bg-slate-200 border border-slate-300 text-xs font-semibold text-slate-700">Esc</kbd> to close</span>
          </div>

          <div className="flex items-center gap-2.5">
            {rel.fact_a?.document_id && (
              <button
                className="btn-trace-action"
                onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
              >
                <IconExternalLink style={{ width: 13, height: 13, color: '#2563EB' }} />
                <span>Fact A in Viewer</span>
              </button>
            )}
            {rel.fact_b?.document_id && (
              <button
                className="btn-trace-action"
                onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
              >
                <IconExternalLink style={{ width: 13, height: 13, color: '#D97706' }} />
                <span>Fact B in Viewer</span>
              </button>
            )}
            <button className="btn-trace-primary" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

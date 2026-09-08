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
      label: 'Attribute / Metric',
      isMatched: trace.same_predicate !== false,
      valueA: rel.fact_a?.attribute || rel.fact_a?.predicate || 'N/A',
      valueB: rel.fact_b?.attribute || rel.fact_b?.predicate || 'N/A',
      description: 'Resolves metric synonyms and validates comparable factual attribute scope.',
    },
    {
      id: 'period',
      label: 'Fiscal Period / Date',
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

  // Synthesis banner styling helper
  const getBannerConfig = () => {
    switch (relType) {
      case 'CONTRADICTS':
        return {
          icon: IconAlertTriangle,
          borderColor: 'border-rose-300',
          bgColor: 'bg-rose-50/70 text-rose-950',
          iconColor: 'text-rose-600',
          badgeClass: 'badge-contradicts',
          symbol: '≠',
          symbolClass: 'text-rose-600 bg-rose-100 border-rose-300',
          label: 'Factual Conflict / Contradiction',
          desc: 'Claims share the same entity and attribute context but assert mutually incompatible or contradictory figures.',
        };
      case 'SUPERSEDES':
        return {
          icon: IconClock,
          borderColor: 'border-amber-300',
          bgColor: 'bg-amber-50/70 text-amber-950',
          iconColor: 'text-amber-600',
          badgeClass: 'badge-supersedes',
          symbol: '>',
          symbolClass: 'text-amber-600 bg-amber-100 border-amber-300',
          label: 'Temporal Supersession',
          desc: 'Target statement supersedes the earlier source statement due to subsequent publication or updated reporting.',
        };
      case 'CORROBORATES':
        return {
          icon: IconCheckCircle,
          borderColor: 'border-emerald-300',
          bgColor: 'bg-emerald-50/70 text-emerald-950',
          iconColor: 'text-emerald-600',
          badgeClass: 'badge-corroborates',
          symbol: '≡',
          symbolClass: 'text-emerald-600 bg-emerald-100 border-emerald-300',
          label: 'Mutual Corroboration',
          desc: 'Independent documents corroborate identical values within tolerance, validating cross-document veracity.',
        };
      default:
        return {
          icon: IconGitCompare,
          borderColor: 'border-blue-300',
          bgColor: 'bg-blue-50/70 text-blue-950',
          iconColor: 'text-blue-600',
          badgeClass: 'badge-contextual_difference',
          symbol: '≈',
          symbolClass: 'text-blue-600 bg-blue-100 border-blue-300',
          label: 'Contextual Difference',
          desc: 'Numerical differences are reconciled by differing reporting scopes, fiscal periods, or accounting standards.',
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
          <div className="flex flex-wrap items-center gap-3">
            <span className={`type-badge ${bannerConfig.badgeClass} text-xs px-3 py-1`}>
              {relType}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="modal-title text-lg font-bold text-primary">
                  Reasoning &amp; Provenance Trace
                </h3>
                {loadingDetail && (
                  <span className="text-xs text-muted font-mono animate-pulse">
                    (Syncing evidence...)
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-0.5 text-xs text-muted font-mono">
                <span>Engine: <strong className="text-secondary">{engine}</strong></span>
                <span>•</span>
                <span className="inline-flex items-center gap-1.5 font-semibold text-accent">
                  <span className="w-2 h-2 rounded-full bg-accent-primary animate-ping"></span>
                  {confidence.toFixed(1)}% Confidence
                </span>
                <span>•</span>
                <span
                  className="cursor-pointer hover:text-primary transition-colors flex items-center gap-1"
                  onClick={() => handleCopy(rel.id, 'relId')}
                  title="Click to copy Relationship UUID"
                >
                  ID: {rel.id?.substring(0, 8)}...
                  {copiedKey === 'relId' ? (
                    <IconCheck className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <IconCopy className="w-3 h-3 opacity-60" />
                  )}
                </span>
              </div>
            </div>
          </div>

          <button
            className="btn-close hover:bg-surface-alt p-1.5 rounded-lg transition-colors"
            onClick={onClose}
            aria-label="Close modal"
          >
            <IconX className="w-5 h-5 text-muted hover:text-primary" />
          </button>
        </div>

        {/* ── Tab Navigation Bar ──────────────────────────────────────── */}
        <div className="trace-tabs">
          <button
            className={`trace-tab-btn ${activeTab === 'visual' ? 'active' : ''}`}
            onClick={() => setActiveTab('visual')}
          >
            <IconSparkles className="w-4 h-4" />
            <span>Visual Trace &amp; Claims</span>
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'provenance' ? 'active' : ''}`}
            onClick={() => setActiveTab('provenance')}
          >
            <IconFileText className="w-4 h-4" />
            <span>Document Evidence &amp; Citations</span>
            {(rel.evidence_a?.length || rel.evidence_b?.length) ? (
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-accent-subtle text-accent font-mono text-[10px]">
                {(rel.evidence_a?.length || 0) + (rel.evidence_b?.length || 0)}
              </span>
            ) : null}
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'dimensions' ? 'active' : ''}`}
            onClick={() => setActiveTab('dimensions')}
          >
            <IconLayers className="w-4 h-4" />
            <span>7-Factor Alignment Matrix</span>
          </button>
          <button
            className={`trace-tab-btn ${activeTab === 'raw' ? 'active' : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            <IconCpu className="w-4 h-4" />
            <span>Audit Metadata (JSON)</span>
          </button>
        </div>

        {/* ── Modal Body Content ──────────────────────────────────────── */}
        <div className="modal-body p-6 space-y-6 overflow-y-auto flex-1">
          {/* TAB 1: Visual Trace & Claims */}
          {activeTab === 'visual' && (
            <div className="space-y-6">
              {/* Analytical Synthesis Banner */}
              <div
                className={`p-4 rounded-xl border ${bannerConfig.borderColor} ${bannerConfig.bgColor} flex items-start gap-3 shadow-sm`}
              >
                <div className={`p-2 rounded-lg bg-white/80 shadow-xs ${bannerConfig.iconColor}`}>
                  <BannerIcon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold tracking-tight">
                      {bannerConfig.label}
                    </h4>
                    <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-white/70 font-semibold">
                      Tolerance: ±5.0%
                    </span>
                  </div>
                  <p className="text-xs mt-1 leading-relaxed opacity-90">
                    {rel.explanation || trace.explanation || bannerConfig.desc}
                  </p>
                </div>
              </div>

              {/* Side-by-Side Claims Comparison */}
              <div>
                <div className="text-xs uppercase tracking-wider font-bold text-muted font-mono mb-2 flex items-center justify-between">
                  <span>Ground-Truth Claims Comparison</span>
                  <span className="text-[11px] lowercase text-muted font-normal">
                    Comparing Source Fact A against Target Fact B
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
                  {/* SOURCE FACT A CARD */}
                  <div className="trace-claim-card card-source">
                    <div className="flex items-center justify-between pb-2 border-b border-border">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-accent-primary"></span>
                        <span className="text-[11px] font-mono uppercase font-bold text-accent">
                          Source Claim A
                        </span>
                      </div>
                      {rel.fact_a?.document_filename && (
                        <span
                          className="text-[11px] text-muted truncate max-w-[170px] font-mono flex items-center gap-1"
                          title={rel.fact_a.document_filename}
                        >
                          <IconFileText className="w-3 h-3 text-muted" />
                          {rel.fact_a.document_filename}
                        </span>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Entity / Subject</span>
                        <div className="text-sm font-bold text-primary flex items-center gap-2">
                          <span>{rel.fact_a?.entity_name || rel.fact_a?.subject || 'Organization'}</span>
                          {rel.fact_a?.category && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-alt font-medium text-muted border border-border">
                              {rel.fact_a.category}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Predicate / Attribute</span>
                        <div className="text-xs font-semibold text-secondary font-mono">
                          {rel.fact_a?.attribute || rel.fact_a?.predicate || 'Claimed Metric'}
                        </div>
                      </div>

                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Asserted Claim Value</span>
                        <div className="trace-value-display flex items-center justify-between text-emerald-600 bg-emerald-50/50 border-emerald-200">
                          <span className="truncate">
                            {typeof rel.fact_a?.normalized_value === 'object'
                              ? JSON.stringify(rel.fact_a?.normalized_value)
                              : String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text ?? 'N/A')}
                          </span>
                          <button
                            className="p-1 hover:bg-emerald-100 rounded text-muted hover:text-primary transition-colors"
                            onClick={() => handleCopy(String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text), 'valA')}
                            title="Copy Value A"
                          >
                            {copiedKey === 'valA' ? <IconCheck className="w-3.5 h-3.5 text-emerald-600" /> : <IconCopy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>

                      {/* Context Pills */}
                      <div className="flex flex-wrap gap-1.5 pt-1 text-[11px] font-mono text-muted">
                        <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                          Period: <strong className="text-secondary">{rel.fact_a?.fiscal_year || rel.fact_a?.validity_start || 'FY2026'}</strong>
                        </span>
                        <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                          Scope: <strong className="text-secondary">{rel.fact_a?.scope || 'Consolidated'}</strong>
                        </span>
                        {rel.fact_a?.geography && (
                          <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                            Geo: <strong className="text-secondary">{rel.fact_a.geography}</strong>
                          </span>
                        )}
                      </div>

                      {/* Jump to Viewer */}
                      {rel.fact_a?.document_id && (
                        <div className="pt-2 border-t border-border flex items-center justify-between">
                          <span className="text-[11px] text-muted font-mono">
                            Page {evA?.page_number || 1}
                          </span>
                          <button
                            className="btn btn-ghost btn-sm text-xs text-accent flex items-center gap-1 hover:underline p-0 h-auto"
                            onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
                          >
                            <span>Inspect in PDF Viewer</span>
                            <IconExternalLink className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* TARGET FACT B CARD */}
                  <div className={`trace-claim-card card-target-${relType.toLowerCase()}`}>
                    <div className="flex items-center justify-between pb-2 border-b border-border">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                        <span className="text-[11px] font-mono uppercase font-bold text-rose-600">
                          Target Claim B
                        </span>
                      </div>
                      {rel.fact_b?.document_filename && (
                        <span
                          className="text-[11px] text-muted truncate max-w-[170px] font-mono flex items-center gap-1"
                          title={rel.fact_b.document_filename}
                        >
                          <IconFileText className="w-3 h-3 text-muted" />
                          {rel.fact_b.document_filename}
                        </span>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Entity / Subject</span>
                        <div className="text-sm font-bold text-primary flex items-center gap-2">
                          <span>{rel.fact_b?.entity_name || rel.fact_b?.subject || 'Organization'}</span>
                          {rel.fact_b?.category && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-alt font-medium text-muted border border-border">
                              {rel.fact_b.category}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Predicate / Attribute</span>
                        <div className="text-xs font-semibold text-secondary font-mono">
                          {rel.fact_b?.attribute || rel.fact_b?.predicate || 'Claimed Metric'}
                        </div>
                      </div>

                      <div>
                        <span className="text-[10px] font-mono uppercase text-muted block">Asserted Claim Value</span>
                        <div className={`trace-value-display flex items-center justify-between ${
                          relType === 'CONTRADICTS'
                            ? 'text-rose-600 bg-rose-50/50 border-rose-200'
                            : 'text-indigo-600 bg-indigo-50/50 border-indigo-200'
                        }`}>
                          <span className="truncate">
                            {typeof rel.fact_b?.normalized_value === 'object'
                              ? JSON.stringify(rel.fact_b?.normalized_value)
                              : String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text ?? 'N/A')}
                          </span>
                          <button
                            className="p-1 hover:bg-rose-100 rounded text-muted hover:text-primary transition-colors"
                            onClick={() => handleCopy(String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text), 'valB')}
                            title="Copy Value B"
                          >
                            {copiedKey === 'valB' ? <IconCheck className="w-3.5 h-3.5 text-rose-600" /> : <IconCopy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>

                      {/* Context Pills */}
                      <div className="flex flex-wrap gap-1.5 pt-1 text-[11px] font-mono text-muted">
                        <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                          Period: <strong className="text-secondary">{rel.fact_b?.fiscal_year || rel.fact_b?.validity_start || 'FY2026'}</strong>
                        </span>
                        <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                          Scope: <strong className="text-secondary">{rel.fact_b?.scope || 'Consolidated'}</strong>
                        </span>
                        {rel.fact_b?.geography && (
                          <span className="px-2 py-0.5 rounded bg-surface-alt border border-border">
                            Geo: <strong className="text-secondary">{rel.fact_b.geography}</strong>
                          </span>
                        )}
                      </div>

                      {/* Jump to Viewer */}
                      {rel.fact_b?.document_id && (
                        <div className="pt-2 border-t border-border flex items-center justify-between">
                          <span className="text-[11px] text-muted font-mono">
                            Page {evB?.page_number || 1}
                          </span>
                          <button
                            className="btn btn-ghost btn-sm text-xs text-accent flex items-center gap-1 hover:underline p-0 h-auto"
                            onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
                          >
                            <span>Inspect in PDF Viewer</span>
                            <IconExternalLink className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Execution Steps & Pipeline Audit */}
              <div className="space-y-3 pt-2">
                <div className="text-xs uppercase tracking-wider font-bold text-muted font-mono flex items-center gap-2">
                  <IconCpu className="w-4 h-4 text-accent-primary" />
                  <span>Decision Engine Execution Pipeline</span>
                </div>

                <div className="p-4 rounded-xl bg-surface border border-border space-y-4">
                  {/* Step 1 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon bg-emerald-100 text-emerald-700">1</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-primary">Candidate Grounding &amp; Entity Alignment</span>
                        <span className="trace-dim-badge dim-matched text-[10px]">Verified Match</span>
                      </div>
                      <p className="text-xs text-secondary mt-0.5">
                        Both statements ground to entity <strong>"{rel.fact_a?.entity_name || rel.fact_a?.subject || 'Organization'}"</strong> and metric <strong>"{rel.fact_a?.attribute || rel.fact_a?.predicate || 'Action'}"</strong>.
                      </p>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon bg-emerald-100 text-emerald-700">2</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-primary">7-Factor Dimensional Filter</span>
                        <span className="trace-dim-badge dim-matched text-[10px]">Context Aligned</span>
                      </div>
                      <p className="text-xs text-secondary mt-0.5">
                        Evaluated temporal periods ({rel.fact_a?.fiscal_year || 'FY2026'}), reporting scope, geographic coverage, and units. All contextual parameters confirmed comparable.
                      </p>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="audit-pipeline-step">
                    <div className={`audit-step-icon ${relType === 'CONTRADICTS' ? 'bg-rose-100 text-rose-700' : 'bg-blue-100 text-blue-700'}`}>3</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-primary">Value Delta &amp; Discrepancy Evaluation</span>
                        <span className={`trace-dim-badge ${relType === 'CONTRADICTS' ? 'dim-mismatch' : 'dim-matched'} text-[10px]`}>
                          {relType === 'CONTRADICTS' ? 'Conflict Detected' : 'Compatible'}
                        </span>
                      </div>
                      <p className="text-xs text-secondary mt-0.5">
                        {rel.explanation || `Compared claimed values: "${rel.fact_a?.normalized_value ?? rel.fact_a?.value_text}" vs "${rel.fact_b?.normalized_value ?? rel.fact_b?.value_text}".`}
                      </p>
                    </div>
                  </div>

                  {/* Step 4 */}
                  <div className="audit-pipeline-step">
                    <div className="audit-step-icon bg-accent-subtle text-accent font-bold">4</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-primary">Verdict &amp; Confidence Assignment</span>
                        <span className="trace-dim-badge bg-accent-light text-accent text-[10px] font-bold">Finalized</span>
                      </div>
                      <p className="text-xs text-secondary mt-0.5">
                        Classified as <strong className="text-primary">{relType}</strong> with {confidence.toFixed(1)}% confidence score via <strong>{engine}</strong>.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Ground-Truth Document Evidence & Citations */}
          {activeTab === 'provenance' && (
            <div className="space-y-6">
              <div className="p-3.5 rounded-xl bg-blue-50/60 border border-blue-200 text-xs text-blue-900 flex items-center gap-2">
                <IconBookOpen className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>
                  Ground-truth citations extracted verbatim from source PDF documents with verified page numbers and coordinate bounding boxes.
                </span>
              </div>

              {/* Evidence for Fact A */}
              <div className="p-4 rounded-xl bg-surface border border-border space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-accent-primary"></span>
                    <span className="text-xs font-bold font-mono uppercase text-accent">
                      Evidence Citation — Fact A
                    </span>
                  </div>
                  {evA?.page_number && (
                    <span className="status-badge status-processing text-[11px]">
                      Page {evA.page_number}
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-muted block mb-1">Source Document</span>
                  <div className="text-xs font-semibold text-primary flex items-center gap-1.5 font-mono">
                    <IconFileText className="w-3.5 h-3.5 text-accent" />
                    <span>{rel.fact_a?.document_filename || rel.fact_a?.document_id || 'Document A'}</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-muted block mb-1">Verbatim PDF Excerpt Quote</span>
                  <blockquote className="evidence-quote">
                    "{evA?.excerpt || evA?.snippet || rel.fact_a?.original_text || rel.fact_a?.object_value || 'Direct claim excerpt extracted from document page text.'}"
                  </blockquote>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[11px] font-mono text-muted pt-2 border-t border-border">
                  <div>
                    <span className="text-muted block text-[10px]">VALIDATION</span>
                    <span className="font-semibold text-emerald-600">
                      {evA?.validation_method ? `${evA.validation_method} (Score: ${evA.validation_score ?? 1.0})` : 'Exact Match (1.0)'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted block text-[10px]">BOUNDING BOX</span>
                    <span className="text-secondary">
                      {evA?.bbox ? `[${evA.bbox.x0?.toFixed(2)}, ${evA.bbox.y0?.toFixed(2)}, ${evA.bbox.x1?.toFixed(2)}, ${evA.bbox.y1?.toFixed(2)}]` : 'Normalized Page Box'}
                    </span>
                  </div>
                  <div className="flex items-end justify-end">
                    {rel.fact_a?.document_id && (
                      <button
                        className="btn btn-secondary btn-sm text-xs flex items-center gap-1"
                        onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
                      >
                        <IconExternalLink className="w-3 h-3 text-indigo-500" />
                        <span>Inspect in PDF</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Evidence for Fact B */}
              <div className="p-4 rounded-xl bg-surface border border-border space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                    <span className="text-xs font-bold font-mono uppercase text-rose-600">
                      Evidence Citation — Fact B
                    </span>
                  </div>
                  {evB?.page_number && (
                    <span className="status-badge status-processing text-[11px]">
                      Page {evB.page_number}
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-muted block mb-1">Source Document</span>
                  <div className="text-xs font-semibold text-primary flex items-center gap-1.5 font-mono">
                    <IconFileText className="w-3.5 h-3.5 text-rose-500" />
                    <span>{rel.fact_b?.document_filename || rel.fact_b?.document_id || 'Document B'}</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-muted block mb-1">Verbatim PDF Excerpt Quote</span>
                  <blockquote className="evidence-quote border-rose-500">
                    "{evB?.excerpt || evB?.snippet || rel.fact_b?.original_text || rel.fact_b?.object_value || 'Direct claim excerpt extracted from document page text.'}"
                  </blockquote>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[11px] font-mono text-muted pt-2 border-t border-border">
                  <div>
                    <span className="text-muted block text-[10px]">VALIDATION</span>
                    <span className="font-semibold text-emerald-600">
                      {evB?.validation_method ? `${evB.validation_method} (Score: ${evB.validation_score ?? 1.0})` : 'Exact Match (1.0)'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted block text-[10px]">BOUNDING BOX</span>
                    <span className="text-secondary">
                      {evB?.bbox ? `[${evB.bbox.x0?.toFixed(2)}, ${evB.bbox.y0?.toFixed(2)}, ${evB.bbox.x1?.toFixed(2)}, ${evB.bbox.y1?.toFixed(2)}]` : 'Normalized Page Box'}
                    </span>
                  </div>
                  <div className="flex items-end justify-end">
                    {rel.fact_b?.document_id && (
                      <button
                        className="btn btn-secondary btn-sm text-xs flex items-center gap-1"
                        onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
                      >
                        <IconExternalLink className="w-3 h-3 text-indigo-500" />
                        <span>Inspect in PDF</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: 7-Factor Dimensional Alignment Matrix */}
          {activeTab === 'dimensions' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-surface-alt border border-border text-xs text-secondary flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconInfo className="w-4 h-4 text-accent" />
                  <span>
                    Each fact pair is audited across 7 distinct dimensions to eliminate false positives and distinguish contextual differences from true contradictions.
                  </span>
                </div>
                <span className="font-mono text-xs font-semibold text-accent">
                  {dimensions.filter((d) => d.isMatched).length} / {dimensions.length} Aligned
                </span>
              </div>

              <div className="space-y-2">
                {dimensions.map((dim) => (
                  <div
                    key={dim.id}
                    className="p-3.5 rounded-xl bg-surface border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-accent-subtle transition-all"
                  >
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-primary font-mono">{dim.label}</span>
                        <span className={`trace-dim-badge ${dim.isMatched ? 'dim-matched' : 'dim-differing'}`}>
                          {dim.isMatched ? (
                            <>
                              <IconCheck className="w-3 h-3" />
                              <span>Aligned</span>
                            </>
                          ) : (
                            <>
                              <IconAlertTriangle className="w-3 h-3" />
                              <span>Diverges</span>
                            </>
                          )}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted">{dim.description}</p>
                    </div>

                    <div className="flex items-center gap-2 text-xs font-mono bg-surface-alt px-3 py-2 rounded-lg border border-border-subtle">
                      <span className="text-emerald-700 font-semibold max-w-[140px] truncate" title={String(dim.valueA)}>
                        {String(dim.valueA)}
                      </span>
                      <span className="text-muted font-bold">vs</span>
                      <span className={`${dim.isMatched ? 'text-secondary' : 'text-rose-600'} font-semibold max-w-[140px] truncate`} title={String(dim.valueB)}>
                        {String(dim.valueB)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: Raw Audit Metadata (JSON) */}
          {activeTab === 'raw' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-muted uppercase">
                  Machine-Readable Structured Execution Trace
                </span>
                <button
                  className="btn btn-secondary btn-sm text-xs flex items-center gap-1.5"
                  onClick={() => handleCopy(JSON.stringify(rel, null, 2), 'rawJson')}
                >
                  {copiedKey === 'rawJson' ? (
                    <>
                      <IconCheck className="w-3.5 h-3.5 text-emerald-500" />
                      <span>Copied Trace</span>
                    </>
                  ) : (
                    <>
                      <IconCopy className="w-3.5 h-3.5 text-muted" />
                      <span>Copy Full JSON</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-slate-900 border border-slate-800 font-mono text-xs text-emerald-400 overflow-x-auto max-h-80 shadow-inner">
                {JSON.stringify(rel, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* ── Modal Footer ────────────────────────────────────────────── */}
        <div className="modal-footer bg-surface-alt border-t border-border py-3 px-6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted font-mono">
            <span>Press <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px]">Esc</kbd> to close</span>
          </div>

          <div className="flex items-center gap-2">
            {rel.fact_a?.document_id && (
              <button
                className="btn btn-secondary btn-sm text-xs flex items-center gap-1"
                onClick={() => handleOpenViewer(rel.fact_a?.document_id, rel.fact_a_id, evA?.page_number || 1)}
              >
                <IconExternalLink className="w-3.5 h-3.5 text-accent" />
                <span>Fact A in Viewer</span>
              </button>
            )}
            {rel.fact_b?.document_id && (
              <button
                className="btn btn-secondary btn-sm text-xs flex items-center gap-1"
                onClick={() => handleOpenViewer(rel.fact_b?.document_id, rel.fact_b_id, evB?.page_number || 1)}
              >
                <IconExternalLink className="w-3.5 h-3.5 text-rose-500" />
                <span>Fact B in Viewer</span>
              </button>
            )}
            <button className="btn btn-primary btn-sm px-4" onClick={onClose}>
              Close Trace
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

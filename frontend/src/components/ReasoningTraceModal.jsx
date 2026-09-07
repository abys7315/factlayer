import React from 'react';
import { IconAlertTriangle, IconSparkles, IconClock, IconCpu, IconShieldCheck } from './Icons';

export default function ReasoningTraceModal({ relationship, onClose }) {
  if (!relationship) return null;

  const trace = relationship.reasoning_trace || {};
  const relType = relationship.relationship_type;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content glass-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <span className={`type-badge badge-${relType.toLowerCase()}`}>
              {relType}
            </span>
            <div>
              <h3 className="modal-title">Reasoning & Provenance Trace</h3>
              <p className="modal-subtitle">Engine: {relationship.engine || 'llm_reasoner'} • Confidence: {(relationship.confidence_score * 100).toFixed(1)}%</p>
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body space-y-6">
          {/* Fact Comparison Panel */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card card-dark">
              <div className="card-header-sm">
                <span className="text-xs uppercase tracking-wider text-muted font-mono">Source Fact A</span>
              </div>
              <div className="p-4 space-y-2">
                <div className="text-sm font-semibold text-accent">{relationship.fact_a?.entity_name || 'Entity A'}</div>
                <div className="text-xs text-muted">Attribute: <span className="text-secondary font-mono">{relationship.fact_a?.attribute || 'N/A'}</span></div>
                <div className="p-2.5 rounded bg-surface-alt font-mono text-sm text-success">
                  {typeof relationship.fact_a?.normalized_value === 'object'
                    ? JSON.stringify(relationship.fact_a?.normalized_value)
                    : String(relationship.fact_a?.normalized_value ?? relationship.fact_a?.value_text)}
                </div>
                <div className="text-xs text-muted">
                  Validity: <span className="font-mono text-secondary">{relationship.fact_a?.validity_start || 'N/A'} → {relationship.fact_a?.validity_end || 'ongoing'}</span>
                </div>
              </div>
            </div>

            <div className="card card-dark">
              <div className="card-header-sm">
                <span className="text-xs uppercase tracking-wider text-muted font-mono">Target Fact B</span>
              </div>
              <div className="p-4 space-y-2">
                <div className="text-sm font-semibold text-accent">{relationship.fact_b?.entity_name || 'Entity B'}</div>
                <div className="text-xs text-muted">Attribute: <span className="text-secondary font-mono">{relationship.fact_b?.attribute || 'N/A'}</span></div>
                <div className="p-2.5 rounded bg-surface-alt font-mono text-sm text-danger">
                  {typeof relationship.fact_b?.normalized_value === 'object'
                    ? JSON.stringify(relationship.fact_b?.normalized_value)
                    : String(relationship.fact_b?.normalized_value ?? relationship.fact_b?.value_text)}
                </div>
                <div className="text-xs text-muted">
                  Validity: <span className="font-mono text-secondary">{relationship.fact_b?.validity_start || 'N/A'} → {relationship.fact_b?.validity_end || 'ongoing'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Explanation Section */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-primary flex items-center gap-2">
              <IconSparkles className="w-4 h-4 text-indigo-400" />
              Detailed Analytical Explanation
            </h4>
            <div className="p-4 rounded-lg bg-surface border border-border text-sm text-secondary leading-relaxed">
              {relationship.explanation || trace.explanation || 'No explanation recorded for this relationship.'}
            </div>
          </div>

          {/* Rules / Steps Traces */}
          {trace.steps && trace.steps.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-primary flex items-center gap-2">
                <IconCpu className="w-4 h-4 text-emerald-400" />
                Execution Steps & Validation Checks
              </h4>
              <div className="space-y-2">
                {trace.steps.map((step, idx) => (
                  <div key={idx} className="p-3 rounded bg-surface-alt border border-border-subtle flex items-start gap-3">
                    <span className="step-num">{idx + 1}</span>
                    <div className="text-xs text-secondary leading-normal">
                      {typeof step === 'string' ? step : JSON.stringify(step)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw Trace Payload */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-primary flex items-center gap-2">
              <IconShieldCheck className="w-4 h-4 text-cyan-400" />
              Machine-Readable Reasoning Metadata
            </h4>
            <pre className="p-4 rounded-lg bg-black/60 border border-border font-mono text-xs text-emerald-300 overflow-x-auto max-h-48">
              {JSON.stringify(trace, null, 2)}
            </pre>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close Trace
          </button>
        </div>
      </div>
    </div>
  );
}

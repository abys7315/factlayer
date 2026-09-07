import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconCheckCircle,
  IconClock,
  IconAlertTriangle,
  IconSparkles,
  IconFileText,
  IconEye,
  IconArrowRight,
  IconDatabase,
} from './Icons';
import { api } from '../api/client';

const PIPELINE_STAGES = [
  { id: 'QUEUED', name: 'File Upload & Verification', desc: 'SHA-256 hash verified, file saved to secure storage' },
  { id: 'PARSING', name: 'PDF Layout & Table Parsing', desc: 'PyMuPDF structured extraction of text, blocks & tables' },
  { id: 'OCR', name: 'OCR & Image Processing', desc: 'Evaluating scanned pages, figures and diagrams' },
  { id: 'CONTEXT', name: 'Document Context Extraction', desc: 'Extracting document type, reporting period and entity context' },
  { id: 'DETECTION', name: 'Candidate Fact Detection', desc: 'Scanning numerical, financial, and temporal statements' },
  { id: 'EXTRACTING', name: 'Semantic Fact Extraction', desc: 'Gemini 2.0 Flash + Deterministic metric claim extraction' },
  { id: 'VALIDATION', name: 'Evidence Grounding & BBoxes', desc: 'Verifying verbatim quotes and character bounding-box coordinates' },
  { id: 'NORMALIZING', name: 'Value Normalization', desc: 'Standardizing currencies, metrics, units and fiscal dates' },
  { id: 'RESOLVING', name: 'Entity Resolution', desc: 'Clustering and resolving entity mentions and aliases' },
  { id: 'EMBEDDING', name: 'Vector Embedding Generation', desc: 'Generating 384-dim dense embeddings via sentence-transformers' },
  { id: 'LINKING', name: 'Cross-Document Reasoning', desc: 'Analyzing Corroborations, Contradictions and Temporal Supersession' },
];

export default function ProcessingProgressModal({ documentId, filename, onClose, onComplete }) {
  const [doc, setDoc] = useState(null);
  const [pollInterval, setPollInterval] = useState(1000);
  const [error, setError] = useState(null);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (!documentId) return;

    let isMounted = true;
    let timerId = null;

    const pollStatus = async () => {
      try {
        const docData = await api.getDocument(documentId);
        if (!isMounted) return;

        setDoc(docData);

        const stageName = docData.current_stage || docData.status;
        const logMsg = `[${new Date().toLocaleTimeString()}] Pipeline stage: ${stageName} (Status: ${docData.status})`;
        
        setLogs((prev) => {
          if (prev.length === 0 || prev[prev.length - 1] !== logMsg) {
            return [...prev.slice(-15), logMsg];
          }
          return prev;
        });

        if (docData.status === 'COMPLETED' || docData.status === 'FAILED' || docData.status === 'COMPLETED_WITH_WARNINGS') {
          if (onComplete) onComplete(docData);
          setPollInterval(0); // Stop polling
        }
      } catch (err) {
        console.error('Polling error:', err);
        setError(err.message);
      }
    };

    pollStatus();
    if (pollInterval > 0) {
      timerId = setInterval(pollStatus, pollInterval);
    }

    return () => {
      isMounted = false;
      if (timerId) clearInterval(timerId);
    };
  }, [documentId, pollInterval]);

  // Determine stage progression index
  const currentStage = (doc?.current_stage || doc?.status || 'QUEUED').toUpperCase();
  const isCompleted = doc?.status === 'COMPLETED' || doc?.status === 'COMPLETED_WITH_WARNINGS';
  const isFailed = doc?.status === 'FAILED';

  let currentStageIndex = PIPELINE_STAGES.findIndex(
    (s) => s.id === currentStage || currentStage.includes(s.id)
  );
  if (currentStageIndex === -1) {
    if (isCompleted) currentStageIndex = PIPELINE_STAGES.length;
    else currentStageIndex = 0;
  }

  const progressPercent = isCompleted
    ? 100
    : Math.min(95, Math.max(10, Math.round(((currentStageIndex + 1) / PIPELINE_STAGES.length) * 100)));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-surface border border-border-alt rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-border bg-surface-alt flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <IconFileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-primary truncate max-w-md">
                  {filename || doc?.filename || 'Document Ingestion Pipeline'}
                </h2>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                    isCompleted
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : isFailed
                      ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse'
                  }`}
                >
                  {isCompleted ? 'COMPLETED' : isFailed ? 'FAILED' : 'PROCESSING'}
                </span>
              </div>
              <p className="text-xs text-muted font-mono mt-0.5">
                ID: {documentId || doc?.id} {doc?.page_count ? `• ${doc.page_count} Pages` : ''}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-muted hover:text-primary rounded-lg hover:bg-surface transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Progress Bar Section */}
          <div className="space-y-2 bg-surface-alt p-4 rounded-xl border border-border">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-primary flex items-center gap-2">
                {!isCompleted && !isFailed && (
                  <div className="w-3 h-3 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                )}
                {isCompleted ? '✓ Processing Complete' : isFailed ? '✗ Ingestion Failed' : `Current Stage: ${currentStage}`}
              </span>
              <span className="font-mono font-bold text-indigo-400">{progressPercent}%</span>
            </div>

            {/* Glowing Animated Progress Bar */}
            <div className="w-full h-3 bg-surface rounded-full overflow-hidden p-0.5 border border-border">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isCompleted
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                    : isFailed
                    ? 'bg-gradient-to-r from-rose-500 to-red-400'
                    : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500'
                }`}
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-xs text-muted pt-1">
              <span>Stage {Math.min(currentStageIndex + 1, 11)} of 11</span>
              <span>{isCompleted ? 'Ready for Cross-Document Analysis' : 'Autonomous AI Processing'}</span>
            </div>
          </div>

          {/* Stepper Pipeline List */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
              Pipeline Preprocessing Steps
            </h3>
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {PIPELINE_STAGES.map((stage, idx) => {
                const isPassed = isCompleted || idx < currentStageIndex;
                const isCurrent = !isCompleted && !isFailed && idx === currentStageIndex;
                const isPending = idx > currentStageIndex;

                return (
                  <div
                    key={stage.id}
                    className={`flex items-start gap-3 p-2.5 rounded-lg border transition-all ${
                      isPassed
                        ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-300'
                        : isCurrent
                        ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-200 shadow-md shadow-indigo-500/5'
                        : 'bg-surface/50 border-border/50 text-muted opacity-60'
                    }`}
                  >
                    <div className="mt-0.5">
                      {isPassed ? (
                        <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                          ✓
                        </div>
                      ) : isCurrent ? (
                        <div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                      ) : (
                        <div className="w-5 h-5 rounded-full bg-surface border border-border flex items-center justify-center text-xs text-muted">
                          {idx + 1}
                        </div>
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-semibold ${isCurrent ? 'text-indigo-300 font-bold' : isPassed ? 'text-emerald-300' : 'text-secondary'}`}>
                          {stage.name}
                        </span>
                        {isCurrent && (
                          <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded font-mono">
                            ACTIVE
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-muted mt-0.5">{stage.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Terminal / Live Logs View */}
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
              <IconSparkles className="w-3.5 h-3.5 text-accent" />
              Live Preprocessing Logs
            </h3>
            <div className="p-3 rounded-lg bg-black/70 border border-border font-mono text-[11px] text-emerald-400 space-y-1 max-h-28 overflow-y-auto">
              {logs.map((l, i) => (
                <div key={i} className="leading-relaxed">
                  {l}
                </div>
              ))}
              {!isCompleted && !isFailed && (
                <div className="text-indigo-300 animate-pulse">
                  &gt; Executing background pipeline worker tasks...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-border bg-surface-alt flex items-center justify-between gap-4">
          <div className="text-xs text-muted">
            {isCompleted ? (
              <span className="text-emerald-400 font-medium">✓ Document is fully indexed and ready.</span>
            ) : isFailed ? (
              <span className="text-rose-400 font-medium">✗ Error occurred during processing.</span>
            ) : (
              <span>Please keep window open while processing finishes.</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isCompleted && (
              <>
                <Link
                  to={`/viewer/${documentId || doc?.id}`}
                  className="btn btn-primary btn-sm"
                  onClick={onClose}
                >
                  <IconEye className="w-3.5 h-3.5" />
                  <span>Open PDF Viewer</span>
                </Link>
                <Link
                  to="/facts"
                  className="btn btn-secondary btn-sm"
                  onClick={onClose}
                >
                  <IconDatabase className="w-3.5 h-3.5" />
                  <span>Explore Facts</span>
                </Link>
              </>
            )}
            <button className="btn btn-ghost btn-sm" onClick={onClose}>
              {isCompleted ? 'Done' : 'Run in Background'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

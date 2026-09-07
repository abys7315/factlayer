import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { IconEye, IconDatabase, IconCheckCircle } from './Icons';

const STEPS = [
  { id: 'upload', name: 'Uploading document', stages: ['QUEUED', 'UPLOADED'] },
  { id: 'extract_text', name: 'Extracting text', stages: ['PARSING', 'OCR'] },
  { id: 'analyze_structure', name: 'Analyzing structure', stages: ['CONTEXT', 'DETECTION'] },
  { id: 'extract_facts', name: 'Extracting facts', stages: ['EXTRACTING', 'VALIDATION', 'NORMALIZING', 'RESOLVING'] },
  { id: 'linking', name: 'Linking & reasoning', stages: ['EMBEDDING', 'LINKING', 'COMPLETED'] },
];

export default function RealtimeProcessingBanner({
  documentId,
  filename,
  onComplete,
  onDismiss,
}) {
  const [doc, setDoc] = useState(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [simulatedProgress, setSimulatedProgress] = useState(15);

  useEffect(() => {
    if (!documentId) return;

    let isMounted = true;
    let pollTimer = null;

    // Smooth progress simulation between backend stage updates
    const simTimer = setInterval(() => {
      setSimulatedProgress((prev) => {
        if (isCompleted) return 100;
        const target = ((currentStepIndex + 1) / STEPS.length) * 100;
        if (prev < target) return Math.min(target, prev + 2);
        return prev;
      });
    }, 200);

    const checkStatus = async () => {
      try {
        const data = await api.getDocument(documentId);
        if (!isMounted) return;
        setDoc(data);

        const stage = (data.current_stage || data.status || 'QUEUED').toUpperCase();

        if (data.status === 'COMPLETED' || data.status === 'COMPLETED_WITH_WARNINGS') {
          setCurrentStepIndex(STEPS.length - 1);
          setIsCompleted(true);
          setSimulatedProgress(100);
          if (onComplete) onComplete(data);
          if (pollTimer) clearInterval(pollTimer);
          return;
        }

        if (data.status === 'FAILED') {
          setIsFailed(true);
          if (pollTimer) clearInterval(pollTimer);
          return;
        }

        // Find corresponding step
        const stepIdx = STEPS.findIndex((s) => s.stages.includes(stage));
        if (stepIdx !== -1) {
          setCurrentStepIndex(stepIdx);
          setSimulatedProgress(Math.max(15, Math.round(((stepIdx + 1) / STEPS.length) * 100)));
        }
      } catch (err) {
        console.error('Error polling document status:', err);
      }
    };

    checkStatus();
    pollTimer = setInterval(checkStatus, 1000);

    return () => {
      isMounted = false;
      if (pollTimer) clearInterval(pollTimer);
      if (simTimer) clearInterval(simTimer);
    };
  }, [documentId, isCompleted, onComplete]);

  const stepNumber = Math.min(STEPS.length, currentStepIndex + 1);
  const totalSteps = STEPS.length;

  return (
    <div className="w-full bg-[#0D0E1A] border border-[#232640] rounded-2xl p-6 shadow-2xl relative overflow-hidden animate-fade-in my-6">
      {/* Ambient background glow */}
      <div className="absolute top-0 left-1/4 w-96 h-24 bg-purple-600/10 blur-3xl pointer-events-none" />

      {/* Top Header Row */}
      <div className="flex items-center justify-between mb-4 relative z-10">
        <div>
          <h3 className="text-white text-lg font-bold tracking-tight">
            {isCompleted ? 'Document processed' : 'Processing document'}
          </h3>
          <p className="text-[#8E92B2] text-xs mt-0.5">
            {isCompleted
              ? `Successfully extracted facts and evidence from ${filename || doc?.filename || 'the file'}.`
              : 'Please wait while the AI analyzes your file.'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[#A5A6C8] font-mono text-sm font-semibold">
            {stepNumber}/{totalSteps}
          </span>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="text-[#65698A] hover:text-white p-1 rounded-lg transition-colors text-sm"
              title="Dismiss"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Horizontal Continuous Progress Bar */}
      <div className="relative w-full h-[5px] bg-[#1A1C2E] rounded-full overflow-hidden mb-8">
        <div
          className="h-full rounded-full transition-all duration-300 ease-out bg-gradient-to-r from-[#8B5CF6] via-[#A855F7] to-[#EC4899] shadow-[0_0_12px_rgba(168,85,247,0.8)]"
          style={{ width: `${isCompleted ? 100 : simulatedProgress}%` }}
        />
      </div>

      {/* Step Indicators with Icons and Labels */}
      <div className="grid grid-cols-5 gap-2 relative z-10">
        {STEPS.map((step, idx) => {
          const isPassed = isCompleted || idx < currentStepIndex;
          const isCurrent = !isCompleted && !isFailed && idx === currentStepIndex;
          const isPending = !isCompleted && idx > currentStepIndex;

          return (
            <div key={step.id} className="flex flex-col items-start text-left">
              {/* Step Circle Indicator */}
              <div className="mb-2.5">
                {isPassed ? (
                  /* Completed State: Solid Purple Circle with White Checkmark */
                  <div className="w-7 h-7 rounded-full bg-[#8B5CF6] text-white flex items-center justify-center shadow-[0_0_10px_rgba(139,92,246,0.6)]">
                    <svg
                      className="w-4 h-4 stroke-current stroke-[2.5]"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                ) : isCurrent ? (
                  /* Active State: Glowing Purple Circle with Inner White Dot */
                  <div className="w-7 h-7 rounded-full bg-[#8B5CF6] flex items-center justify-center shadow-[0_0_16px_rgba(168,85,247,0.9)] animate-pulse">
                    <div className="w-2.5 h-2.5 rounded-full bg-white shadow-[0_0_6px_#fff]" />
                  </div>
                ) : (
                  /* Pending State: Dim Grayish Circle */
                  <div className="w-7 h-7 rounded-full bg-[#181A2A] border border-[#2A2E46] flex items-center justify-center" />
                )}
              </div>

              {/* Step Title Label */}
              <span
                className={`text-xs font-medium tracking-tight transition-colors ${
                  isPassed
                    ? 'text-white font-semibold'
                    : isCurrent
                    ? 'text-[#C4B5FD] font-semibold'
                    : 'text-[#505470]'
                }`}
              >
                {step.name}
              </span>
            </div>
          );
        })}
      </div>

      {/* Completed Action Buttons */}
      {isCompleted && (
        <div className="mt-6 pt-4 border-t border-[#232640] flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
            <IconCheckCircle className="w-4 h-4 text-emerald-400" />
            <span>Ready for provenance audit and cross-document reasoning.</span>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to={`/viewer/${documentId || doc?.id}`}
              className="px-3.5 py-1.5 rounded-lg bg-[#8B5CF6] hover:bg-[#7C3AED] text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-purple-900/30 transition-all"
            >
              <IconEye className="w-3.5 h-3.5" />
              <span>Open PDF Viewer</span>
            </Link>
            <Link
              to="/facts"
              className="px-3.5 py-1.5 rounded-lg bg-[#1F2136] hover:bg-[#2B2E4A] text-[#D8DAE8] text-xs font-semibold flex items-center gap-1.5 border border-[#323654] transition-all"
            >
              <IconDatabase className="w-3.5 h-3.5" />
              <span>Explore Facts</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

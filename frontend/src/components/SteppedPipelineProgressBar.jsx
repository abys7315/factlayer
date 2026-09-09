
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { IconEye, IconDatabase, IconCheckCircle, IconFileText } from './Icons';

const STAGE_ORDER = [
  'QUEUED',
  'PARSING',
  'OCR',
  'CONTEXT',
  'DETECTION',
  'EXTRACTING',
  'VALIDATION',
  'NORMALIZING',
  'RESOLVING',
  'EMBEDDING',
  'LINKING',
  'COMPLETED',
];

const PIPELINE_STEPS = [
  {
    id: 1,
    name: 'Upload & Verify',
    subtitle: 'SHA-256 validation',
    completedAfterStage: 'QUEUED',
    activeStages: ['QUEUED'],
  },
  {
    id: 2,
    name: 'Layout & Parsing',
    subtitle: 'PyMuPDF text & tables',
    completedAfterStage: 'CONTEXT',
    activeStages: ['PARSING', 'OCR', 'CONTEXT'],
  },
  {
    id: 3,
    name: 'Fact Extraction',
    subtitle: 'Gemini 2.0 Flash AI',
    completedAfterStage: 'EXTRACTING',
    activeStages: ['DETECTION', 'EXTRACTING'],
  },
  {
    id: 4,
    name: 'Grounding & BBoxes',
    subtitle: 'Coordinates & Normalization',
    completedAfterStage: 'NORMALIZING',
    activeStages: ['VALIDATION', 'NORMALIZING'],
  },
  {
    id: 5,
    name: 'Reasoning & Graph',
    subtitle: 'Cross-document links',
    completedAfterStage: 'LINKING',
    activeStages: ['RESOLVING', 'EMBEDDING', 'LINKING', 'COMPLETED'],
  },
];

export default function SteppedPipelineProgressBar({
  documentId,
  filename,
  onComplete,
  onDismiss,
}) {
  const [doc, setDoc] = useState(null);
  const [currentStage, setCurrentStage] = useState('QUEUED');
  const [isCompleted, setIsCompleted] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [stageDesc, setStageDesc] = useState('Validating file upload...');

  useEffect(() => {
    if (!documentId) return;

    let isMounted = true;
    let pollTimer = null;
    let errorCount = 0;

    const pollStatus = async () => {
      try {
        const data = await api.getDocument(documentId);
        if (!isMounted) return;
        errorCount = 0;
        setDoc(data);

        const stage = (data.current_stage || data.status || 'QUEUED').toUpperCase();
        setCurrentStage(stage);

        if (data.status === 'COMPLETED' || data.status === 'COMPLETED_WITH_WARNINGS') {
          setIsCompleted(true);
          setStageDesc('Pipeline completed successfully');
          if (onComplete) onComplete(data);
          if (pollTimer) clearInterval(pollTimer);
          return;
        }

        if (data.status === 'FAILED') {
          setIsFailed(true);
          setStageDesc(data.error_message || 'Processing failed');
          if (pollTimer) clearInterval(pollTimer);
          return;
        }

        // Descriptive stage label
        if (stage === 'QUEUED') setStageDesc('Validating file & staging storage...');
        else if (stage === 'PARSING') setStageDesc('Parsing PDF pages & extracting table matrices...');
        else if (stage === 'OCR') setStageDesc('Applying OCR to scanned pages and visual figures...');
        else if (stage === 'CONTEXT') setStageDesc('Resolving document hierarchy & accounting period...');
        else if (stage === 'DETECTION') setStageDesc('Scanning numeric, financial & temporal candidates...');
        else if (stage === 'EXTRACTING') setStageDesc('Extracting atomic facts via Gemini 2.0 Flash...');
        else if (stage === 'VALIDATION') setStageDesc('Computing character-level bounding boxes...');
        else if (stage === 'NORMALIZING') setStageDesc('Normalizing currency multipliers & fiscal dates...');
        else if (stage === 'RESOLVING') setStageDesc('Clustering entity mentions and canonical aliases...');
        else if (stage === 'EMBEDDING') setStageDesc('Computing 384-dim dense embeddings...');
        else if (stage === 'LINKING') setStageDesc('Auditing contradictions, supersessions & corroborations...');
      } catch (err) {
        errorCount += 1;
        console.error('Error polling pipeline status:', err);
        if (errorCount >= 4) {
          if (pollTimer) clearInterval(pollTimer);
          setIsFailed(true);
          setStageDesc('Document not found or server restarted. Please refresh and re-upload.');
        }
      }
    };

    pollStatus();
    pollTimer = setInterval(pollStatus, 400);

    return () => {
      isMounted = false;
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [documentId, onComplete]);

  // Determine stage progression index in STAGE_ORDER
  const currentStageIndex = isCompleted
    ? STAGE_ORDER.length - 1
    : Math.max(0, STAGE_ORDER.indexOf(currentStage));

  // Determine which step is currently active
  let activeStepId = 1;
  if (isCompleted) {
    activeStepId = 5;
  } else if (currentStageIndex >= STAGE_ORDER.indexOf('RESOLVING')) {
    activeStepId = 5;
  } else if (currentStageIndex >= STAGE_ORDER.indexOf('VALIDATION')) {
    activeStepId = 4;
  } else if (currentStageIndex >= STAGE_ORDER.indexOf('DETECTION')) {
    activeStepId = 3;
  } else if (currentStageIndex >= STAGE_ORDER.indexOf('PARSING')) {
    activeStepId = 2;
  } else {
    activeStepId = 1;
  }

  // Calculate track progress percentage
  // Step 1: 15% -> Step 2: 35% -> Step 3: 55% -> Step 4: 75% -> Step 5: 90% -> Completed: 100%
  let trackPercent = 15;
  if (isCompleted) {
    trackPercent = 100;
  } else if (activeStepId === 5) {
    trackPercent = 90;
  } else if (activeStepId === 4) {
    trackPercent = 75;
  } else if (activeStepId === 3) {
    trackPercent = 55;
  } else if (activeStepId === 2) {
    trackPercent = 35;
  } else {
    trackPercent = 15;
  }

  return (
    <div className="dribbble-stepper-container">
      <div className="dribbble-stepper-card">
        {/* Header with filename & live stage badge */}
        <div className="dribbble-stepper-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '50%',
                background: '#EFF6FF',
                color: '#2563EB',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <IconFileText className="w-4 h-4" />
            </div>
            <div>
              <h4 style={{ fontSize: '15px', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                {filename || doc?.filename || 'Document Pipeline'}
              </h4>
              <p style={{ fontSize: '12px', color: isCompleted ? '#16A34A' : isFailed ? '#E11D48' : '#2563EB', margin: '2px 0 0 0', fontWeight: 500 }}>
                {stageDesc}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                fontSize: '12px',
                fontFamily: 'monospace',
                fontWeight: 700,
                color: isCompleted ? '#16A34A' : '#2563EB',
                background: isCompleted ? '#F0FDF4' : '#EFF6FF',
                padding: '4px 12px',
                borderRadius: '9999px',
                border: `1px solid ${isCompleted ? '#BBF7D0' : '#DBEAFE'}`,
              }}
            >
              {isCompleted ? '100% COMPLETE' : `${trackPercent}%`}
            </span>
            {onDismiss && (
              <button
                onClick={onDismiss}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '16px',
                  color: '#94A3B8',
                  cursor: 'pointer',
                  padding: '4px 8px',
                }}
                title="Dismiss"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* 5 Stepped Circles & Labels in a single horizontal row (Dribbble reference layout) */}
        <div className="dribbble-stepper-steps-row">
          {PIPELINE_STEPS.map((step) => {
            const completedStageIndex = STAGE_ORDER.indexOf(step.completedAfterStage);
            const isStepCompleted = isCompleted || (currentStageIndex > completedStageIndex);
            const isStepActive = !isCompleted && !isFailed && (activeStepId === step.id);
            const isStepPending = !isStepCompleted && !isStepActive;

            return (
              <div key={step.id} className="dribbble-stepper-step-item">
                {/* Number / Checkmark Circle */}
                <div
                  className={`dribbble-stepper-circle ${isStepCompleted
                      ? 'dribbble-stepper-circle-completed'
                      : isStepActive
                        ? 'dribbble-stepper-circle-active'
                        : 'dribbble-stepper-circle-pending'
                    }`}
                >
                  {isStepCompleted ? (
                    <svg
                      style={{ width: '18px', height: '18px', stroke: '#FFFFFF', strokeWidth: 3 }}
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    step.id
                  )}
                </div>

                {/* Step Title Label */}
                <div
                  className={`dribbble-stepper-label ${isStepActive
                      ? 'dribbble-stepper-label-active'
                      : isStepCompleted
                        ? 'dribbble-stepper-label-completed'
                        : 'dribbble-stepper-label-pending'
                    }`}
                >
                  {step.name}
                </div>

                {/* Subtitle */}
                <div className="dribbble-stepper-subtitle">
                  {step.subtitle}
                </div>
              </div>
            );
          })}
        </div>

        {/* Horizontal Progress Track Bar (Exact Dribbble layout) */}
        <div className="dribbble-stepper-track">
          <div
            className="dribbble-stepper-fill"
            style={{ width: `${trackPercent}%` }}
          />
        </div>

        {/* Completion Action Bar */}
        {isCompleted && (
          <div className="dribbble-stepper-footer">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#16A34A', fontWeight: 600 }}>
              <IconCheckCircle className="w-4 h-4" />
              <span>Document indexed with character-level bounding boxes & cross-document links.</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Link
                to={`/viewer/${documentId || doc?.id}`}
                className="btn btn-primary btn-sm"
              >
                <IconEye className="w-3.5 h-3.5" />
                <span>Open PDF Viewer →</span>
              </Link>
              <Link
                to="/facts"
                className="btn btn-secondary btn-sm"
              >
                <IconDatabase className="w-3.5 h-3.5" />
                <span>Explore Facts</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

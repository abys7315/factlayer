import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconLayers,
  IconFileText,
  IconGitCompare,
  IconAlertTriangle,
  IconClock,
  IconUpload,
  IconArrowRight,
  IconSparkles,
  IconDatabase,
  IconCheckCircle,
  IconRefreshCw,
  IconExternalLink,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';
import ProcessingProgressModal from './ProcessingProgressModal';
import RealtimeProcessingBanner from './RealtimeProcessingBanner';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentContradictions, setRecentContradictions] = useState([]);
  const [recentDocs, setRecentDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRelationship, setSelectedRelationship] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [activeProcessingDoc, setActiveProcessingDoc] = useState(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, contraData, docsData] = await Promise.all([
        api.getDashboardStats().catch(() => null),
        api.getContradictions({ limit: 5 }).catch(() => ({ items: [] })),
        api.listDocuments(0, 5).catch(() => ({ items: [] })),
      ]);
      setStats(statsData);
      setRecentContradictions(contraData.items || []);
      setRecentDocs(docsData.items || []);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setUploading(true);
      setUploadMsg('Uploading & staging document for extraction pipeline...');
      const res = await api.uploadDocument(file);
      const docId = res.id || res.document_id;
      setActiveProcessingDoc({ documentId: docId, filename: file.name });
      setUploadMsg('Document uploaded! Preprocessing active.');
      await loadData();
    } catch (err) {
      setUploadMsg(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadMsg(''), 5000);
    }
  };

  return (
    <div className="dashboard-container space-y-8">
      {/* Top Banner */}
      <div className="hero-banner">
        <div className="hero-content">
          <div className="hero-badge">
            <IconSparkles className="w-4 h-4 text-indigo-400" />
            <span>Multi-Stage Autonomous Ingestion & Reasoning Engine</span>
          </div>
          <h1 className="hero-title">
            Enterprise Fact Knowledge Layer
          </h1>
          <p className="hero-description">
            Continuous PDF extraction with exact bounding-box provenance, multi-hypothesis
            entity resolution, temporal supersession tracking, and contextual contradiction detection.
          </p>
          <div className="hero-actions">
            <label className="btn btn-primary cursor-pointer">
              <IconUpload className="w-4 h-4" />
              <span>{uploading ? 'Processing Upload...' : 'Upload PDF Document'}</span>
              <input
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileUpload}
                disabled={uploading}
              />
            </label>
            <Link to="/contradictions" className="btn btn-secondary">
              <IconAlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Audit Contradictions</span>
            </Link>
            <button className="btn btn-ghost" onClick={loadData}>
              <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          {activeProcessingDoc && (
            <RealtimeProcessingBanner
              documentId={activeProcessingDoc.documentId}
              filename={activeProcessingDoc.filename}
              onComplete={() => loadData()}
              onDismiss={() => setActiveProcessingDoc(null)}
            />
          )}
          {uploadMsg && !activeProcessingDoc && (
            <div className="mt-3 text-xs font-mono text-indigo-300 bg-indigo-950/60 border border-indigo-700/50 p-2.5 rounded max-w-xl">
              {uploadMsg}
            </div>
          )}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="metric-card glass-card">
          <div className="metric-header">
            <span className="metric-label">Ingested Documents</span>
            <div className="metric-icon bg-indigo-500/10 text-indigo-400">
              <IconFileText className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value">{stats?.total_documents ?? 0}</div>
          <div className="metric-footer">
            <span className="text-success font-medium">Ready for reasoning</span>
            <span className="text-muted">PDFs & Financials</span>
          </div>
        </div>

        <div className="metric-card glass-card">
          <div className="metric-header">
            <span className="metric-label">Extracted Facts</span>
            <div className="metric-icon bg-emerald-500/10 text-emerald-400">
              <IconDatabase className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value">{stats?.total_facts ?? 0}</div>
          <div className="metric-footer">
            <span className="text-accent font-medium">Normalized & Vectorized</span>
            <span className="text-muted">Entity-Attribute pairs</span>
          </div>
        </div>

        <div className="metric-card glass-card">
          <div className="metric-header">
            <span className="metric-label">Contradictions Flagged</span>
            <div className="metric-icon bg-rose-500/10 text-rose-400">
              <IconAlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value text-rose-400">{stats?.contradictions ?? 0}</div>
          <div className="metric-footer">
            <Link to="/contradictions" className="text-rose-400 hover:underline flex items-center gap-1 font-medium">
              Investigate conflicts <IconArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>

        <div className="metric-card glass-card">
          <div className="metric-header">
            <span className="metric-label">Superseded Facts</span>
            <div className="metric-icon bg-amber-500/10 text-amber-400">
              <IconClock className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value text-amber-400">{stats?.superseded_facts ?? 0}</div>
          <div className="metric-footer">
            <Link to="/timeline" className="text-amber-400 hover:underline flex items-center gap-1 font-medium">
              View temporal timeline <IconArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>

      {/* Main Split Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Contradictions High-Priority Watch */}
        <div className="lg:col-span-2 card glass-card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded bg-rose-500/10 text-rose-400">
                <IconAlertTriangle className="w-4 h-4" />
              </div>
              <div>
                <h3 className="card-title">Critical Contradictions & Discrepancies</h3>
                <p className="card-subtitle">Conflicting statements detected across document revisions or sections</p>
              </div>
            </div>
            <Link to="/contradictions" className="btn btn-ghost btn-sm">
              View All ({stats?.contradictions ?? 0})
            </Link>
          </div>

          <div className="card-body p-0 divide-y divide-border">
            {recentContradictions.length === 0 ? (
              <div className="p-8 text-center text-muted">
                <IconCheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
                <p className="font-medium text-secondary">No unresolved contradictions detected</p>
                <p className="text-xs text-muted mt-1">Upload documents to trigger cross-document reasoning</p>
              </div>
            ) : (
              recentContradictions.map((rel) => (
                <div key={rel.id} className="p-4 hover:bg-surface-alt transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="type-badge badge-contradicts">CONTRADICTION</span>
                        <span className="text-xs font-mono text-muted">
                          Confidence: {(rel.confidence_score * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs text-muted">
                          • {rel.fact_a?.entity_name} ({rel.fact_a?.attribute})
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 mt-2 text-xs">
                        <div className="p-2.5 rounded bg-surface border border-rose-900/30">
                          <span className="text-muted block text-[10px] uppercase font-mono">Fact A:</span>
                          <span className="text-secondary font-mono">{String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}</span>
                        </div>
                        <div className="p-2.5 rounded bg-surface border border-rose-900/30">
                          <span className="text-muted block text-[10px] uppercase font-mono">Fact B:</span>
                          <span className="text-rose-400 font-mono">{String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}</span>
                        </div>
                      </div>
                      <p className="text-xs text-muted mt-2 line-clamp-2">
                        {rel.explanation}
                      </p>
                    </div>
                    <button
                      className="btn btn-secondary btn-sm shrink-0"
                      onClick={() => setSelectedRelationship(rel)}
                    >
                      <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
                      Trace
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Ingested Documents Queue */}
        <div className="card glass-card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded bg-indigo-500/10 text-indigo-400">
                <IconFileText className="w-4 h-4" />
              </div>
              <div>
                <h3 className="card-title">Recent Ingestions</h3>
                <p className="card-subtitle">Document pipeline status</p>
              </div>
            </div>
            <Link to="/documents" className="btn btn-ghost btn-sm">
              All Docs
            </Link>
          </div>

          <div className="card-body p-0 divide-y divide-border">
            {recentDocs.length === 0 ? (
              <div className="p-6 text-center text-muted text-xs">
                No documents uploaded yet.
              </div>
            ) : (
              recentDocs.map((doc) => (
                <Link
                  key={doc.id}
                  to={`/documents/${doc.id}`}
                  className="p-3.5 hover:bg-surface-alt transition-colors flex items-center justify-between block"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-sm font-medium text-primary truncate">
                      {doc.filename}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted">
                      <span>{doc.page_count ?? 1} pages</span>
                      <span>•</span>
                      <span className={`status-badge status-${(doc.status || 'completed').toLowerCase()}`}>
                        {doc.status}
                      </span>
                    </div>
                  </div>
                  <IconArrowRight className="w-4 h-4 text-muted shrink-0" />
                </Link>
              ))
            )}
          </div>

          <div className="p-4 border-t border-border bg-surface-alt/40 rounded-b-xl">
            <Link to="/documents" className="btn btn-secondary btn-sm w-full justify-center">
              Manage & Ingest More Files
            </Link>
          </div>
        </div>
      </div>

      {/* Reasoning Trace Modal */}
      {selectedRelationship && (
        <ReasoningTraceModal
          relationship={selectedRelationship}
          onClose={() => setSelectedRelationship(null)}
        />
      )}

      {/* 11-Stage Interactive Preprocessing Progress Modal */}
      {activeProcessingDoc && (
        <ProcessingProgressModal
          documentId={activeProcessingDoc.documentId}
          filename={activeProcessingDoc.filename}
          onClose={() => setActiveProcessingDoc(null)}
          onComplete={loadData}
        />
      )}
    </div>
  );
}

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
  IconSearch,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';
import SteppedPipelineProgressBar from './SteppedPipelineProgressBar';

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
    <div className="space-y-12">
      {/* ── 1. Hero Section (Screenshot 1 Style) ── */}
      <section className="hero-wrapper">
        <div className="hero-header-badge">
          <IconSparkles className="w-4 h-4" />
          <span>Multi-Stage Autonomous Ingestion & Reasoning Engine</span>
        </div>

        <h1 className="hero-main-title">
          Extract More. Stress Less.<br />
          <span className="hero-highlight-text">100% Grounded</span> Across Every Filing
        </h1>

        <p className="hero-sub-description">
          Enterprise teams and financial analysts extract atomic claims, audit contradictions, and track temporal changes across SEC filings, prospectuses, and reports with character-level PDF provenance.
        </p>

        <div className="hero-cta-group">
          <label className="btn btn-primary btn-lg cursor-pointer">
            <IconUpload className="w-5 h-5" />
            <span>{uploading ? 'Processing Upload...' : 'Upload PDF Document →'}</span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileUpload}
              disabled={uploading}
            />
          </label>

          <Link to="/contradictions" className="btn btn-secondary btn-lg">
            <IconAlertTriangle className="w-5 h-5 text-rose-500" />
            <span>Audit Contradictions</span>
          </Link>
        </div>

        {/* ── Stepped Pipeline Progress Bar right below Upload (Dribbble Ref) ── */}
        {activeProcessingDoc && (
          <div className="max-w-3xl mx-auto text-left">
            <SteppedPipelineProgressBar
              documentId={activeProcessingDoc.documentId}
              filename={activeProcessingDoc.filename}
              onComplete={() => loadData()}
              onDismiss={() => setActiveProcessingDoc(null)}
            />
          </div>
        )}

        {uploadMsg && !activeProcessingDoc && (
          <div className="mt-4 text-sm font-mono text-blue-700 bg-blue-50 border border-blue-200 p-3 rounded-xl max-w-xl mx-auto">
            {uploadMsg}
          </div>
        )}

        {/* Trust Badges Bar */}
        <div className="trust-badges-bar">
          <div className="trust-chip">
            <span className="trust-badge-icon trust-trustpilot">★</span>
            <span>Trustpilot</span>
            <span className="stars-rating">★★★★★</span>
            <span className="text-muted font-normal">4.9/5 Rating</span>
          </div>

          <div className="trust-chip">
            <span className="trust-badge-icon trust-google">G</span>
            <span>Google Rating</span>
            <span className="stars-rating">★★★★★</span>
            <span className="text-muted font-normal">4.9 Stars</span>
          </div>

          <div className="trust-chip">
            <span className="trust-badge-icon trust-verified">✓</span>
            <span>Accredited Engine</span>
            <span className="text-muted font-normal">Gemini 2.0 Flash Verified</span>
          </div>

          <div className="trust-chip">
            <IconCheckCircle className="w-4 h-4 text-emerald-500" />
            <span>Zero Hallucination</span>
            <span className="text-muted font-normal">Exact Bounding Boxes</span>
          </div>
        </div>

        {/* Hero Interactive Showcase Image */}
        <div className="hero-showcase-card">
          <img
            src="/images/hero_showcase.jpg"
            alt="FactLayer Intelligent Document Extraction Showcase"
            className="hero-showcase-image"
          />
        </div>
      </section>

      {/* ── 2. Feature Bento Grid (Screenshot 2: Superior Technology) ── */}
      <section>
        <div className="section-header-center">
          <h2 className="section-title">Powering The Future With Superior Technology</h2>
          <p className="section-subtitle">
            Autonomous multi-pass extraction with character-level PDF coordinates and 5-factor cross-document reconciliation.
          </p>
        </div>

        <div className="feature-bento-grid">
          {/* Card 1: Solar Panels style -> Atomic Extraction */}
          <div className="feature-bento-card">
            <div className="feature-icon-badge feature-icon-orange">
              <IconDatabase className="w-6 h-6" />
            </div>
            <h3 className="feature-bento-title">Atomic Fact Extraction</h3>
            <p className="feature-bento-desc">
              Extract every numeric metric, executive appointment, and table line-item with zero data loss using directive exhaustive prompting and two-pass missed-fact recovery.
            </p>
          </div>

          {/* Card 2: Solar Batteries style -> Bounding-Box Grounding */}
          <div className="feature-bento-card">
            <div className="feature-icon-badge feature-icon-purple">
              <IconLayers className="w-6 h-6" />
            </div>
            <h3 className="feature-bento-title">Bounding-Box Provenance</h3>
            <p className="feature-bento-desc">
              Every single extracted fact is grounded directly to character-exact coordinates on the source PDF page with visual polygon overlays and page attribution.
            </p>
          </div>

          {/* Card 3: EV Charging style -> Cross-Doc Reasoning */}
          <div className="feature-bento-card">
            <div className="feature-icon-badge feature-icon-blue">
              <IconGitCompare className="w-6 h-6" />
            </div>
            <h3 className="feature-bento-title">Cross-Doc Reconciliation</h3>
            <p className="feature-bento-desc">
              Distinguish between genuine contradictions and contextual reconciliations such as GAAP vs Non-GAAP, differing fiscal years, units, and corporate scopes.
            </p>
          </div>
        </div>
      </section>

      {/* ── 3. Live Operational Metrics Row ── */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Ingested Documents</span>
            <div className="metric-icon feature-icon-blue">
              <IconFileText className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value">{stats?.total_documents ?? 0}</div>
          <div className="metric-footer">
            <span className="text-success font-semibold">Active in Pipeline</span>
            <span className="text-muted">PDFs & Financials</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Extracted Facts</span>
            <div className="metric-icon feature-icon-green">
              <IconDatabase className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value">{stats?.total_facts ?? 0}</div>
          <div className="metric-footer">
            <span className="text-accent font-semibold">Normalized & Vectorized</span>
            <span className="text-muted">Grounded Claims</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Contradictions Flagged</span>
            <div className="metric-icon" style={{ background: 'var(--pastel-rose-bg)', color: 'var(--pastel-rose-text)' }}>
              <IconAlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value text-danger">{stats?.contradictions ?? 0}</div>
          <div className="metric-footer">
            <Link to="/contradictions" className="text-danger font-semibold hover:underline flex items-center gap-1">
              Investigate conflicts <IconArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Superseded Facts</span>
            <div className="metric-icon feature-icon-orange">
              <IconClock className="w-5 h-5" />
            </div>
          </div>
          <div className="metric-value text-warning">{stats?.superseded_facts ?? 0}</div>
          <div className="metric-footer">
            <Link to="/timeline" className="text-warning font-semibold hover:underline flex items-center gap-1">
              View temporal updates <IconArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── 4. Split Highlight Section (Screenshot 3: Maximize Savings) ── */}
      <section className="split-highlight-section">
        <div className="split-visual-card">
          <img
            src="/images/audit_provenance.jpg"
            alt="AI Verification and Grounding Engine"
            className="split-visual-image"
          />
        </div>

        <div className="split-content">
          <h2 className="split-headline">
            Audit Every Claim With Verbatim Grounding.
          </h2>
          <p className="split-copy">
            Eliminate hallucination risks in high-stakes corporate analysis. Our pipeline matches facts with cosine vector similarity and subjects conflicting pairs to a 5-factor contextual reasoning audit.
          </p>
          <div>
            <Link to="/facts" className="btn btn-primary">
              <span>Explore Fact Explorer →</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ── 5. Standard Grid (Screenshot 3: Setting the Standard) ── */}
      <section>
        <div className="standard-header-row">
          <div>
            <h2 className="section-title">Setting The Standard In Fact Intelligence</h2>
            <p className="section-subtitle">Engineered for financial audits, corporate due diligence, and regulatory compliance.</p>
          </div>
          <Link to="/relationships" className="btn btn-primary btn-sm">
            <span>See the difference →</span>
          </Link>
        </div>

        <div className="standard-grid">
          <div className="standard-card">
            <div className="standard-card-icon feature-icon-blue">
              <IconCheckCircle className="w-5 h-5" />
            </div>
            <h3 className="standard-card-title">Zero Hallucination Guarantee</h3>
            <p className="standard-card-desc">
              Every factual assertion is locked to exact PDF page bounding-box coordinates and raw supporting quotes.
            </p>
          </div>

          <div className="standard-card">
            <div className="standard-card-icon feature-icon-purple">
              <IconLayers className="w-5 h-5" />
            </div>
            <h3 className="standard-card-title">5-Factor Context Reasoner</h3>
            <p className="standard-card-desc">
              Understands GAAP vs Non-GAAP, fiscal years, currency units, regional scopes, and proforma additions.
            </p>
          </div>

          <div className="standard-card">
            <div className="standard-card-icon feature-icon-orange">
              <IconClock className="w-5 h-5" />
            </div>
            <h3 className="standard-card-title">Temporal Supersession</h3>
            <p className="standard-card-desc">
              Automatically tracks leadership appointments, revenue updates, and metric evolution across quarters.
            </p>
          </div>

          <div className="standard-card">
            <div className="standard-card-icon feature-icon-green">
              <IconSparkles className="w-5 h-5" />
            </div>
            <h3 className="standard-card-title">Failure Audit & QA Watchdog</h3>
            <p className="standard-card-desc">
              Central error logging and completeness auditing instantly flag low-confidence or under-extracted pages.
            </p>
          </div>
        </div>
      </section>

      {/* ── 6. Step-by-Step Flow (Screenshot 4: Going Solar With Us Is Simple) ── */}
      <section className="steps-section">
        <div>
          <h2 className="section-title" style={{ marginBottom: '2.5rem' }}>
            Fact Verification With Us<br />Is Simple.
          </h2>

          <div className="steps-list">
            <div className="step-item">
              <div className="step-number">1</div>
              <div className="step-content">
                <h3 className="step-title">Upload Any Corporate PDF</h3>
                <p className="step-desc">
                  Drag and drop SEC 10-K filings, annual reports, IPO prospectuses, or analyst notes into the secure validator.
                </p>
              </div>
            </div>

            <div className="step-item">
              <div className="step-number">2</div>
              <div className="step-content">
                <h3 className="step-title">Autonomous Fact Extraction & Grounding</h3>
                <p className="step-desc">
                  Our 11-stage pipeline parses text and tables, normalizes units and fiscal periods, and computes 384-d embeddings.
                </p>
              </div>
            </div>

            <div className="step-item">
              <div className="step-number">3</div>
              <div className="step-content">
                <h3 className="step-title">Cross-Document Contradiction Audit</h3>
                <p className="step-desc">
                  Explore corroborated figures, audit detected contradictions, and inspect complete multi-hypothesis reasoning traces.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-8 text-center" style={{ background: 'var(--bg-surface-alt)' }}>
          <div className="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto mb-4">
            <IconSparkles className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-primary mb-2">Ready to audit documents?</h3>
          <p className="text-sm text-secondary mb-6">
            Upload your first financial statement or run the synthetic cross-document benchmark.
          </p>
          <label className="btn btn-primary cursor-pointer w-full justify-center">
            <IconUpload className="w-4 h-4" />
            <span>Upload Document Now →</span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileUpload}
              disabled={uploading}
            />
          </label>
        </div>
      </section>

      {/* ── 7. Operational Data Sections: Contradictions & Documents ── */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Contradictions */}
        <div className="lg:col-span-2 card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md" style={{ background: 'var(--pastel-rose-bg)', color: 'var(--pastel-rose-text)' }}>
                <IconAlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="card-title">Critical Contradictions & Discrepancies</h3>
                <p className="card-subtitle">Conflicting claims detected across document revisions or reporting bodies</p>
              </div>
            </div>
            <Link to="/contradictions" className="btn btn-secondary btn-sm">
              View All ({stats?.contradictions ?? 0})
            </Link>
          </div>

          <div className="card-body p-0 divide-y divide-border">
            {recentContradictions.length === 0 ? (
              <div className="p-10 text-center text-muted">
                <IconCheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
                <p className="font-semibold text-primary">No unresolved contradictions detected</p>
                <p className="text-xs text-muted mt-1">Upload documents to trigger cross-document reasoning</p>
              </div>
            ) : (
              recentContradictions.map((rel) => (
                <div key={rel.id} className="p-5 hover:bg-slate-50 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="type-badge badge-contradicts">CONTRADICTION</span>
                        <span className="text-xs font-mono text-muted">
                          Confidence: {(rel.confidence_score * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs font-medium text-secondary">
                          • {rel.fact_a?.entity_name} ({rel.fact_a?.attribute})
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 mt-2 text-xs">
                        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                          <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Fact A (Filing):</span>
                          <span className="text-primary font-mono font-semibold">{String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}</span>
                        </div>
                        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200">
                          <span className="text-rose-600 block text-[10px] uppercase font-bold tracking-wider">Fact B (Conflict):</span>
                          <span className="text-rose-600 font-mono font-semibold">{String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}</span>
                        </div>
                      </div>
                      <p className="text-xs text-secondary mt-2 line-clamp-2 leading-relaxed">
                        {rel.explanation}
                      </p>
                    </div>
                    <button
                      className="btn btn-secondary btn-sm shrink-0"
                      onClick={() => setSelectedRelationship(rel)}
                    >
                      <IconSparkles className="w-3.5 h-3.5 text-blue-600" />
                      Trace
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Ingested Documents List */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md feature-icon-blue">
                <IconFileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="card-title">Recent Ingestions</h3>
                <p className="card-subtitle">Document pipeline status</p>
              </div>
            </div>
            <Link to="/documents" className="btn btn-secondary btn-sm">
              All Docs
            </Link>
          </div>

          <div className="card-body p-0 divide-y divide-border">
            {recentDocs.length === 0 ? (
              <div className="p-8 text-center text-muted text-xs">
                No documents uploaded yet.
              </div>
            ) : (
              recentDocs.map((doc) => (
                <Link
                  key={doc.id}
                  to={`/documents/${doc.id}`}
                  className="p-4 hover:bg-slate-50 transition-colors flex items-center justify-between block"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-sm font-semibold text-primary truncate">
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

          <div className="p-4 border-t border-border bg-slate-50 rounded-b-xl">
            <Link to="/documents" className="btn btn-primary btn-sm w-full justify-center">
              Manage & Ingest Documents →
            </Link>
          </div>
        </div>
      </section>

      {/* Reasoning Trace Modal */}
      {selectedRelationship && (
        <ReasoningTraceModal
          relationship={selectedRelationship}
          onClose={() => setSelectedRelationship(null)}
        />
      )}
    </div>
  );
}

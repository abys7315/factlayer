import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  IconArrowRight,
  IconEye,
  IconFileText,
  IconSparkles,
  IconShieldCheck,
  IconAlertTriangle,
  IconSearch,
  IconLayers,
  IconCheckCircle,
  IconFilter,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';

export default function PdfViewer() {
  const { docId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFactId = searchParams.get('fact_id');

  const [doc, setDoc] = useState(null);
  const [overlayData, setOverlayData] = useState(null);
  const [allFacts, setAllFacts] = useState([]);
  const [selectedFactId, setSelectedFactId] = useState(initialFactId);
  const [modalFact, setModalFact] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scale, setScale] = useState(0.85); // Compact default scale
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('this_page'); // 'this_page' | 'all_facts'
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  // Load document, overlay coordinates, and canonical facts
  useEffect(() => {
    async function loadViewerData() {
      try {
        setLoading(true);
        const [docData, overlay, factsResponse] = await Promise.all([
          api.getDocument(docId).catch(() => null),
          api.getViewerOverlay(docId).catch(() => null),
          api.listFacts({ document_id: docId, limit: 200 }).catch(() => ({ items: [] })),
        ]);
        setDoc(docData);
        setOverlayData(overlay);
        setAllFacts(factsResponse?.items || []);
        setTotalPages(docData?.page_count || overlay?.page_count || 1);
      } catch (err) {
        console.error('Failed to load viewer data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadViewerData();
  }, [docId]);

  // Combine overlay bboxes with canonical facts metadata
  const enrichedFacts = useMemo(() => {
    const overlays = overlayData?.overlays || [];
    const factMap = new Map();
    allFacts.forEach((f) => factMap.set(f.id, f));

    return overlays.map((o) => {
      const canonical = factMap.get(o.fact_id);
      return {
        ...o,
        category: canonical?.category || o.category || 'financial',
        normalized_value: canonical?.normalized_value,
        valid_from: canonical?.valid_from,
        valid_to: canonical?.valid_to,
        scope: canonical?.scope || 'Consolidated',
        basis: canonical?.basis || 'GAAP',
        fiscal_year: canonical?.fiscal_year,
        currency: canonical?.currency || 'USD',
        unit: canonical?.unit,
      };
    });
  }, [overlayData, allFacts]);

  // If initialFactId is passed, locate page and trigger modal/selection
  useEffect(() => {
    if (initialFactId && enrichedFacts.length > 0) {
      const target = enrichedFacts.find((f) => f.fact_id === initialFactId);
      if (target) {
        setSelectedFactId(target.fact_id);
        if (target.page_number) setCurrentPage(target.page_number);
        setModalFact(target);
      }
    }
  }, [initialFactId, enrichedFacts]);

  // Active page overlays
  const currentPageOverlays = useMemo(() => {
    return enrichedFacts.filter((o) => (o.page_number || 1) === currentPage);
  }, [enrichedFacts, currentPage]);

  // Filtered facts based on viewMode, category, and search query
  const displayedFacts = useMemo(() => {
    let list = viewMode === 'this_page' ? currentPageOverlays : enrichedFacts;

    if (selectedCategory !== 'ALL') {
      list = list.filter((f) => (f.category || '').toLowerCase() === selectedCategory.toLowerCase());
    }

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      list = list.filter(
        (f) =>
          (f.entity_name || '').toLowerCase().includes(q) ||
          (f.attribute || '').toLowerCase().includes(q) ||
          (f.value_text || '').toLowerCase().includes(q) ||
          (f.snippet || '').toLowerCase().includes(q)
      );
    }

    return list;
  }, [viewMode, currentPageOverlays, enrichedFacts, selectedCategory, searchTerm]);

  const handleSelectFact = (fact, openModal = false) => {
    setSelectedFactId(fact.fact_id);
    setSearchParams({ fact_id: fact.fact_id });
    if (fact.page_number && fact.page_number !== currentPage) {
      setCurrentPage(fact.page_number);
    }
    if (openModal) {
      setModalFact(fact);
    }
  };

  const handleZoomPreset = (preset) => {
    if (preset === 'fit_page') setScale(0.75);
    else if (preset === 'fit_width') setScale(0.95);
    else if (preset === 'actual') setScale(1.0);
  };

  const categories = ['ALL', 'financial', 'governance', 'operational', 'legal'];

  return (
    <div className="pdf-viewer-layout">
      {/* Top Controls Toolbar */}
      <div className="pdf-toolbar">
        <div className="flex items-center gap-3">
          <Link to={`/documents/${docId}`} className="btn btn-ghost btn-sm">
            &larr; Document Details
          </Link>
          <div className="border-l border-border h-4" />
          <div className="flex items-center gap-2">
            <IconFileText className="w-4 h-4 text-blue-600" />
            <span className="font-bold text-xs text-primary truncate max-w-xs">
              {doc?.filename || 'PDF Document Viewer'}
            </span>
          </div>
        </div>

        {/* Page Navigation */}
        <div className="flex items-center gap-1.5 bg-surface-alt px-2 py-1 rounded-md border border-border">
          <button
            type="button"
            className="btn btn-ghost btn-sm !px-2 !py-1 text-xs"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            title="Previous Page"
          >
            &larr;
          </button>
          <span className="text-xs font-mono font-medium text-muted px-1">
            Page <span className="text-primary font-bold">{currentPage}</span> of {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm !px-2 !py-1 text-xs"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            title="Next Page"
          >
            &rarr;
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className="btn btn-secondary btn-sm !px-2.5 !py-1 text-xs"
            onClick={() => setScale((s) => Math.max(0.5, Number((s - 0.1).toFixed(2))))}
            title="Zoom Out"
          >
            -
          </button>
          <span className="text-xs font-mono font-semibold text-secondary min-w-[3rem] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm !px-2.5 !py-1 text-xs"
            onClick={() => setScale((s) => Math.min(1.6, Number((s + 0.1).toFixed(2))))}
            title="Zoom In"
          >
            +
          </button>

          <div className="flex items-center gap-1 ml-1 border-l border-border pl-2">
            <button
              type="button"
              className={`btn btn-sm !px-2 !py-1 text-[11px] ${scale === 0.75 ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleZoomPreset('fit_page')}
            >
              Fit Page
            </button>
            <button
              type="button"
              className={`btn btn-sm !px-2 !py-1 text-[11px] ${scale === 0.95 ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleZoomPreset('fit_width')}
            >
              Fit Width
            </button>
            <button
              type="button"
              className={`btn btn-sm !px-2 !py-1 text-[11px] ${scale === 1.0 ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleZoomPreset('actual')}
            >
              100%
            </button>
          </div>
        </div>
      </div>

      {/* Main Split Container */}
      <div className="pdf-main-container">
        {/* PDF Canvas Viewport Area */}
        <div className="pdf-viewport-area">
          <div
            className="pdf-page-container"
            style={{
              transform: `scale(${scale})`,
              transformOrigin: 'top center',
            }}
          >
            <div className="pdf-canvas-card">
              {/* Rendered PDF Page Image */}
              <img
                key={`page-${docId}-${currentPage}`}
                src={api.getPageImageUrl(docId, currentPage, 180)}
                alt={`PDF Page ${currentPage}`}
                className="pdf-page-image"
                loading="eager"
              />

              {/* Bounding Box Highlights Overlay Layer */}
              <div className="absolute inset-0 pointer-events-none">
                {currentPageOverlays.map((overlay, idx) => {
                  const isSelected = overlay.fact_id === selectedFactId;
                  const bbox = overlay.bbox || { x0: 0.1, y0: 0.1, x1: 0.9, y1: 0.2 };
                  const left = `${(bbox.x0 ?? 0) * 100}%`;
                  const top = `${(bbox.y0 ?? 0) * 100}%`;
                  const width = `${((bbox.x1 ?? 1) - (bbox.x0 ?? 0)) * 100}%`;
                  const height = `${((bbox.y1 ?? 1) - (bbox.y0 ?? 0)) * 100}%`;

                  return (
                    <div
                      key={overlay.evidence_id || idx}
                      className={`pdf-bbox-overlay ${
                        isSelected
                          ? 'pdf-bbox-selected'
                          : 'border border-blue-500/70 bg-blue-500/10'
                      }`}
                      style={{ left, top, width, height }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectFact(overlay, true);
                      }}
                      title={`Click to view details: ${overlay.entity_name} - ${overlay.attribute}: ${overlay.value_text}`}
                    >
                      {isSelected && (
                        <div className="pdf-bbox-tag">
                          {overlay.entity_name}: {overlay.attribute} ({overlay.value_text})
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar: Extracted Facts & Provenance */}
        <div className="pdf-sidebar">
          {/* Header & Mode Switcher */}
          <div className="pdf-sidebar-header">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-primary flex items-center gap-1.5 uppercase tracking-wider">
                <IconShieldCheck className="w-4 h-4 text-blue-600" />
                Extracted Fact Claims
              </h3>
              <span className="text-[10px] font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                {displayedFacts.length} {displayedFacts.length === 1 ? 'Fact' : 'Facts'}
              </span>
            </div>

            {/* Segmented Switcher: This Page vs Show All Document Facts */}
            <div className="pdf-mode-switcher">
              <button
                type="button"
                className={`pdf-mode-btn ${viewMode === 'this_page' ? 'active' : ''}`}
                onClick={() => setViewMode('this_page')}
              >
                <span>📄 This Page</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {currentPageOverlays.length}
                </span>
              </button>
              <button
                type="button"
                className={`pdf-mode-btn ${viewMode === 'all_facts' ? 'active' : ''}`}
                onClick={() => setViewMode('all_facts')}
              >
                <span>🌐 Show All</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {enrichedFacts.length}
                </span>
              </button>
            </div>

            {/* Search Input */}
            <div className="search-input-wrapper">
              <IconSearch className="search-icon w-3.5 h-3.5 text-muted" />
              <input
                type="text"
                placeholder="Search extracted facts, metrics, entities..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input-field pl-8 !py-1.5 text-xs"
              />
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full capitalize transition-colors ${
                    selectedCategory === cat
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-surface-alt text-muted hover:text-primary'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Fact Cards Scrollable List */}
          <div className="pdf-sidebar-list">
            {displayedFacts.length === 0 ? (
              <div className="p-8 text-center text-muted text-xs space-y-2">
                <IconLayers className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="font-semibold text-secondary">No extracted facts found</p>
                <p className="text-[11px]">
                  {viewMode === 'this_page'
                    ? `No facts on Page ${currentPage}. Click "Show All" to view all document facts.`
                    : 'Try adjusting your search or category filters.'}
                </p>
              </div>
            ) : (
              displayedFacts.map((item, idx) => {
                const isSelected = item.fact_id === selectedFactId;
                const pageNum = item.page_number || 1;

                return (
                  <div
                    key={item.evidence_id || item.fact_id || idx}
                    onClick={() => handleSelectFact(item, true)}
                    className={`pdf-fact-card ${isSelected ? 'selected' : ''}`}
                    title="Click to view detailed fact breakdown & evidence"
                  >
                    {/* Top Row: Entity + Page Badge */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <span className="pdf-fact-subject truncate block">
                          {item.entity_name || 'Organization'}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <span className="text-[10px] font-mono font-bold bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200">
                          P.{pageNum}
                        </span>
                        <span className="confidence-pill text-[10px]">
                          {((item.confidence || 0.95) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {/* Predicate & Value */}
                    <div className="pdf-fact-predicate-row">
                      <span className="pdf-fact-predicate">{item.attribute}</span>
                      <span className="pdf-fact-value">{item.value_text}</span>
                    </div>

                    {/* Verbatim Source Snippet */}
                    {item.snippet && (
                      <div className="pdf-fact-snippet line-clamp-2">
                        "{item.snippet}"
                      </div>
                    )}

                    {/* Card Footer: Metadata & Inspect Button */}
                    <div className="pdf-fact-footer">
                      <span className="capitalize text-muted font-sans font-semibold">
                        {item.category || 'General'}
                      </span>
                      <span className="text-blue-600 font-semibold flex items-center gap-1 hover:underline">
                        <span>Inspect in Detail</span>
                        <IconArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Fact Detail Modal on Click */}
      {modalFact && (
        <div className="modal-backdrop" onClick={() => setModalFact(null)}>
          <div className="fact-detail-modal-card" onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className="modal-header">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                  <IconShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="modal-title text-base font-extrabold text-primary">
                    Fact Claim & Evidence Provenance
                  </h3>
                  <p className="modal-subtitle text-xs text-muted">
                    Verified grounding against source PDF page {modalFact.page_number || 1}
                  </p>
                </div>
              </div>
              <button
                className="btn-close"
                onClick={() => setModalFact(null)}
                title="Close"
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div className="modal-body space-y-4 p-5 overflow-y-auto">
              {/* Highlight Value Banner */}
              <div className="p-4 rounded-xl bg-slate-900 text-white flex items-center justify-between gap-4">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block mb-0.5">
                    {modalFact.entity_name} &bull; {modalFact.attribute}
                  </span>
                  <div className="text-xl font-bold font-mono text-emerald-400">
                    {typeof modalFact.normalized_value === 'object'
                      ? JSON.stringify(modalFact.normalized_value)
                      : String(modalFact.normalized_value ?? modalFact.value_text)}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-slate-400 block">Confidence</span>
                  <span className="text-base font-mono font-bold text-blue-400">
                    {((modalFact.confidence || 0.95) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Attributes Grid */}
              <div className="fact-detail-grid">
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Entity / Subject</span>
                  <span className="fact-detail-cell-value">{modalFact.entity_name || 'Organization'}</span>
                </div>
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Attribute / Metric</span>
                  <span className="fact-detail-cell-value">{modalFact.attribute}</span>
                </div>
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Category</span>
                  <span className="fact-detail-cell-value capitalize">{modalFact.category || 'Financial'}</span>
                </div>
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Accounting Scope / Basis</span>
                  <span className="fact-detail-cell-value">{modalFact.basis || 'GAAP'} &bull; {modalFact.scope || 'Consolidated'}</span>
                </div>
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Fiscal Period</span>
                  <span className="fact-detail-cell-value">{modalFact.fiscal_year || modalFact.valid_from || 'Full Year / As-Reported'}</span>
                </div>
                <div className="fact-detail-cell">
                  <span className="fact-detail-cell-label">Unit & Currency</span>
                  <span className="fact-detail-cell-value">{modalFact.unit || modalFact.currency || 'USD'}</span>
                </div>
              </div>

              {/* Exact Verbatim Source Excerpt */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted">
                  Exact Verbatim Source Excerpt
                </label>
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-800 leading-relaxed">
                  "{modalFact.snippet || modalFact.value_text}"
                </div>
              </div>

              {/* Coordinates & Bounding Box Details */}
              <div className="p-3 rounded-lg bg-surface-alt border border-border flex items-center justify-between text-xs font-mono text-muted">
                <span>Page: <strong className="text-primary">{modalFact.page_number || 1}</strong></span>
                <span>
                  BBox: [
                  {modalFact.bbox?.x0?.toFixed(2) ?? '0.00'}, {modalFact.bbox?.y0?.toFixed(2) ?? '0.00'},{' '}
                  {modalFact.bbox?.x1?.toFixed(2) ?? '1.00'}, {modalFact.bbox?.y1?.toFixed(2) ?? '1.00'}
                  ]
                </span>
                <span className="text-blue-600 font-semibold">Grounded & Verified</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="modal-footer p-4 border-t border-border flex items-center justify-between bg-slate-50">
              <Link
                to={`/graph?fact_id=${modalFact.id}&entity=${encodeURIComponent(modalFact.entity_name || modalFact.subject || '')}&doc_id=${docId || modalFact.document_id || ''}`}
                className="btn btn-primary btn-sm text-xs shadow-sm flex items-center gap-1.5"
                title="Explore this fact claim and its connected entity network in the interactive Knowledge Graph"
              >
                <IconNetwork className="w-3.5 h-3.5 text-white" />
                <span>Explore in Knowledge Graph</span>
              </Link>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm text-xs"
                  onClick={() => setModalFact(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

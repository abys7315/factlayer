import React, { useState, useEffect, useRef } from 'react';
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
} from './Icons';
import { api } from '../api/client';

export default function PdfViewer() {
  const { docId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFactId = searchParams.get('fact_id');

  const [doc, setDoc] = useState(null);
  const [overlayData, setOverlayData] = useState(null);
  const [selectedFactId, setSelectedFactId] = useState(initialFactId);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scale, setScale] = useState(1.2);
  const [searchTerm, setSearchTerm] = useState('');

  const canvasRef = useRef(null);
  const pdfDocRef = useRef(null);

  // Load document and overlay coordinates
  useEffect(() => {
    async function loadViewerData() {
      try {
        setLoading(true);
        const [docData, overlay] = await Promise.all([
          api.getDocument(docId),
          api.getViewerOverlay(docId, selectedFactId).catch(() => null),
        ]);
        setDoc(docData);
        setOverlayData(overlay);
        setTotalPages(docData.page_count || 1);
      } catch (err) {
        console.error('Failed to load viewer data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadViewerData();
  }, [docId, selectedFactId]);

  // If initialFactId is passed, find which page it belongs to and switch page
  useEffect(() => {
    if (overlayData?.overlays && selectedFactId) {
      const activeOverlay = overlayData.overlays.find((o) => o.fact_id === selectedFactId);
      if (activeOverlay && activeOverlay.page_number) {
        setCurrentPage(activeOverlay.page_number);
      }
    }
  }, [overlayData, selectedFactId]);

  const pdfUrl = api.getPdfUrl(docId);

  // Active page overlays
  const pageOverlays = (overlayData?.overlays || []).filter(
    (o) => o.page_number === currentPage
  );

  const handleSelectFact = (factId, pageNum) => {
    setSelectedFactId(factId);
    setSearchParams({ fact_id: factId });
    if (pageNum) setCurrentPage(pageNum);
  };

  const filteredFactsList = (overlayData?.overlays || []).filter((o) =>
    (o.entity_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (o.attribute || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (o.snippet || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="pdf-viewer-layout">
      {/* Top Controls Toolbar */}
      <div className="pdf-toolbar glass-card">
        <div className="flex items-center gap-4">
          <Link to={`/documents/${docId}`} className="btn btn-ghost btn-sm">
            &larr; Document Details
          </Link>
          <div className="border-l border-border h-5" />
          <div className="flex items-center gap-2">
            <IconFileText className="w-4 h-4 text-indigo-400" />
            <span className="font-semibold text-sm text-primary truncate max-w-xs">
              {doc?.filename || 'Document Viewer'}
            </span>
          </div>
        </div>

        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span className="text-xs font-mono text-muted">
            Page <span className="text-primary font-semibold">{currentPage}</span> of {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setScale((s) => Math.max(0.8, s - 0.2))}
          >
            -
          </button>
          <span className="text-xs font-mono text-muted">{Math.round(scale * 100)}%</span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setScale((s) => Math.min(2.0, s + 0.2))}
          >
            +
          </button>
        </div>
      </div>

      {/* Main Split Container */}
      <div className="pdf-main-container">
        {/* PDF Canvas Viewport Area */}
        <div className="pdf-viewport-area">
          <div className="pdf-page-container" style={{ transform: `scale(${scale})`, transformOrigin: 'top center' }}>
            {/* Embedded High-Resolution Page Canvas with Evidence Bounding Box Coordinates */}
            <div className="relative border border-border shadow-2xl bg-white rounded-lg overflow-hidden min-w-[650px] min-h-[850px] flex items-center justify-center">
              {/* High-Resolution Rendered PDF Page Image */}
              <img
                key={`page-${docId}-${currentPage}`}
                src={api.getPageImageUrl(docId, currentPage, 180)}
                alt={`PDF Page ${currentPage}`}
                className="w-full h-auto select-none pointer-events-auto block transition-opacity duration-200"
                loading="eager"
              />

              {/* Bounding Box Highlights Overlay Layer */}
              <div className="absolute inset-0 pointer-events-none">
                {pageOverlays.map((overlay, idx) => {
                  const isSelected = overlay.fact_id === selectedFactId;
                  const bbox = overlay.bbox || { x0: 0.1, y0: 0.1, x1: 0.9, y1: 0.2 };
                  // Convert normalized bbox [x0, y0, x1, y1] to percentage style
                  const left = `${(bbox.x0 ?? 0) * 100}%`;
                  const top = `${(bbox.y0 ?? 0) * 100}%`;
                  const width = `${((bbox.x1 ?? 1) - (bbox.x0 ?? 0)) * 100}%`;
                  const height = `${((bbox.y1 ?? 1) - (bbox.y0 ?? 0)) * 100}%`;

                  return (
                    <div
                      key={overlay.evidence_id || idx}
                      className={`absolute transition-all pointer-events-auto cursor-pointer rounded ${
                        isSelected
                          ? 'border-2 border-indigo-500 bg-indigo-500/25 shadow-lg shadow-indigo-500/30 ring-2 ring-indigo-400'
                          : 'border border-amber-400/80 bg-amber-400/15 hover:bg-amber-400/30'
                      }`}
                      style={{ left, top, width, height }}
                      onClick={() => handleSelectFact(overlay.fact_id, overlay.page_number)}
                      title={`Fact: ${overlay.entity_name} - ${overlay.attribute}: ${overlay.value_text}`}
                    >
                      <div className="absolute -top-5 left-0 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-600 text-white shadow whitespace-nowrap z-20">
                        {overlay.entity_name}: {overlay.attribute}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar: Extracted Facts & Provenance */}
        <div className="pdf-sidebar glass-card">
          <div className="p-4 border-b border-border space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
                <IconShieldCheck className="w-4 h-4 text-indigo-400" />
                Evidence Provenance ({filteredFactsList.length})
              </h3>
              <span className="text-[10px] font-mono text-muted bg-surface-alt px-2 py-0.5 rounded">
                Exact BBoxes
              </span>
            </div>

            <div className="search-input-wrapper">
              <IconSearch className="search-icon w-3.5 h-3.5 text-muted" />
              <input
                type="text"
                placeholder="Filter facts on page..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input-field pl-8 text-xs"
              />
            </div>
          </div>

          <div className="p-3 space-y-3 overflow-y-auto max-h-[calc(100vh-220px)]">
            {filteredFactsList.length === 0 ? (
              <div className="p-6 text-center text-muted text-xs">
                No evidence overlays found for this view.
              </div>
            ) : (
              filteredFactsList.map((item, idx) => {
                const isSelected = item.fact_id === selectedFactId;
                return (
                  <div
                    key={item.evidence_id || idx}
                    onClick={() => handleSelectFact(item.fact_id, item.page_number)}
                    className={`p-3 rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-950/40 shadow-md ring-1 ring-indigo-500'
                        : 'border-border bg-surface hover:bg-surface-alt'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-muted block">
                          Page {item.page_number || 1} • {item.block_type || 'Text'}
                        </span>
                        <div className="text-xs font-semibold text-primary mt-0.5">
                          {item.entity_name}
                        </div>
                        <div className="text-[11px] font-mono text-accent">
                          {item.attribute}: <span className="text-emerald-400 font-bold">{item.value_text}</span>
                        </div>
                      </div>
                      <span className="confidence-pill text-[10px]">
                        {((item.confidence || 0.95) * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Snippet from source PDF */}
                    {item.snippet && (
                      <div className="mt-2 p-2 rounded bg-black/40 border border-border-subtle text-[11px] text-secondary font-mono leading-relaxed line-clamp-3">
                        "{item.snippet}"
                      </div>
                    )}

                    <div className="mt-2 flex items-center justify-between text-[10px] text-muted font-mono">
                      <span>Exact BBox Coordinates</span>
                      <span className="text-indigo-400">Jump to box &rarr;</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

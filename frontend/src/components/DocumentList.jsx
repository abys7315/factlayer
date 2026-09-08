import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  IconFileText,
  IconUpload,
  IconSearch,
  IconRefreshCw,
  IconEye,
  IconTrash,
  IconCheckCircle,
  IconAlertTriangle,
  IconExternalLink,
  IconSparkles,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';
import SteppedPipelineProgressBar from './SteppedPipelineProgressBar';

export default function DocumentList() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [activeProcessingDoc, setActiveProcessingDoc] = useState(null);

  const fetchDocs = async () => {
    try {
      setLoading(true);
      const data = await api.listDocuments(0, 100);
      setDocuments(data.items || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
    const interval = setInterval(fetchDocs, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleUploadFile = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a valid PDF document.');
      return;
    }
    try {
      setUploading(true);
      setUploadProgress('Uploading PDF to secure processing sandbox...');
      const res = await api.uploadDocument(file);
      const docId = res.id || res.document_id;
      setActiveProcessingDoc({ documentId: docId, filename: file.name });
      setUploadProgress(`Document "${file.name}" uploaded! Real-time preprocessing active.`);
      await fetchDocs();
    } catch (err) {
      setUploadProgress(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(null), 5000);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (docId, filename, e) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm(`Are you sure you want to delete "${filename}" and all its extracted facts/provenance?`)) return;
    try {
      await api.deleteDocument(docId);
      await fetchDocs();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const filteredDocs = documents.filter((doc) =>
    (doc.filename || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (doc.document_type || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="document-list-container space-y-6">
      {/* Header & Upload Box */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Document Repository & Ingestion</h1>
          <p className="page-subtitle">
            Upload enterprise PDFs to automatically parse, classify sections, extract candidate facts, and compute cross-document contradictions.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start md:self-auto">
          <Link
            to="/graph?from=documents"
            className="btn btn-secondary btn-sm flex items-center gap-1.5"
            title="Visualize Document-Fact relationships in Knowledge Graph"
          >
            <IconNetwork className="w-4 h-4" />
            <span>Explore in Graph</span>
          </Link>
          <button className="btn btn-ghost" onClick={fetchDocs}>
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        className={`upload-zone ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        <div className="upload-zone-content">
          <div className="upload-icon-wrapper">
            <IconUpload className="w-8 h-8 text-blue-600" />
          </div>
          <div className="text-center space-y-1">
            <h3 className="text-base font-bold text-slate-900">
              {uploading ? 'Ingesting Document...' : 'Drag & Drop PDF document here, or browse'}
            </h3>
            <p className="text-xs text-slate-500">
              Supports SEC filings, 10-K reports, IPO prospectuses, and multi-page corporate PDFs with tables
            </p>
          </div>
          <label className="btn btn-primary cursor-pointer mt-2">
            <span>Choose PDF File →</span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleUploadFile(e.target.files?.[0])}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* ── Stepped Pipeline Progress Bar right below Upload (Dribbble Ref) ── */}
      {activeProcessingDoc && (
        <SteppedPipelineProgressBar
          documentId={activeProcessingDoc.documentId}
          filename={activeProcessingDoc.filename}
          onComplete={() => fetchDocs()}
          onDismiss={() => setActiveProcessingDoc(null)}
        />
      )}

      {uploadProgress && !activeProcessingDoc && (
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs font-mono text-blue-700 flex items-center gap-2">
          <IconSparkles className="w-4 h-4 text-blue-600 animate-pulse" />
          <span>{uploadProgress}</span>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex items-center gap-3">
        <div className="search-input-wrapper flex-1">
          <IconSearch className="search-icon w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search documents by name, type, or entity..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field pl-9"
          />
        </div>
      </div>

      {/* Document Table */}
      <div className="card glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-custom">
            <thead>
              <tr>
                <th>Document File</th>
                <th>Type / Doc Date</th>
                <th>Pages / Hash</th>
                <th>Status / Pipeline</th>
                <th>Created</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-12 text-muted">
                    {loading ? 'Loading document repository...' : 'No documents found. Upload your first PDF to begin!'}
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-surface-alt/60 transition-colors">
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded bg-indigo-500/10 text-indigo-400">
                          <IconFileText className="w-5 h-5" />
                        </div>
                        <div>
                          <Link to={`/documents/${doc.id}`} className="font-semibold text-primary hover:text-accent transition-colors">
                            {doc.filename}
                          </Link>
                          <div className="text-xs text-muted font-mono">
                            ID: {doc.id.substring(0, 8)}...
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="badge-pill font-medium">
                        {doc.document_type || 'General PDF'}
                      </span>
                      {doc.doc_date && (
                        <div className="text-xs text-muted mt-1 font-mono">
                          Date: {doc.doc_date}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="text-xs text-secondary font-mono">
                        {doc.page_count ?? 1} pages
                      </div>
                      <div className="text-[10px] text-muted font-mono truncate max-w-[120px]">
                        sha256: {doc.sha256_hash?.substring(0, 10)}...
                      </div>
                    </td>
                    <td>
                      <button
                        onClick={() => setActiveProcessingDoc({ documentId: doc.id, filename: doc.filename })}
                        className={`status-badge status-${(doc.status || 'completed').toLowerCase()} hover:opacity-80 transition-opacity text-left`}
                        title="Click to view 11-stage preprocessing pipeline progress"
                      >
                        {doc.status}
                        {doc.current_stage && doc.status !== 'COMPLETED' && (
                          <span className="block text-[10px] opacity-80 uppercase">
                            {doc.current_stage}
                          </span>
                        )}
                      </button>
                      {doc.error_message && (
                        <div className="text-xs text-rose-400 max-w-xs truncate mt-1">
                          {doc.error_message}
                        </div>
                      )}
                    </td>
                    <td className="text-xs text-muted font-mono">
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/graph?document_id=${encodeURIComponent(doc.id)}&from=documents`}
                          className="btn btn-secondary btn-sm flex items-center gap-1 text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/10"
                          title={`Explore Knowledge Graph for ${doc.filename}`}
                        >
                          <IconNetwork className="w-3.5 h-3.5" />
                          <span>Graph</span>
                        </Link>
                        <Link
                          to={`/viewer/${doc.id}`}
                          className="btn btn-secondary btn-sm"
                          title="Interactive PDF Viewer with Evidence Bounding Boxes"
                        >
                          <IconEye className="w-3.5 h-3.5" />
                          <span>PDF Viewer</span>
                        </Link>
                        <Link
                          to={`/documents/${doc.id}`}
                          className="btn btn-ghost btn-sm"
                          title="Document Detail"
                        >
                          <IconExternalLink className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          className="btn btn-ghost btn-sm text-rose-400 hover:text-rose-300"
                          onClick={(e) => handleDelete(doc.id, doc.filename, e)}
                          title="Delete Document"
                        >
                          <IconTrash className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

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
                <th style={{ width: '30%' }}>Document File</th>
                <th style={{ width: '16%' }}>Type & Date</th>
                <th style={{ width: '14%' }}>Pages & Hash</th>
                <th style={{ width: '14%' }}>Processing Status</th>
                <th style={{ width: '10%' }}>Created</th>
                <th style={{ width: '16%', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-16 text-slate-500">
                    <div className="flex flex-col items-center gap-2">
                      <IconFileText className="w-10 h-10 text-slate-300" />
                      <p className="font-semibold text-base text-slate-700">
                        {loading ? 'Loading document repository...' : 'No documents found in this workspace.'}
                      </p>
                      <p className="text-xs text-slate-400">Upload a PDF above to extract candidate facts and analyze contradictions.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => {
                  const statusLower = (doc.status || 'completed').toLowerCase();
                  const isParsing = statusLower === 'parsing' || statusLower === 'processing';
                  const isFailed = statusLower === 'failed' || statusLower === 'error';
                  const isCompleted = statusLower === 'completed';

                  return (
                    <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 shrink-0">
                            <IconFileText className="w-5 h-5" />
                          </div>
                          <div className="min-w-0">
                            <Link
                              to={`/documents/${doc.id}`}
                              className="font-bold text-[15px] text-slate-900 hover:text-blue-600 transition-colors block truncate max-w-[340px]"
                              title={doc.filename}
                            >
                              {doc.filename}
                            </Link>
                            <div className="text-xs text-slate-500 font-mono mt-0.5 flex items-center gap-1.5">
                              <span className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-mono text-[11px]">
                                ID: {doc.id.substring(0, 8)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="flex flex-col gap-1 items-start">
                          <span className="badge-pill font-bold text-xs bg-slate-100 text-slate-800 border border-slate-200">
                            {doc.document_type ? doc.document_type.replace(/_/g, ' ') : 'General PDF'}
                          </span>
                          {doc.doc_date && (
                            <span className="text-xs text-slate-600 font-medium">
                              {doc.doc_date}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="text-sm font-bold text-slate-800">
                          {doc.page_count ?? 1} {doc.page_count === 1 ? 'page' : 'pages'}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono truncate max-w-[130px] mt-0.5" title={doc.sha256_hash}>
                          sha: {doc.sha256_hash ? doc.sha256_hash.substring(0, 10) : '—'}...
                        </div>
                      </td>
                      <td>
                        <button
                          onClick={() => setActiveProcessingDoc({ documentId: doc.id, filename: doc.filename })}
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition-all text-left ${
                            isCompleted
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                              : isParsing
                              ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse hover:bg-blue-100'
                              : isFailed
                              ? 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                          title="Click to view 11-stage preprocessing pipeline progress"
                        >
                          {isCompleted && <IconCheckCircle className="w-3.5 h-3.5 text-emerald-600" />}
                          {isParsing && <IconRefreshCw className="w-3.5 h-3.5 text-blue-600 animate-spin" />}
                          {isFailed && <IconAlertTriangle className="w-3.5 h-3.5 text-rose-600" />}
                          <span>{doc.status}</span>
                        </button>
                        {doc.current_stage && doc.status !== 'COMPLETED' && (
                          <div className="text-[10.5px] text-blue-600 font-semibold uppercase mt-0.5 tracking-wider">
                            {doc.current_stage}
                          </div>
                        )}
                        {doc.error_message && (
                          <div className="text-xs text-rose-500 max-w-xs truncate mt-1" title={doc.error_message}>
                            {doc.error_message}
                          </div>
                        )}
                      </td>
                      <td className="text-sm font-medium text-slate-600">
                        {doc.created_at
                          ? new Date(doc.created_at).toLocaleDateString(undefined, {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                            })
                          : '—'}
                      </td>
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            to={`/graph?document_id=${encodeURIComponent(doc.id)}&from=documents`}
                            className="btn-trace-action"
                            style={{ padding: '5px 10px', fontSize: '12.5px' }}
                            title={`Explore Knowledge Graph for ${doc.filename}`}
                          >
                            <IconNetwork className="w-3.5 h-3.5 text-indigo-600" />
                            <span>Graph</span>
                          </Link>
                          <Link
                            to={`/viewer/${doc.id}`}
                            className="btn-trace-action"
                            style={{ padding: '5px 10px', fontSize: '12.5px' }}
                            title="Interactive PDF Viewer with Evidence Bounding Boxes"
                          >
                            <IconEye className="w-3.5 h-3.5 text-blue-600" />
                            <span>Viewer</span>
                          </Link>
                          <Link
                            to={`/documents/${doc.id}`}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                            title="Document Detail"
                          >
                            <IconExternalLink className="w-4 h-4" />
                          </Link>
                          <button
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                            onClick={(e) => handleDelete(doc.id, doc.filename, e)}
                            title="Delete Document"
                          >
                            <IconTrash className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

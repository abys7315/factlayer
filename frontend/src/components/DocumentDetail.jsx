import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  IconFileText,
  IconEye,
  IconDatabase,
  IconGitCompare,
  IconArrowRight,
  IconSparkles,
  IconClock,
  IconShieldCheck,
  IconAlertTriangle,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';
import RealtimeProcessingBanner from './RealtimeProcessingBanner';

export default function DocumentDetail() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [facts, setFacts] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('facts');
  const [selectedRel, setSelectedRel] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [docData, factsData, relsData] = await Promise.all([
          api.getDocument(id),
          api.listFacts({ document_id: id, limit: 100 }).catch(() => ({ items: [] })),
          api.listRelationships({ document_id: id, limit: 100 }).catch(() => ({ items: [] })),
        ]);
        setDoc(docData);
        setFacts(factsData.items || []);
        setRelationships(relsData.items || []);
      } catch (err) {
        console.error('Failed to load document details:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [id]);

  if (loading) {
    return (
      <div className="p-12 text-center text-muted space-y-3">
        <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto" />
        <p>Loading document metadata & extracted knowledge...</p>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="p-12 text-center text-muted">
        <IconAlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
        <p className="text-secondary font-medium">Document not found</p>
        <Link to="/documents" className="btn btn-secondary btn-sm mt-4">
          Back to Documents
        </Link>
      </div>
    );
  }

  return (
    <div className="document-detail-container space-y-6">
      {/* Realtime Preprocessing Banner if document is processing */}
      {doc.status !== 'COMPLETED' && doc.status !== 'COMPLETED_WITH_WARNINGS' && (
        <RealtimeProcessingBanner
          documentId={doc.id}
          filename={doc.filename}
          onComplete={(updated) => setDoc(updated)}
        />
      )}

      {/* Top Header Card */}
      <div className="card glass-card p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="badge-pill">{doc.document_type || 'PDF Document'}</span>
              <span className={`status-badge status-${(doc.status || 'completed').toLowerCase()}`}>
                {doc.status}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-primary">{doc.filename}</h1>
            <p className="text-xs text-muted font-mono">
              Document ID: {doc.id} • SHA-256: {doc.sha256_hash?.substring(0, 16)}...
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to={`/graph?document_id=${encodeURIComponent(doc.id)}&from=documents`}
              className="btn btn-secondary flex items-center gap-1.5"
              title="Explore Document Knowledge Graph"
            >
              <IconNetwork className="w-4 h-4 text-indigo-400" />
              <span>Explore in Graph</span>
            </Link>
            <Link to={`/viewer/${doc.id}`} className="btn btn-primary">
              <IconEye className="w-4 h-4" />
              <span>Launch PDF Viewer & Overlay</span>
            </Link>
          </div>
        </div>

        {/* Document Context / Summary */}
        {doc.context_summary && (
          <div className="mt-6 p-4 rounded-lg bg-surface-alt border border-border space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-accent uppercase tracking-wider">
              <IconSparkles className="w-3.5 h-3.5" />
              Document Context & Extracted Abstract
            </div>
            <p className="text-sm text-secondary leading-relaxed">
              {doc.context_summary}
            </p>
          </div>
        )}

        {/* Quick Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-border">
          <div>
            <span className="text-xs text-muted block">Total Pages</span>
            <span className="text-lg font-semibold text-primary font-mono">{doc.page_count ?? 1}</span>
          </div>
          <div>
            <span className="text-xs text-muted block">Document Date</span>
            <span className="text-lg font-semibold text-primary font-mono">{doc.doc_date || 'N/A'}</span>
          </div>
          <div>
            <span className="text-xs text-muted block">Extracted Facts</span>
            <span className="text-lg font-semibold text-emerald-400 font-mono">{facts.length}</span>
          </div>
          <div>
            <span className="text-xs text-muted block">Relationships</span>
            <span className="text-lg font-semibold text-indigo-400 font-mono">{relationships.length}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-6">
        <button
          className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 ${activeTab === 'facts' ? 'tab-btn-active' : 'text-muted hover:text-secondary'}`}
          onClick={() => setActiveTab('facts')}
        >
          <IconDatabase className="w-4 h-4" />
          <span>Extracted Facts ({facts.length})</span>
        </button>
        <button
          className={`tab-btn pb-3 text-sm font-semibold flex items-center gap-2 ${activeTab === 'relationships' ? 'tab-btn-active' : 'text-muted hover:text-secondary'}`}
          onClick={() => setActiveTab('relationships')}
        >
          <IconGitCompare className="w-4 h-4" />
          <span>Relationships & Contradictions ({relationships.length})</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'facts' && (
        <div className="card glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table-custom">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Attribute</th>
                  <th>Extracted Value</th>
                  <th>Validity Period</th>
                  <th>Confidence</th>
                  <th>Category</th>
                  <th className="text-right">Provenance</th>
                </tr>
              </thead>
              <tbody>
                {facts.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center py-8 text-muted">
                      No facts extracted from this document yet.
                    </td>
                  </tr>
                ) : (
                  facts.map((fact) => (
                    <tr key={fact.id} className="hover:bg-surface-alt/60">
                      <td className="font-semibold text-primary">
                        {fact.entity_name || 'N/A'}
                      </td>
                      <td className="font-mono text-xs text-accent">
                        {fact.attribute}
                      </td>
                      <td>
                        <span className="font-mono text-xs text-success font-semibold">
                          {typeof fact.normalized_value === 'object'
                            ? JSON.stringify(fact.normalized_value)
                            : String(fact.normalized_value ?? fact.value_text)}
                        </span>
                      </td>
                      <td className="text-xs font-mono text-muted">
                        {fact.validity_start || fact.doc_date || 'N/A'}
                        {fact.validity_end ? ` → ${fact.validity_end}` : ''}
                      </td>
                      <td>
                        <span className="confidence-pill font-mono">
                          {((fact.confidence_score || 0.95) * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td>
                        <span className="badge-pill text-[10px]">
                          {fact.category || 'General'}
                        </span>
                      </td>
                      <td className="text-right">
                        <Link
                          to={`/viewer/${doc.id}?fact_id=${fact.id}`}
                          className="btn btn-ghost btn-sm text-indigo-400"
                          title="Jump to bounding box in PDF"
                        >
                          <IconEye className="w-3.5 h-3.5" />
                          <span>View Box</span>
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'relationships' && (
        <div className="card glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table-custom">
              <thead>
                <tr>
                  <th>Relationship Type</th>
                  <th>Fact A</th>
                  <th>Fact B</th>
                  <th>Confidence / Engine</th>
                  <th>Explanation</th>
                  <th className="text-right">Trace</th>
                </tr>
              </thead>
              <tbody>
                {relationships.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="text-center py-8 text-muted">
                      No relationships recorded for this document yet.
                    </td>
                  </tr>
                ) : (
                  relationships.map((rel) => (
                    <tr key={rel.id} className="hover:bg-surface-alt/60">
                      <td>
                        <span className={`type-badge badge-${(rel.relationship_type || '').toLowerCase()}`}>
                          {rel.relationship_type}
                        </span>
                      </td>
                      <td className="text-xs">
                        <div className="font-semibold text-primary">{rel.fact_a?.entity_name}</div>
                        <div className="font-mono text-muted">{rel.fact_a?.attribute}: {String(rel.fact_a?.normalized_value ?? rel.fact_a?.value_text)}</div>
                      </td>
                      <td className="text-xs">
                        <div className="font-semibold text-primary">{rel.fact_b?.entity_name}</div>
                        <div className="font-mono text-muted">{rel.fact_b?.attribute}: {String(rel.fact_b?.normalized_value ?? rel.fact_b?.value_text)}</div>
                      </td>
                      <td className="text-xs font-mono text-muted">
                        <div>{((rel.confidence_score || 0.9) * 100).toFixed(0)}%</div>
                        <span className="text-[10px] text-accent">{rel.engine || 'llm'}</span>
                      </td>
                      <td className="text-xs text-secondary max-w-xs line-clamp-2">
                        {rel.explanation}
                      </td>
                      <td className="text-right">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setSelectedRel(rel)}
                        >
                          <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Trace</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedRel && (
        <ReasoningTraceModal
          relationship={selectedRel}
          onClose={() => setSelectedRel(null)}
        />
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  IconLayers,
  IconFileText,
  IconGitCompare,
  IconAlertTriangle,
  IconClock,
  IconSparkles,
  IconDatabase,
  IconSearch,
  IconNetwork,
} from './Icons';
import { api } from '../api/client';

export default function Navbar() {
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [activeProcessingDocs, setActiveProcessingDocs] = useState([]);

  useEffect(() => {
    async function loadStats() {
      try {
        const data = await api.getDashboardStats();
        setStats(data);
      } catch (e) {
        // Backend may still be initializing
      }
    }
    loadStats();

    // Connect to Server-Sent Events (SSE) stream for instant real-time sync
    let es = null;
    try {
      es = api.getEventSource();
      es.onopen = () => setIsLive(true);
      es.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.total_facts !== undefined) {
            setStats((prev) => ({
              ...(prev || {}),
              total_facts: payload.total_facts,
              total_relationships: payload.total_relationships,
              corroborations: payload.corroborations,
              contradictions: payload.contradictions,
              contextual_differences: payload.contextual_differences,
              superseded_facts: payload.superseded,
            }));
            setIsLive(true);
          }
          if (Array.isArray(payload.processing_docs)) {
            setActiveProcessingDocs(payload.processing_docs);
          }
        } catch (e) {
          // Keep stream active
        }
      };
      es.onerror = () => {
        setIsLive(false);
      };
    } catch (err) {
      console.debug('SSE stream initialization fallback');
    }

    const timer = setInterval(loadStats, 10000);
    return () => {
      clearInterval(timer);
      if (es) es.close();
    };
  }, []);

  const getGraphTarget = () => {
    const { pathname, search } = location;
    if (pathname.startsWith('/contradictions')) {
      return '/graph?preset=contradictions&from=contradictions';
    }
    if (pathname.startsWith('/timeline')) {
      return '/graph?preset=supersedes&from=timeline';
    }
    if (pathname.startsWith('/relationships')) {
      return '/graph?preset=relationships&from=relationships';
    }
    if (pathname.startsWith('/documents/')) {
      const parts = pathname.split('/');
      const docId = parts[2];
      if (docId) {
        return `/graph?document_id=${encodeURIComponent(docId)}&from=documents`;
      }
      return '/graph?from=documents';
    }
    if (pathname.startsWith('/documents')) {
      return '/graph?from=documents';
    }
    if (pathname.startsWith('/facts')) {
      return '/graph?from=facts';
    }
    if (pathname.startsWith('/graph')) {
      return `${pathname}${search}`;
    }
    return '/graph';
  };

  const navItems = [
    { path: '/', label: 'Dashboard', icon: IconLayers },
    { path: '/documents', label: 'Documents', icon: IconFileText },
    { path: '/facts', label: 'Fact Explorer', icon: IconDatabase },
    { path: '/graph', getTarget: getGraphTarget, label: 'Knowledge Graph', icon: IconNetwork },
    { path: '/relationships', label: 'Relationships', icon: IconGitCompare },
    { path: '/contradictions', label: 'Contradictions', icon: IconAlertTriangle, count: stats?.contradictions },
    { path: '/timeline', label: 'Timeline & History', icon: IconClock, count: stats?.superseded_facts },
  ];

  const activeDoc = activeProcessingDocs.length > 0 ? activeProcessingDocs[0] : null;

  return (
    <header className="navbar">
      <div className="navbar-container">
        <Link to="/" className="brand">
          <div className="brand-logo">
            <IconSparkles className="w-5 h-5 text-accent" />
          </div>
          <div className="brand-text">
            <span className="brand-title">FactLayer</span>
            <span className="brand-subtitle">Provenance Engine</span>
          </div>
        </Link>

        <nav className="nav-links">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            const targetUrl = item.getTarget ? item.getTarget() : item.path;
            return (
              <Link
                key={item.path}
                to={targetUrl}
                className={`nav-link ${isActive ? 'active' : ''}`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
                {item.count > 0 && (
                  <span className={`badge-pill ${item.path === '/contradictions' ? 'badge-pill-danger' : 'badge-pill-warning'}`}>
                    {item.count}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="nav-actions">
          {activeDoc && (
            <Link
              to="/documents"
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-950/60 border border-indigo-500/40 text-xs text-indigo-300 hover:text-white transition-all shadow-sm"
              title={`Ingestion active: ${activeDoc.filename}`}
            >
              <span className="live-dot"></span>
              <span className="font-mono truncate max-w-[130px]">{activeDoc.filename}</span>
              <span className="text-[10px] uppercase font-bold text-indigo-400">({activeDoc.stage})</span>
            </Link>
          )}

          <div className="live-indicator hidden sm:flex" title={isLive ? 'Real-time Server-Sent Events stream active' : 'Live stream reconnecting...'}>
            <span className={`live-dot ${isLive ? '' : 'bg-amber-400'}`}></span>
            <span>{isLive ? 'Real-Time' : 'Syncing'}</span>
          </div>

          {stats && (
            <div className="phone-contact">
              <span className="status-dot"></span>
              <span>{stats.total_facts} Grounded Facts</span>
            </div>
          )}
          <Link to="/documents" className="btn btn-primary btn-sm">
            <IconFileText className="w-4 h-4" />
            <span>Ingest Document →</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

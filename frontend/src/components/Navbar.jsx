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
} from './Icons';
import { api } from '../api/client';

export default function Navbar() {
  const location = useLocation();
  const [stats, setStats] = useState(null);

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
    const timer = setInterval(loadStats, 15000);
    return () => clearInterval(timer);
  }, []);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: IconLayers },
    { path: '/documents', label: 'Documents', icon: IconFileText },
    { path: '/facts', label: 'Fact Explorer', icon: IconDatabase },
    { path: '/relationships', label: 'Relationships', icon: IconGitCompare },
    { path: '/contradictions', label: 'Contradictions', icon: IconAlertTriangle, count: stats?.contradictions },
    { path: '/timeline', label: 'Timeline & History', icon: IconClock, count: stats?.superseded_facts },
  ];

  return (
    <header className="navbar">
      <div className="navbar-container">
        <Link to="/" className="brand">
          <div className="brand-logo">
            <IconSparkles className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="brand-text">
            <span className="brand-title">FactLayer</span>
            <span className="brand-subtitle">Autonomous Knowledge Engine</span>
          </div>
        </Link>

        <nav className="nav-links">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
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
          {stats && (
            <div className="status-indicator">
              <span className="status-dot online"></span>
              <span className="status-text">{stats.total_facts} Active Facts</span>
            </div>
          )}
          <Link to="/documents" className="btn btn-primary btn-sm">
            <IconFileText className="w-4 h-4" />
            <span>Ingest Document</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

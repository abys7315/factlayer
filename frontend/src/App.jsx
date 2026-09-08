import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import DocumentList from './components/DocumentList';
import DocumentDetail from './components/DocumentDetail';
import PdfViewer from './components/PdfViewer';
import FactExplorer from './components/FactExplorer';
import RelationshipExplorer from './components/RelationshipExplorer';
import ContradictionView from './components/ContradictionView';
import TimelineView from './components/TimelineView';
import KnowledgeGraphView from './components/KnowledgeGraphView';

export default function App() {
  return (
    <Router>
      <div className="app-shell">
        <Navbar />
        <main className="main-content">
          <div className="content-container">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/documents" element={<DocumentList />} />
              <Route path="/documents/:id" element={<DocumentDetail />} />
              <Route path="/viewer/:docId" element={<PdfViewer />} />
              <Route path="/facts" element={<FactExplorer />} />
              <Route path="/relationships" element={<RelationshipExplorer />} />
              <Route path="/contradictions" element={<ContradictionView />} />
              <Route path="/timeline" element={<TimelineView />} />
              <Route path="/graph" element={<KnowledgeGraphView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

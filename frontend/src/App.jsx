import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { useState, useEffect } from 'react';

import AuthPage from './screens/AuthPage';
import UploadPage from './screens/UploadPage';
import LibraryPage from './screens/LibraryPage';
import SearchPage from './screens/SearchPage';
import QAPage from './screens/QAPage';
import AnalyticsPage from './screens/AnalyticsPage';
import HistoryPage from './screens/HistoryPage';

function Sidebar({ onLogout }) {
  const navigate = useNavigate();
  const nav = [
    { to: '/library',   icon: '📚', label: 'Library' },
    { to: '/upload',    icon: '⬆️', label: 'Upload' },
    { to: '/search',    icon: '🔍', label: 'Search' },
    { to: '/qa',        icon: '💬', label: 'Ask AI' },
    { to: '/analytics', icon: '📊', label: 'Analytics' },
    { to: '/history',   icon: '🕐', label: 'History' },
  ];

  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-icon">🧠</div>
        <div>
          <div className="logo-text">PaperMind</div>
          <div className="logo-sub">AI Research</div>
        </div>
      </div>

      <nav className="nav">
        <span className="nav-section">Navigation</span>
        {nav.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
        <button className="nav-item" onClick={onLogout} style={{ color: 'var(--rose)', width: '100%' }}>
          <span className="nav-icon">🚪</span> Sign Out
        </button>
      </div>
    </aside>
  );
}

function AppShell() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem('pm_token');
    toast.success('Signed out');
    navigate('/auth');
  }

  return (
    <div className="app-shell">
      <Sidebar onLogout={handleLogout} />
      <main className="main-content">
        <Routes>
          <Route path="/library"   element={<LibraryPage />} />
          <Route path="/upload"    element={<UploadPage />} />
          <Route path="/search"    element={<SearchPage />} />
          <Route path="/qa"        element={<QAPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/history"   element={<HistoryPage />} />
          <Route path="*"          element={<Navigate to="/library" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function RequireAuth({ children }) {
  const token = localStorage.getItem('pm_token');
  if (!token) return <Navigate to="/auth" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            fontFamily: 'var(--font)',
            fontSize: '0.875rem',
          },
          success: { iconTheme: { primary: 'var(--emerald)', secondary: '#fff' } },
          error: { iconTheme: { primary: 'var(--rose)', secondary: '#fff' } },
        }}
      />
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/*" element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        } />
      </Routes>
    </BrowserRouter>
  );
}

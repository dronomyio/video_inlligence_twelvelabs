import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, Search, Scissors, ShieldCheck, BarChart2,
  Zap, Radio, ChevronRight, Database, Target, Film, GitBranch
} from 'lucide-react';
import api from './api.jsx';
import Dashboard from './pages/Dashboard.jsx';
import SearchTrack from './pages/SearchTrack.jsx';
import SegmentationTrack from './pages/SegmentationTrack.jsx';
import ComplianceTrack from './pages/ComplianceTrack.jsx';
import AdvertiserBriefs from './pages/AdvertiserBriefs.jsx';
import VideoGrid from './pages/VideoGrid.jsx';
import Campaigns from './pages/Campaigns.jsx';
import Payments from './pages/Payments.jsx';
import CreativesPage from './pages/CreativesPage.jsx';
import TrackItPage from './pages/TrackItPage.jsx';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchInterval: 15000, retry: 1 } },
});

const NAV = [
  { to: '/',            icon: BarChart2,   label: 'Dashboard'    },
  { to: '/videos',      icon: Database,    label: 'Video Graph'  },
  { to: '/search',      icon: Search,      label: 'Search Track' },
  { to: '/segment',     icon: Scissors,    label: 'Segmentation' },
  { to: '/compliance',  icon: ShieldCheck, label: 'Compliance'   },
  { to: '/briefs',      icon: Zap,         label: 'Ad Briefs'    },
  { to: '/campaigns',   icon: Target,      label: 'Campaigns'    },
  { to: '/creatives',   icon: Film,        label: 'LTX Creatives'},
  { to: '/trackit',     icon: GitBranch,   label: 'TrackIt'      },
  { to: '/payments',    icon: Activity,    label: 'Payments'     },
];

function Sidebar({ stats, pipelineStatus, onStartPipeline }) {
  const loc = useLocation();
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    await onStartPipeline();
    setTimeout(() => setStarting(false), 3000);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Radio size={20} style={{ color: 'var(--accent)' }} />
        <span className="sidebar-title">ViralIntel</span>
        <span className="sidebar-tag">NAB 2026</span>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) =>
            `nav-item ${isActive ? 'active' : ''}`}>
            <Icon size={16} />
            <span>{label}</span>
            {loc.pathname === to && <ChevronRight size={12} className="nav-arrow" />}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-stats">
        <div className="stat-row">
          <span className="stat-label">Videos</span>
          <span className="stat-val mono">{stats?.videos ?? ' - '}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Scenes</span>
          <span className="stat-val mono">{stats?.scenes ?? ' - '}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Creators</span>
          <span className="stat-val mono">{stats?.creators ?? ' - '}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Trends</span>
          <span className="stat-val mono">{stats?.trends ?? ' - '}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Flags</span>
          <span className="stat-val mono" style={{ color: 'var(--red)' }}>
            {stats?.flags ?? ' - '}
          </span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Queue</span>
          <span className="stat-val mono" style={{ color: 'var(--amber)' }}>
            {pipelineStatus?.queue_depth ?? ' - '}
          </span>
        </div>
      </div>

      <button
        className={`pipeline-btn ${starting ? 'running' : ''}`}
        onClick={handleStart}
        disabled={starting}
      >
        <Activity size={14} />
        {starting ? 'Starting...' : 'Run Pipeline'}
      </button>
    </aside>
  );
}

function AppInner() {
  const { data: statsData } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.getStats().then(r => r.data),
  });
  const { data: pipelineData } = useQuery({
    queryKey: ['pipeline'],
    queryFn: () => api.getPipelineStatus().then(r => r.data),
  });

  const startPipeline = async () => {
    try { await api.startPipeline(); }
    catch (e) { console.error(e); }
  };

  const location = useLocation();

  return (
    <div className="app-layout">
      <Sidebar
        stats={statsData}
        pipelineStatus={pipelineData}
        onStartPipeline={startPipeline}
      />
      <main className="app-main">
        <AnimatePresence mode="wait" initial={false}>
          <Routes>
            <Route path="/"           element={<Dashboard stats={statsData} pipeline={pipelineData} />} />
            <Route path="/videos"     element={<VideoGrid />} />
            <Route path="/search"     element={<SearchTrack />} />
            <Route path="/segment"    element={<SegmentationTrack />} />
            <Route path="/compliance" element={<ComplianceTrack />} />
            <Route path="/briefs"     element={<AdvertiserBriefs />} />
            <Route path="/campaigns"  element={<Campaigns />} />
            <Route path="/creatives"  element={<CreativesPage />} />
            <Route path="/trackit"    element={<TrackItPage />} />
            <Route path="/payments"   element={<Payments />} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppInner />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

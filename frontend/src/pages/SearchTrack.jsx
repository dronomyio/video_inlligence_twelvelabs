import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Search, Clock, Film, ChevronRight } from 'lucide-react';
import api from '../api.jsx';
import { motion, AnimatePresence } from 'framer-motion';
import { PageWrap, FadeUp, StaggerList, StaggerItem, CountUp, AnimatedBar, ScanLine, PopIn, SeverityPing, TimelineReveal } from '../animations.jsx';

const EXAMPLE_QUERIES = [
  "emotional celebration after a game-winning moment",
  "wide establishing shots of urban skylines at golden hour",
  "interview segments with outdoor natural lighting",
  "fast-paced action with quick cuts and dynamic camera movement",
  "sunset over water with birds flying",
  "crowd reaction to unexpected sports moment",
  "news anchor delivering breaking news urgently",
  "slow motion athlete in peak performance",
];

const CONTENT_TYPES = [
  { value: "any",         label: "All Archives" },
  { value: "sports",      label: "Sports" },
  { value: "news",        label: "News Broadcast" },
  { value: "production",  label: "B-Roll / Production" },
  { value: "documentary", label: "Documentary" },
];

function formatTime(s) {
  if (!s && s !== 0) return '--';
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

export default function SearchTrack() {
  const [query, setQuery]             = useState('');
  const [contentType, setContentType] = useState('any');
  const [results, setResults]         = useState(null);
  const [searchTime, setSearchTime]   = useState(null);
  const [searched, setSearched]       = useState(false);

  const { data: topHooks } = useQuery({
    queryKey: ['top-hooks'],
    queryFn: () => api.getTopHooks({ limit: 5 }).then(r => r.data),
  });

  const searchMutation = useMutation({
    mutationFn: async ({ query, contentType }) => {
      const t0 = Date.now();
      const res = await api.semanticSearch({ query, content_type: contentType, limit: 20, use_twelvelabs: true });
      setSearchTime(((Date.now() - t0) / 1000).toFixed(2));
      return res.data;
    },
    onSuccess: (data) => { setResults(data); setSearched(true); },
  });

  const handleSearch = () => {
    if (!query.trim()) return;
    searchMutation.mutate({ query, contentType });
  };

  return (
    <PageWrap>
      <div className="page">
        <FadeUp>
          <div className="page-header">
            <div className="page-title">Archive Search</div>
            <div className="page-sub">TwelveLabs Marengo via AWS Bedrock  -  semantic moment retrieval across broadcast archives</div>
          </div>
        </FadeUp>

        {/* Search bar */}
        <FadeUp delay={0.08}>
          <div className="card">
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <select value={contentType} onChange={e => setContentType(e.target.value)}
                style={{ background: 'var(--bg2)', border: '1px solid var(--border2)', borderRadius: 6,
                         padding: '8px 12px', color: 'var(--text)', fontSize: 13, minWidth: 160 }}>
                {CONTENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder='e.g. "emotional celebration after a game-winning moment"'
                style={{ flex: 1, background: 'var(--bg2)', border: '1px solid var(--border2)',
                         borderRadius: 6, padding: '8px 14px', color: 'var(--text)', fontSize: 14 }} />
              <motion.button onClick={handleSearch}
                disabled={searchMutation.isPending || !query.trim()}
                whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                style={{ background: 'var(--cyan)', color: 'var(--bg)', border: 'none', borderRadius: 6,
                         padding: '8px 20px', fontWeight: 700, cursor: 'pointer', fontSize: 14,
                         opacity: searchMutation.isPending ? 0.7 : 1 }}>
                {searchMutation.isPending ? 'Searching...' : 'Search'}
              </motion.button>
            </div>

            {/* Scanning animation while searching */}
            <AnimatePresence>{searchMutation.isPending && <ScanLine />}</AnimatePresence>

            <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)', marginBottom: 10 }}>
              x402 gated * $0.05 USDC * model: twelvelabs.marengo-retrieval-2-7-v1
            </div>

            {/* Example query chips */}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6,
                          textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: 'var(--mono)' }}>
              Example queries
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {EXAMPLE_QUERIES.map((q, i) => (
                <motion.button key={q} onClick={() => setQuery(q)}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  whileHover={{ scale: 1.03, borderColor: 'var(--cyan)' }}
                  style={{ background: 'var(--bg2)', border: '1px solid var(--border)',
                           borderRadius: 4, padding: '4px 10px', fontSize: 12,
                           color: 'var(--muted)', cursor: 'pointer' }}>
                  {q}
                </motion.button>
              ))}
            </div>
          </div>
        </FadeUp>

        {/* Results */}
        <PopIn show={searched}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div className="card-title">
                <CountUp to={results?.results?.length || 0} /> moments found
                {searchTime && (
                  <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    style={{ marginLeft: 8, color: 'var(--green)', fontWeight: 400 }}>
                    in {searchTime}s
                  </motion.span>
                )}
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                {results?.search_source || 'bedrock'}
              </span>
            </div>

            {results?.results?.length === 0 && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ textAlign: 'center', color: 'var(--muted)', padding: '24px 0' }}>
                No moments found  -  try a different query
              </motion.div>
            )}

            <StaggerList>
              {(results?.results || []).map((r, i) => (
                <StaggerItem key={i}>
                  <div style={{ display: 'flex', gap: 12, padding: '10px 0',
                                borderBottom: '1px solid var(--border)' }}>
                    <div style={{ width: 80, height: 52, background: 'var(--bg3)', borderRadius: 4,
                                  flexShrink: 0, display: 'flex', alignItems: 'center',
                                  justifyContent: 'center', overflow: 'hidden' }}>
                      {r.thumbnail_url
                        ? <img src={r.thumbnail_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        : <Film size={20} color="var(--muted)" />}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>
                          {r.title || r['v.title'] || r['v.video_id']?.replace(/_/g,' ') || `Archive clip ${i + 1}`}
                        </span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>#{i + 1}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 12, marginBottom: 6 }}>
                        <span style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Clock size={11} /> {formatTime(r.start)}--{formatTime(r.end)}
                        </span>
                        <span className="badge b-cyan" style={{ fontSize: 10 }}>
                          {r['v.category'] || r.content_type || r.category || 'archive'}
                        </span>
                      </div>
                      <AnimatedBar value={r.score || 0} color="var(--cyan)" delay={i * 0.05} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <ChevronRight size={16} color="var(--muted)" />
                    </div>
                  </div>
                </StaggerItem>
              ))}
            </StaggerList>
          </div>
        </PopIn>

        {/* Top hooks */}
        <FadeUp delay={0.15}>
          <div className="card">
            <div className="card-title">Top archive moments  -  highest attention score</div>
            {!topHooks?.moments?.length && (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Run the pipeline first to populate archive moments</div>
            )}
            <StaggerList>
              {(topHooks?.moments || []).slice(0, 5).map((m, i) => (
                <StaggerItem key={i}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10,
                                padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--mono)', color: 'var(--cyan)', minWidth: 20 }}>{i + 1}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: 'var(--text)' }}>{m.title || m.video_title}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted)' }}>@ {formatTime(m.t_start)}</div>
                    </div>
                    <AnimatedBar value={m.viral_segment_score || 0} color="var(--green)" delay={i * 0.06} />
                  </div>
                </StaggerItem>
              ))}
            </StaggerList>
          </div>
        </FadeUp>
      </div>
    </PageWrap>
  );
}


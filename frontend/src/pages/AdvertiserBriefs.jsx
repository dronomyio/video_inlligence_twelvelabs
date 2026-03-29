import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Zap, ExternalLink, DollarSign } from 'lucide-react';
import api from '../api.jsx';

export default function AdvertiserBriefs() {
  const [category, setCategory] = useState('');
  const [minCpm, setMinCpm] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ['briefs', category, minCpm],
    queryFn: () => api.getBriefs({ category: category || undefined, min_cpm: minCpm, limit: 100 }).then(r => r.data),
  });

  const briefs = data?.briefs || [];
  const avgCpm = briefs.length
    ? (briefs.reduce((s, b) => s + (b['ab.estimated_cpm'] || 0), 0) / briefs.length).toFixed(2)
    : 0;
  const topCpm = briefs.length
    ? Math.max(...briefs.map(b => b['ab.estimated_cpm'] || 0)).toFixed(2)
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">ZeroClick Advertiser Briefs</div>
        <div className="page-subtitle">
          AI-generated contextual placement cards  -  zero effort advertiser activation
        </div>
      </div>

      <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 20 }}>
        <div className="metric-card">
          <div className="metric-label">Total Briefs</div>
          <div className="metric-val">{briefs.length}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Avg CPM</div>
          <div className="metric-val" style={{ color: 'var(--green)' }}>${avgCpm}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Top CPM</div>
          <div className="metric-val" style={{ color: 'var(--amber)' }}>${topCpm}</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={category} onChange={e => setCategory(e.target.value)}>
          <option value="">All Categories</option>
          <option value="food_cooking">Food & Cooking</option>
          <option value="product_unboxing">Product Unboxing</option>
          <option value="sports_highlights">Sports</option>
          <option value="satisfying_asmr">Satisfying / ASMR</option>
          <option value="life_hack_tutorial">Life Hacks</option>
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Min CPM $</span>
          <input type="number" value={minCpm} onChange={e => setMinCpm(parseFloat(e.target.value) || 0)}
            style={{ width: 80 }} min={0} max={20} step={0.5} />
        </div>
      </div>

      {isLoading ? (
        <div className="loading"><div className="spinner" />Loading briefs...</div>
      ) : briefs.length === 0 ? (
        <div className="empty">
          <Zap size={32} style={{ color: 'var(--border2)', marginBottom: 12 }} />
          <div>No briefs generated yet  -  run the pipeline to start</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {briefs.map((b, i) => (
            <div key={i} className="card" style={{
              borderLeft: '3px solid var(--amber)',
              transition: 'border-color 0.15s',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  {/* Headline */}
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, color: 'var(--text)' }}>
                    {b['ab.headline']}
                  </div>

                  {/* Meta row */}
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
                    <span className="tag">{b['v.category']}</span>
                    <span style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Zap size={11} /> Placement at {parseFloat(b['ab.placement_moment'] || 0).toFixed(1)}s
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {(b['v.view_count'] || 0).toLocaleString()} views
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <DollarSign size={11} />
                      Viral score: {parseFloat(b['v.viral_score'] || 0).toFixed(2)}
                    </span>
                  </div>

                  {/* ZeroClick context */}
                  <div style={{
                    background: 'var(--bg2)', borderRadius: 6, padding: '10px 12px',
                    fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 10,
                  }}>
                    {b['ab.zeroclick_context']}
                  </div>

                  {/* Verticals */}
                  {b['ab.target_verticals'] && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, color: 'var(--muted)', marginRight: 4 }}>Verticals:</span>
                      {(Array.isArray(b['ab.target_verticals'])
                        ? b['ab.target_verticals']
                        : [b['ab.target_verticals']]
                      ).map((v, j) => (
                        <span key={j} className="tag" style={{ color: 'var(--accent2)' }}>{v}</span>
                      ))}
                    </div>
                  )}
                </div>

                {/* CPM + link */}
                <div style={{ textAlign: 'right', minWidth: 90 }}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase',
                    letterSpacing: '0.08em', marginBottom: 4 }}>Est. CPM</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 700,
                    color: 'var(--amber)' }}>
                    ${parseFloat(b['ab.estimated_cpm'] || 0).toFixed(2)}
                  </div>
                  <a href={b['v.url']} target="_blank" rel="noreferrer"
                    style={{ fontSize: 11, color: 'var(--muted)', display: 'flex',
                      alignItems: 'center', gap: 3, justifyContent: 'flex-end', marginTop: 8 }}>
                    <ExternalLink size={10} /> View video
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

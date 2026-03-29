import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Play, TrendingUp } from 'lucide-react';
import api from '../api.jsx';

const CAT_COLORS = {
  food_cooking: 'var(--accent)',
  product_unboxing: 'var(--amber)',
  sports_highlights: 'var(--green)',
  satisfying_asmr: 'var(--accent2)',
  life_hack_tutorial: 'var(--red)',
};

export default function VideoGrid() {
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(0);
  const limit = 48;

  const { data, isLoading } = useQuery({
    queryKey: ['videos', category, page],
    queryFn: () => api.getVideos({
      skip: page * limit,
      limit,
      category: category || undefined,
    }).then(r => r.data),
    keepPreviousData: true,
  });

  const videos = data?.videos || [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Video Graph</div>
        <div className="page-subtitle">
          500-video Neo4j ontology  -  each card is a graph node with Creator, Trend, Scene, and Brief edges
        </div>
      </div>

      {/* Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['', 'food_cooking', 'product_unboxing', 'sports_highlights', 'satisfying_asmr', 'life_hack_tutorial'].map(c => (
          <button key={c}
            className={category === c ? 'btn-primary' : 'btn-ghost'}
            style={category === c ? {} : { fontSize: 12, padding: '6px 12px' }}
            onClick={() => { setCategory(c); setPage(0); }}>
            {c === '' ? 'All' : c.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="loading"><div className="spinner" />Loading video graph...</div>
      ) : (
        <>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
            Showing {page * limit + 1}--{page * limit + videos.length} videos
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 12,
          }}>
            {videos.map((v, i) => (
              <div key={i} className="card" style={{
                padding: 0, overflow: 'hidden',
                borderTop: `2px solid ${CAT_COLORS[v['v.category']] || 'var(--border)'}`,
                transition: 'transform 0.15s, border-color 0.15s',
              }}
                onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'none'}
              >
                {/* Thumbnail */}
                {v['v.thumbnail_url'] ? (
                  <div style={{ position: 'relative', paddingTop: '56.25%', background: 'var(--bg3)', overflow: 'hidden' }}>
                    <img src={v['v.thumbnail_url']} alt=""
                      style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                    <div style={{
                      position: 'absolute', top: 6, right: 6,
                      background: 'rgba(0,0,0,0.75)', borderRadius: 3,
                      padding: '2px 6px', fontSize: 10, fontFamily: 'var(--mono)',
                      color: 'var(--accent)',
                    }}>
                      {parseFloat(v['v.viral_score'] || 0).toFixed(2)}
                    </div>
                  </div>
                ) : (
                  <div style={{
                    height: 100, background: 'var(--bg3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Play size={24} style={{ color: 'var(--border2)' }} />
                  </div>
                )}

                <div style={{ padding: '10px 12px' }}>
                  {/* Title */}
                  <div style={{
                    fontSize: 12, fontWeight: 500, lineHeight: 1.4, marginBottom: 6,
                    overflow: 'hidden', display: '-webkit-box',
                    WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  }}>
                    {v['v.title'] || '(no title)'}
                  </div>

                  {/* Creator */}
                  {v.creator_name && (
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <TrendingUp size={10} /> {v.creator_name}
                    </div>
                  )}

                  {/* Stats */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {(v['v.view_count'] || 0).toLocaleString()} views
                    </span>
                    <span className="tag" style={{
                      color: CAT_COLORS[v['v.category']] || 'var(--muted)',
                      borderColor: CAT_COLORS[v['v.category']] || 'var(--border)',
                    }}>
                      {(v['v.category'] || '').replace('_', ' ')}
                    </span>
                  </div>

                  {/* Brief headline */}
                  {v.brief_headline && (
                    <div style={{
                      fontSize: 10, color: 'var(--amber)', padding: '5px 8px',
                      background: 'rgba(255,184,0,0.06)', borderRadius: 4,
                      borderLeft: '2px solid var(--amber)', marginBottom: 6,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {v.brief_headline}
                    </div>
                  )}

                  <a href={v['v.url']} target="_blank" rel="noreferrer"
                    style={{ fontSize: 11, color: 'var(--muted)', display: 'flex',
                      alignItems: 'center', gap: 3 }}>
                    <ExternalLink size={10} /> {v['v.platform'] || 'youtube'}
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 24, alignItems: 'center' }}>
            <button className="btn-ghost" onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}>&#8592; Prev</button>
            <span style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
              Page {page + 1}
            </span>
            <button className="btn-ghost" onClick={() => setPage(p => p + 1)}
              disabled={videos.length < limit}>Next</button>
          </div>
        </>
      )}
    </div>
  );
}

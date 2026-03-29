import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity, Database, Layers, ShieldAlert, Zap, TrendingUp } from 'lucide-react';
import api from '../api.jsx';

const COLORS = ['#00e5ff', '#7b61ff', '#00ff88', '#ffb800', '#ff4757'];

const CAT_LABELS = {
  sports_archive: 'Sports',
  news_broadcast: 'News',
  production_broll: 'B-Roll',
  documentary: 'Documentary',
  entertainment: 'Entertainment',
};

export default function Dashboard({ stats, pipeline }) {
  const { data: cats } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.getCategories().then(r => r.data),
  });

  const { data: hooksData } = useQuery({
    queryKey: ['top-hooks'],
    queryFn: () => api.getTopHooks({ limit: 5 }).then(r => r.data),
  });

  const { data: structData } = useQuery({
    queryKey: ['structure'],
    queryFn: () => api.getStructureAnalysis().then(r => r.data),
  });

  const catData = (cats?.categories || []).map((c, i) => ({
    name: CAT_LABELS[c.key] || c.key,
    target: c.target_count,
    color: COLORS[i % COLORS.length],
  }));

  const segDist = (structData?.distribution || []).map((d, i) => ({
    name: d.type,
    count: d.count,
    avg: parseFloat((d.avg_viral_score || 0).toFixed(3)),
    color: COLORS[i % COLORS.length],
  }));

  const metrics = [
    { label: 'Total Videos', val: stats?.videos ?? 0, icon: Database, color: 'var(--accent)' },
    { label: 'Scene Segments', val: stats?.scenes ?? 0, icon: Layers, color: 'var(--accent2)' },
    { label: 'Creators', val: stats?.creators ?? 0, icon: TrendingUp, color: 'var(--green)' },
    { label: 'Trend Tags', val: stats?.trends ?? 0, icon: Activity, color: 'var(--amber)' },
    { label: 'Compliance Flags', val: stats?.flags ?? 0, icon: ShieldAlert, color: 'var(--red)' },
    { label: 'Ad Briefs', val: stats?.briefs ?? 0, icon: Zap, color: 'var(--accent)' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Viral Video Intelligence</div>
        <div className="page-subtitle">
          TwelveLabs x Neo4j x ZeroClick.ai  -  NAB 2026 Hackathon
        </div>
      </div>

      {/* Pipeline status */}
      {pipeline && (
        <div className="card-sm" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: pipeline.queue_depth > 0 ? 'var(--amber)' : 'var(--green)',
              animation: pipeline.queue_depth > 0 ? 'pulse 1s infinite' : 'none',
              display: 'inline-block',
            }} />
            <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
              {pipeline.queue_depth > 0 ? `Processing: ${pipeline.queue_depth} videos queued` : 'Pipeline idle'}
            </span>
          </div>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            Completed: <strong style={{ color: 'var(--green)' }}>{pipeline.completed_jobs ?? 0}</strong>
          </span>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            Failed: <strong style={{ color: 'var(--red)' }}>{pipeline.failed_jobs ?? 0}</strong>
          </span>
        </div>
      )}

      {/* Metrics grid */}
      <div className="metrics-grid">
        {metrics.map(({ label, val, icon: Icon, color }) => (
          <div className="metric-card" key={label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div className="metric-label">{label}</div>
                <div className="metric-val" style={{ color }}>{val.toLocaleString()}</div>
              </div>
              <Icon size={18} style={{ color, opacity: 0.5 }} />
            </div>
          </div>
        ))}
      </div>

      <div className="two-col" style={{ marginBottom: 20 }}>
        {/* Category targets */}
        <div className="card">
          <div className="section-title">Content Mix</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={catData} barSize={28}>
              <XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: 'var(--text)' }}
                itemStyle={{ color: 'var(--accent)' }}
              />
              <Bar dataKey="target" radius={[3, 3, 0, 0]}>
                {catData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Segment type distribution */}
        <div className="card">
          <div className="section-title">Segment Distribution</div>
          {segDist.length === 0 ? (
            <div className="empty" style={{ padding: 60 }}>Run pipeline to see segments</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={segDist} dataKey="count" nameKey="name"
                  cx="50%" cy="50%" outerRadius={80}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={{ stroke: 'var(--muted)' }}
                >
                  {segDist.map((entry, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top hooks */}
      <div className="card">
        <div className="section-title">Top Hook Moments by Viral Score</div>
        {!hooksData?.hooks?.length ? (
          <div className="empty">No hook segments yet  -  start the pipeline to index videos</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Hook Start</th>
                  <th>Viral Score</th>
                  <th>Views</th>
                </tr>
              </thead>
              <tbody>
                {hooksData.hooks.slice(0, 8).map((h, i) => (
                  <tr key={i}>
                    <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={h['v.url']} target="_blank" rel="noreferrer"
                        style={{ color: 'var(--accent)' }}>
                        {h['v.title'] || '(no title)'}
                      </a>
                    </td>
                    <td><span className="tag">{h['v.category']}</span></td>
                    <td className="mono" style={{ fontSize: 12 }}>{parseFloat(h['s.t_start'] || 0).toFixed(1)}s</td>
                    <td>
                      <div className="score-bar-wrap">
                        <div className="score-bar">
                          <div className="score-bar-fill"
                            style={{ width: `${(h['s.viral_segment_score'] || 0) * 100}%` }} />
                        </div>
                        <span className="score-num">
                          {parseFloat(h['s.viral_segment_score'] || 0).toFixed(2)}
                        </span>
                      </div>
                    </td>
                    <td className="mono" style={{ fontSize: 12 }}>
                      {(h['v.view_count'] || 0).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

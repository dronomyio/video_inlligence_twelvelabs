import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Zap, ExternalLink, TrendingUp, DollarSign, Radio } from 'lucide-react';
import api from '../api.jsx';

const DEFAULT_BRIEF = {
  name: 'Q2 Cookware Campaign',
  advertiser: 'HexClad',
  vertical: 'kitchenware',
  target_audience: 'food enthusiasts 25-44',
  budget_usd: 10000,
  max_cpm: 4.5,
  brand_safety_level: 'standard',
  preferred_categories: ['food_cooking'],
  ad_format: 'both',
  campaign_objective: 'awareness',
  activate_on_networks: false,
  networks: ['gam', 'ttd'],
};

function CampaignForm({ onSubmit, loading }) {
  const [brief, setBrief] = useState(DEFAULT_BRIEF);

  const update = (k, v) => setBrief(b => ({ ...b, [k]: v }));

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="section-title">New Campaign Brief - Opus 4.6 Matcher</div>
      <div className="two-col" style={{ gap: 12, marginBottom: 12 }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Campaign name</label>
          <input value={brief.name} onChange={e => update('name', e.target.value)} style={{ width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Advertiser</label>
          <input value={brief.advertiser} onChange={e => update('advertiser', e.target.value)} style={{ width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Vertical</label>
          <select value={brief.vertical} onChange={e => update('vertical', e.target.value)} style={{ width: '100%' }}>
            <option value="kitchenware">Kitchenware</option>
            <option value="CPG">CPG</option>
            <option value="sports_brands">Sports brands</option>
            <option value="consumer_electronics">Consumer electronics</option>
            <option value="wellness">Wellness</option>
            <option value="ecommerce">Ecommerce</option>
            <option value="energy_drinks">Energy drinks</option>
            <option value="beauty">Beauty</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Target audience</label>
          <input value={brief.target_audience} onChange={e => update('target_audience', e.target.value)} style={{ width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Budget USD</label>
          <input type="number" value={brief.budget_usd} onChange={e => update('budget_usd', parseFloat(e.target.value))} style={{ width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Max CPM $</label>
          <input type="number" step="0.5" value={brief.max_cpm} onChange={e => update('max_cpm', parseFloat(e.target.value))} style={{ width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Brand safety</label>
          <select value={brief.brand_safety_level} onChange={e => update('brand_safety_level', e.target.value)} style={{ width: '100%' }}>
            <option value="strict">Strict</option>
            <option value="standard">Standard</option>
            <option value="relaxed">Relaxed</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Objective</label>
          <select value={brief.campaign_objective} onChange={e => update('campaign_objective', e.target.value)} style={{ width: '100%' }}>
            <option value="awareness">Awareness</option>
            <option value="consideration">Consideration</option>
            <option value="conversion">Conversion</option>
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, padding: '10px 12px', background: 'var(--bg2)', borderRadius: 6, border: '1px solid var(--border)' }}>
        <input type="checkbox" id="activate" checked={brief.activate_on_networks}
          onChange={e => update('activate_on_networks', e.target.checked)} />
        <label htmlFor="activate" style={{ fontSize: 12, cursor: 'pointer' }}>
          Activate on ad networks after matching (creates live GAM line items + TTD PMP deals)
        </label>
        {brief.activate_on_networks && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            {['gam', 'ttd'].map(n => (
              <label key={n} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, cursor: 'pointer' }}>
                <input type="checkbox" checked={brief.networks.includes(n)}
                  onChange={e => update('networks', e.target.checked
                    ? [...brief.networks, n]
                    : brief.networks.filter(x => x !== n))} />
                {n.toUpperCase()}
              </label>
            ))}
          </div>
        )}
      </div>

      <button className="btn-primary" onClick={() => onSubmit(brief)} disabled={loading}
        style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Radio size={14} />
        {loading ? 'Opus 4.6 reasoning...' : 'Match Campaign with Opus 4.6'}
      </button>
    </div>
  );
}

function MediaPlanResult({ plan, campaignId }) {
  const placements = plan?.placements || [];
  const excluded = plan?.placements_excluded || [];

  return (
    <div>
      {plan?.executive_summary && (
        <div style={{ padding: '12px 14px', background: 'rgba(123,97,255,.08)', border: '1px solid rgba(123,97,255,.2)', borderRadius: 8, fontSize: 12, color: 'var(--text)', lineHeight: 1.6, marginBottom: 16 }}>
          <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--purple)', fontFamily: 'var(--mono)', display: 'block', marginBottom: 5 }}>Opus 4.6 Executive Summary</span>
          {plan.executive_summary}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 16 }}>
        <div className="metric-card">
          <div className="metric-label">Est. Reach</div>
          <div className="metric-val" style={{ color: 'var(--cyan)', fontSize: 20 }}>
            {(plan?.total_estimated_reach || 0).toLocaleString()}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Est. Spend</div>
          <div className="metric-val" style={{ color: 'var(--amber)', fontSize: 20 }}>
            ${(plan?.total_estimated_spend || 0).toLocaleString()}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Audience Match</div>
          <div className="metric-val" style={{ color: 'var(--green)', fontSize: 20 }}>
            {((plan?.weighted_audience_match || 0) * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <div className="section-title">Ranked Placements ({placements.length})</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
        {placements.map((p, i) => (
          <div key={i} className="card" style={{ borderLeft: '3px solid var(--amber)', padding: '12px 14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--muted)' }}>#{p.rank}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{p.video_title}</span>
                  <span className="tag">{p.category}</span>
                  <span className="badge" style={{ background: 'rgba(0,229,255,.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,.2)', fontSize: 9 }}>
                    {p.ad_format}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6, display: 'flex', gap: 12 }}>
                  <span>Placement: <strong style={{ color: 'var(--text)' }}>{p.timestamp_seconds?.toFixed(1)}s</strong></span>
                  <span>Reach: <strong style={{ color: 'var(--text)' }}>{(p.estimated_reach || 0).toLocaleString()}</strong></span>
                  <span>Spend: <strong style={{ color: 'var(--amber)' }}>${(p.estimated_spend || 0).toFixed(0)}</strong></span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg2)', borderRadius: 5, padding: '7px 10px', lineHeight: 1.5 }}>
                  <span style={{ color: 'var(--purple)', fontWeight: 600 }}>Opus reasoning: </span>
                  {p.reasoning}
                </div>
                {p.caveats && (
                  <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 5 }}>- {p.caveats}</div>
                )}
              </div>
              <div style={{ textAlign: 'right', minWidth: 80 }}>
                <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.07em', fontFamily: 'var(--mono)', marginBottom: 3 }}>Match</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>
                  {((p.audience_match_score || 0) * 100).toFixed(0)}%
                </div>
                <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 4 }}>CPM ${(p.estimated_cpm || 0).toFixed(2)}</div>
                {p.video_url && (
                  <a href={p.video_url} target="_blank" rel="noreferrer"
                    style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'flex-end', marginTop: 6 }}>
                    <ExternalLink size={10} /> Video
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {excluded.length > 0 && (
        <div>
          <div className="section-title" style={{ color: 'var(--red)' }}>Excluded ({excluded.length})</div>
          {excluded.map((e, i) => (
            <div key={i} style={{ fontSize: 11, color: 'var(--muted)', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{e.video_id}</span>
              {'  -  '}
              <span style={{ color: 'var(--red)' }}>{e.reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Campaigns() {
  const [activeResult, setActiveResult] = useState(null);
  const qc = useQueryClient();

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => api.getCampaigns().then(r => r.data),
  });

  const { data: revenue } = useQuery({
    queryKey: ['revenue'],
    queryFn: () => api.getRevenue().then(r => r.data),
  });

  const matchMutation = useMutation({
    mutationFn: (brief) => api.matchCampaign(brief).then(r => r.data),
    onSuccess: (data) => {
      setActiveResult(data);
      qc.invalidateQueries(['campaigns']);
    },
  });

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Campaign Matching</div>
        <div className="page-subtitle">
          Opus 4.6 reasons across 500 videos - ranked media plan - one-click GAM + TTD activation
        </div>
      </div>

      {revenue && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 20 }}>
          <div className="metric-card">
            <div className="metric-label">Total Revenue</div>
            <div className="metric-val" style={{ color: 'var(--green)', fontSize: 18 }}>
              ${(revenue.total_revenue_usd || 0).toLocaleString()}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Impressions</div>
            <div className="metric-val" style={{ fontSize: 18 }}>
              {(revenue.total_impressions || 0).toLocaleString()}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Active Deals</div>
            <div className="metric-val" style={{ color: 'var(--amber)', fontSize: 18 }}>
              {revenue.total_deals || 0}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Platforms</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
              {(revenue.by_platform || []).map(p => (
                <span key={p.platform} className="badge" style={{ background: 'rgba(0,229,255,.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,.2)', fontSize: 9 }}>
                  {p.platform === 'the_trade_desk' ? 'TTD' : 'GAM'}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <CampaignForm
        onSubmit={(brief) => matchMutation.mutate(brief)}
        loading={matchMutation.isPending}
      />

      {matchMutation.isPending && (
        <div className="loading">
          <div className="spinner" />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
            Opus 4.6 reasoning across 500 videos with extended thinking...
          </span>
        </div>
      )}

      {matchMutation.isError && (
        <div style={{ color: 'var(--red)', fontSize: 13, padding: 16, background: 'rgba(255,68,85,.08)', border: '1px solid rgba(255,68,85,.2)', borderRadius: 8, marginBottom: 16 }}>
          {matchMutation.error?.response?.data?.detail || 'Campaign matching failed. Check ANTHROPIC_API_KEY.'}
        </div>
      )}

      {activeResult && !matchMutation.isPending && (
        <div>
          <div className="section-title">
            Campaign <span style={{ color: 'var(--cyan)', fontFamily: 'var(--mono)' }}>{activeResult.campaign_id}</span>
            {activeResult.network_activation && Object.keys(activeResult.network_activation).length > 0 && (
              <span style={{ marginLeft: 10 }}>
                {Object.keys(activeResult.network_activation).map(n => (
                  <span key={n} className="badge" style={{ background: 'rgba(0,232,122,.1)', color: 'var(--green)', border: '1px solid rgba(0,232,122,.2)', marginLeft: 4 }}>
                    {n.toUpperCase()} activated
                  </span>
                ))}
              </span>
            )}
          </div>
          <MediaPlanResult plan={activeResult.media_plan} campaignId={activeResult.campaign_id} />
        </div>
      )}

      {!activeResult && !matchMutation.isPending && campaigns?.campaigns?.length > 0 && (
        <div>
          <div className="section-title">Previous Campaigns</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th><th>Advertiser</th><th>Vertical</th>
                  <th>Budget</th><th>Placements</th><th>Est. Reach</th><th>Match</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.campaigns.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c['c.name']}</td>
                    <td style={{ fontSize: 12 }}>{c['c.advertiser']}</td>
                    <td><span className="tag">{c['c.vertical']}</span></td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>${(c['c.budget_usd'] || 0).toLocaleString()}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.placement_count}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{(c['c.total_estimated_reach'] || 0).toLocaleString()}</td>
                    <td>
                      <div className="score-bar-wrap">
                        <div className="score-bar">
                          <div className="score-bar-fill" style={{ width: `${(c['c.weighted_audience_match'] || 0) * 100}%`, background: 'var(--green)' }} />
                        </div>
                        <span className="score-num">{((c['c.weighted_audience_match'] || 0) * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

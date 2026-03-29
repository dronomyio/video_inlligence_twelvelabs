import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Wallet, Zap, Copy, CheckCircle, ExternalLink, Shield } from 'lucide-react';
import api from '../api.jsx';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--green)' : 'var(--muted)', padding: '0 4px' }}>
      {copied ? <CheckCircle size={12} /> : <Copy size={12} />}
    </button>
  );
}

const QUERY_TYPES = [
  { key: 'semantic_search',    label: 'Semantic Search',    desc: 'Find specific moments across 500 videos' },
  { key: 'campaign_match',     label: 'Campaign Match',     desc: 'Opus 4.6 full media plan' },
  { key: 'trend_detect',       label: 'Trend Report',       desc: 'Opus 4.6 emerging pattern detection' },
  { key: 'brief_lookup',       label: 'Brief Lookup',       desc: 'Fetch a ZeroClick advertiser brief' },
  { key: 'compliance_flags',   label: 'Compliance Check',   desc: 'Run rules-based content review' },
  { key: 'top_hooks',          label: 'Top Hooks',          desc: 'Viral hook moment rankings' },
];

export default function Payments() {
  const [selectedType, setSelectedType] = useState('semantic_search');
  const [intentResult, setIntentResult] = useState(null);
  const [verifyId, setVerifyId] = useState('');
  const [verifyResult, setVerifyResult] = useState(null);

  const { data: wallet, refetch: refetchWallet } = useQuery({
    queryKey: ['circle-wallet'],
    queryFn: () => api.getCircleWallet().then(r => r.data),
    refetchInterval: 30000,
  });

  const { data: x402Stats } = useQuery({
    queryKey: ['x402-stats'],
    queryFn: () => api.getX402Stats().then(r => r.data),
    refetchInterval: 15000,
  });

  const { data: pricing } = useQuery({
    queryKey: ['x402-pricing'],
    queryFn: () => api.getX402Pricing().then(r => r.data),
  });

  const { data: txns } = useQuery({
    queryKey: ['circle-txns'],
    queryFn: () => api.getCircleTransactions().then(r => r.data),
    refetchInterval: 30000,
  });

  const { data: mcpManifest } = useQuery({
    queryKey: ['mcp-manifest'],
    queryFn: () => api.getMCPManifest().then(r => r.data),
  });

  const intentMutation = useMutation({
    mutationFn: (qt) => api.createPaymentIntent(qt).then(r => r.data),
    onSuccess: setIntentResult,
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, qt }) => api.verifyPayment(id, qt).then(r => r.data),
    onSuccess: setVerifyResult,
  });

  const totalUsdc = x402Stats?.total_revenue_usdc || 0;
  const isSimulated = wallet?.status === 'simulated' || wallet?.environment?.includes('simulated');

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Circle / x402 Payments</div>
        <div className="page-sub">
          USDC micropayment layer on Circle Arc testnet  -  AI agents pay per query, no subscription needed
        </div>
      </div>

      {/* Status banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
        background: isSimulated ? 'rgba(255,184,0,.06)' : 'rgba(0,232,122,.06)',
        border: `1px solid ${isSimulated ? 'rgba(255,184,0,.2)' : 'rgba(0,232,122,.2)'}`,
        borderRadius: 7, marginBottom: 20, fontSize: 12,
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: isSimulated ? 'var(--amber)' : 'var(--green)', display: 'inline-block', flexShrink: 0 }} />
        <span style={{ color: isSimulated ? 'var(--amber)' : 'var(--green)', fontFamily: 'var(--mono)', fontWeight: 700 }}>
          {isSimulated ? 'SIMULATION MODE' : 'LIVE  -  CIRCLE ARC TESTNET'}
        </span>
        <span style={{ color: 'var(--muted)' }}>
          {isSimulated
            ? 'Set CIRCLE_API_KEY + CIRCLE_WALLET_ID in .env to activate live wallet'
            : `Wallet: ${wallet?.wallet_id}`}
        </span>
        {!isSimulated && (
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', color: 'var(--green)', fontWeight: 700 }}>
            {wallet?.usdc_balance?.toFixed(2)} USDC
          </span>
        )}
      </div>

      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 20 }}>
        <div className="metric-card">
          <div className="metric-label">Wallet Balance</div>
          <div className="metric-val" style={{ color: 'var(--green)', fontSize: 20 }}>
            {(wallet?.usdc_balance || 0).toFixed(2)}
          </div>
          <div className="metric-sub">USDC</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total x402 Revenue</div>
          <div className="metric-val" style={{ color: 'var(--cyan)', fontSize: 20 }}>
            {totalUsdc.toFixed(4)}
          </div>
          <div className="metric-sub">USDC earned</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Enforcement</div>
          <div className="metric-val" style={{ fontSize: 16, color: pricing?.enforcement ? 'var(--green)' : 'var(--amber)' }}>
            {pricing?.enforcement ? 'ON' : 'OFF'}
          </div>
          <div className="metric-sub">{pricing?.enforcement ? 'paying callers only' : 'demo mode'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Chain</div>
          <div className="metric-val" style={{ fontSize: 16, color: 'var(--purple)' }}>ARB</div>
          <div className="metric-sub">Arbitrum USDC</div>
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 20, gap: 16 }}>

        {/* Pricing */}
        <div className="card">
          <div className="card-title">x402 pricing per query</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {QUERY_TYPES.map(qt => (
              <div key={qt.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{qt.label}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>{qt.desc}</div>
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--amber)' }}>
                  ${(pricing?.pricing?.[qt.key] || 0).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Revenue by query type */}
        <div className="card">
          <div className="card-title">Revenue by query type</div>
          {!(x402Stats?.by_query_type?.length) ? (
            <div className="empty" style={{ padding: 32 }}>No payments recorded yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(x402Stats.by_query_type || []).map((row, i) => (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text)' }}>{row.query_type}</span>
                    <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--amber)' }}>
                      ${(row.total_usdc || 0).toFixed(4)}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="score-bar" style={{ flex: 1 }}>
                      <div className="score-bar-fill" style={{
                        width: `${totalUsdc > 0 ? (row.total_usdc / totalUsdc * 100) : 0}%`,
                        background: 'var(--amber)',
                      }} />
                    </div>
                    <span style={{ fontSize: 10, color: 'var(--muted)', minWidth: 40, textAlign: 'right' }}>
                      {row.count}x
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 20, gap: 16 }}>

        {/* Create payment intent */}
        <div className="card">
          <div className="card-title">Create payment intent</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <select value={selectedType} onChange={e => setSelectedType(e.target.value)} style={{ width: '100%' }}>
              {QUERY_TYPES.map(qt => (
                <option key={qt.key} value={qt.key}>{qt.label}  -  ${(pricing?.pricing?.[qt.key] || 0).toFixed(2)} USDC</option>
              ))}
            </select>
            <button className="btn-primary" onClick={() => intentMutation.mutate(selectedType)} disabled={intentMutation.isPending}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Wallet size={13} />
              {intentMutation.isPending ? 'Creating...' : 'Generate Deposit Address'}
            </button>

            {intentResult && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 7, padding: 12 }}>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.07em', fontFamily: 'var(--mono)' }}>
                  Deposit address (ARB)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <code style={{ fontSize: 10, color: 'var(--cyan)', flex: 1, wordBreak: 'break-all', lineHeight: 1.4 }}>
                    {intentResult.deposit_address}
                  </code>
                  <CopyButton text={intentResult.deposit_address} />
                </div>
                <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--muted)' }}>
                  <span>Amount: <strong style={{ color: 'var(--amber)' }}>{intentResult.amount_usdc} USDC</strong></span>
                  <span>Intent: <code style={{ fontSize: 10, color: 'var(--text)' }}>{intentResult.intent_id?.slice(0, 16)}...</code></span>
                </div>
                {intentResult.status === 'simulated' && (
                  <div style={{ marginTop: 8, fontSize: 10, color: 'var(--amber)', background: 'rgba(255,184,0,.07)', padding: '5px 8px', borderRadius: 4 }}>
                    Demo mode: use <code>sim_anything</code> as transfer_id to verify
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Verify payment */}
        <div className="card">
          <div className="card-title">Verify transfer</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input value={verifyId} onChange={e => setVerifyId(e.target.value)}
              placeholder="transfer_id or sim_anything for demo..."
              onKeyDown={e => e.key === 'Enter' && verifyMutation.mutate({ id: verifyId, qt: selectedType })}
            />
            <button className="btn-primary" onClick={() => verifyMutation.mutate({ id: verifyId, qt: selectedType })}
              disabled={verifyMutation.isPending || !verifyId}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Shield size={13} />
              {verifyMutation.isPending ? 'Verifying...' : 'Verify Payment'}
            </button>

            {verifyResult && (
              <div style={{
                padding: 12, borderRadius: 7, border: `1px solid ${verifyResult.verified ? 'rgba(0,232,122,.3)' : 'rgba(255,68,85,.3)'}`,
                background: verifyResult.verified ? 'rgba(0,232,122,.06)' : 'rgba(255,68,85,.06)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  {verifyResult.verified
                    ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                    : <Shield size={14} style={{ color: 'var(--red)' }} />}
                  <span style={{ fontSize: 13, fontWeight: 600, color: verifyResult.verified ? 'var(--green)' : 'var(--red)' }}>
                    {verifyResult.verified ? 'Payment verified  -  access granted' : 'Payment not verified'}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                  Received: <strong style={{ color: 'var(--text)' }}>{verifyResult.amount_received} USDC</strong>
                  <span style={{ marginLeft: 12 }}>Status: <code style={{ fontSize: 10 }}>{verifyResult.status}</code></span>
                </div>
                {verifyResult.verified && (
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--cyan)' }}>
                    Add header to your request: <code style={{ fontSize: 10 }}>X-Payment-Transfer-Id: {verifyResult.transfer_id}</code>
                    <CopyButton text={`X-Payment-Transfer-Id: ${verifyResult.transfer_id}`} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* MCP manifest */}
      {mcpManifest && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">MCP server manifest  -  AI agent discovery</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, lineHeight: 1.6 }}>
            AI buying agents (Claude, GPT agents, TTD algorithmic buyers) discover your API tools and prices at
            <code style={{ fontSize: 11, color: 'var(--cyan)', margin: '0 4px' }}>/.well-known/mcp.json</code>
             -  same pattern as MEV Shield's x402 architecture.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(mcpManifest.tools || []).map((tool, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', background: 'var(--bg2)', borderRadius: 6, border: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--cyan)', marginBottom: 2 }}>{tool.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>{tool.description?.slice(0, 80)}...</div>
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: 'var(--amber)', marginLeft: 16, flexShrink: 0 }}>
                  ${tool.price_usdc?.toFixed(2)} USDC
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent transactions */}
      {txns?.transactions?.length > 0 && (
        <div className="card">
          <div className="card-title">Recent USDC inflows</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Transfer ID</th><th>Amount</th><th>Status</th><th>Date</th></tr>
              </thead>
              <tbody>
                {txns.transactions.map((tx, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--cyan)' }}>{tx.id}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--amber)' }}>
                      {tx.amount?.amount} {tx.amount?.currency}
                    </td>
                    <td><span className={`badge ${tx.status === 'complete' ? 'b-payoff' : 'b-cta'}`}>{tx.status}</span></td>
                    <td style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {tx.createDate ? new Date(tx.createDate).toLocaleDateString() : ' - '}
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

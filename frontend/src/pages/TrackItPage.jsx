import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { GitBranch, FileText, Shield, Activity, CheckCircle, Clock, AlertTriangle } from 'lucide-react';
import api from '../api.jsx';

const STATE_COLORS = {
  video_discovered:   'var(--cyan)',
  tl_indexed:         'var(--purple)',
  segments_extracted: 'var(--purple)',
  compliance_checked: 'var(--red)',
  brief_generated:    'var(--amber)',
  creative_generated: 'var(--green)',
  deal_activated:     'var(--amber)',
  payment_recorded:   'var(--green)',
};

function PipelineTracker({ states, completed = [] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {states.map((state, i) => {
        const done = completed.includes(state);
        const isLast = i === states.length - 1;
        return (
          <div key={state} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                background: done ? STATE_COLORS[state] || 'var(--green)' : 'var(--bg3)',
                border: `1px solid ${done ? STATE_COLORS[state] || 'var(--green)' : 'var(--border2)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all .3s',
              }}>
                {done
                  ? <CheckCircle size={12} color="var(--bg)" />
                  : <Clock size={10} color="var(--muted)" />
                }
              </div>
              {!isLast && (
                <div style={{
                  width: 2, height: 20,
                  background: done ? 'var(--border2)' : 'var(--border)',
                  margin: '2px 0',
                }} />
              )}
            </div>
            <div style={{ paddingBottom: isLast ? 0 : 18 }}>
              <div style={{
                fontSize: 12, fontFamily: 'var(--mono)',
                color: done ? 'var(--text)' : 'var(--muted)',
                fontWeight: done ? 600 : 400,
              }}>
                {state.replace(/_/g, ' ')}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function TrackItPage() {
  const [videoId, setVideoId] = useState('');
  const [workflowId, setWorkflowId] = useState('');
  const [workflowResult, setWorkflowResult] = useState(null);
  const [mamResult, setMamResult] = useState(null);
  const [qoeResult, setQoeResult] = useState(null);
  const [activeTab, setActiveTab] = useState('workflow');

  const { data: statesData } = useQuery({
    queryKey: ['pipeline-states'],
    queryFn: () => api.getTrackItPipelineStates().then(r => r.data),
  });

  const { data: auditData, refetch: refetchAudit } = useQuery({
    queryKey: ['audit', videoId],
    queryFn: () => api.getAuditTrail(videoId || undefined).then(r => r.data),
    refetchInterval: 10000,
  });

  const { data: workflowStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['workflow-status', workflowId],
    queryFn: () => workflowId ? api.getWorkflowStatus(workflowId).then(r => r.data) : null,
    enabled: !!workflowId,
    refetchInterval: 5000,
  });

  const submitMutation = useMutation({
    mutationFn: (vid) => api.submitWorkflow(vid).then(r => r.data),
    onSuccess: (data) => {
      setWorkflowResult(data);
      setWorkflowId(data.workflow_id);
    },
  });

  const mamMutation = useMutation({
    mutationFn: (vid) => api.pushMAM(vid).then(r => r.data),
    onSuccess: setMamResult,
  });

  const qoeMutation = useMutation({
    mutationFn: (vid) => api.getQoE(vid).then(r => r.data),
    onSuccess: setQoeResult,
  });

  const pipelineStates = statesData?.states || [];
  const completedStates = workflowStatus?.completed_states || [];
  const progressPct = workflowStatus?.progress_pct || 0;

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">TrackIt Workflow</div>
        <div className="page-sub">
          Pipeline orchestration - SMPTE MAM metadata - CDN registration - Broadcaster audit trail
        </div>
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px',
        marginBottom: 20, background: 'rgba(0,212,170,.06)',
        border: '1px solid rgba(0,212,170,.2)', borderRadius: 7, fontSize: 12,
        color: 'var(--muted)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%',
          background: 'var(--teal)', display: 'inline-block' }} />
        <span style={{ color: 'var(--teal)', fontFamily: 'var(--mono)', fontWeight: 700 }}>
          TrackIt
        </span>
        AWS Advanced Tier M&amp;E Partner - workflow orchestration, MAM integration, CDN, broadcaster audit trail
        <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--border2)' }}>
          Local execution when TRACKIT_API_KEY not set
        </span>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        {['workflow', 'mam', 'qoe', 'audit'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px', fontSize: 12, cursor: 'pointer',
              background: 'none', border: 'none',
              borderBottom: `2px solid ${activeTab === tab ? 'var(--teal)' : 'transparent'}`,
              color: activeTab === tab ? 'var(--teal)' : 'var(--muted)',
              transition: 'all .15s', textTransform: 'capitalize',
            }}>
            {tab === 'mam' ? 'MAM' : tab === 'qoe' ? 'QoE' : tab}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        <input className="search-input" placeholder="Enter video_id..."
          value={videoId} onChange={e => setVideoId(e.target.value)} style={{ maxWidth: 320 }} />
      </div>

      {activeTab === 'workflow' && (
        <div className="two-col" style={{ gap: 16 }}>
          <div className="card">
            <div className="section-title">Pipeline state machine</div>
            {pipelineStates.length > 0 ? (
              <PipelineTracker states={pipelineStates} completed={completedStates} />
            ) : (
              <div className="loading"><div className="spinner" />Loading states...</div>
            )}
            {workflowStatus && (
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between',
                  fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                  <span>Progress</span>
                  <span style={{ fontFamily: 'var(--mono)', color: 'var(--teal)' }}>{progressPct}%</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 2, background: 'var(--teal)',
                    width: `${progressPct}%`, transition: 'width .5s' }} />
                </div>
                <div style={{ marginTop: 8, fontSize: 11, display: 'flex', alignItems: 'center', gap: 6,
                  color: workflowStatus.status === 'complete' ? 'var(--green)' : 'var(--amber)' }}>
                  {workflowStatus.status === 'complete'
                    ? <CheckCircle size={12} />
                    : <Activity size={12} style={{ animation: 'pulse 1s infinite' }} />}
                  {workflowStatus.status}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-title">Submit workflow</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={() => videoId && submitMutation.mutate(videoId)}
                disabled={!videoId || submitMutation.isPending}>
                <GitBranch size={13} />
                {submitMutation.isPending ? 'Submitting...' : 'Submit to TrackIt'}
              </button>
              {workflowResult && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: 10, fontSize: 11 }}>
                  <div style={{ color: 'var(--teal)', fontFamily: 'var(--mono)', marginBottom: 4, fontWeight: 700 }}>
                    Workflow submitted
                  </div>
                  <div style={{ color: 'var(--muted)' }}>
                    ID: <code style={{ color: 'var(--text)', fontSize: 10 }}>{workflowResult.workflow_id}</code>
                  </div>
                  <div style={{ color: 'var(--muted)' }}>
                    Mode: <span style={{ color: 'var(--text)' }}>{workflowResult.mode || 'local'}</span>
                  </div>
                </div>
              )}
              {workflowId && (
                <div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6,
                    textTransform: 'uppercase', letterSpacing: '.08em', fontFamily: 'var(--mono)' }}>
                    Tracking: <code style={{ color: 'var(--cyan)' }}>{workflowId.slice(0, 24)}...</code>
                  </div>
                  <button className="btn-ghost" style={{ fontSize: 11, padding: '6px 12px' }}
                    onClick={() => refetchStatus()}>
                    Refresh status
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'mam' && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">Push SMPTE ST 2067 metadata to MAM</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.6 }}>
              Packages TwelveLabs scene labels, viral scores, compliance flags,
              and ZeroClick advertiser signals into broadcaster-standard metadata.
            </div>
            <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={() => videoId && mamMutation.mutate(videoId)}
              disabled={!videoId || mamMutation.isPending}>
              <FileText size={13} />
              {mamMutation.isPending ? 'Pushing...' : 'Push to MAM'}
            </button>
          </div>
          {mamResult && (
            <div className="card">
              <div className="section-title" style={{ color: 'var(--green)' }}>
                MAM record - {mamResult.asset_id || mamResult.record?.asset_id}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4,
                    textTransform: 'uppercase', letterSpacing: '.07em', fontFamily: 'var(--mono)' }}>Schema</div>
                  <div style={{ fontSize: 12, color: 'var(--text)' }}>{mamResult.record?.schema_version}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4,
                    textTransform: 'uppercase', letterSpacing: '.07em', fontFamily: 'var(--mono)' }}>Status</div>
                  <div style={{ fontSize: 12 }}>
                    <span className={`badge ${mamResult.status === 'pushed' ? 'b-payoff' : 'b-cta'}`}>
                      {mamResult.status}
                    </span>
                  </div>
                </div>
              </div>
              {mamResult.record?.compliance && (
                <div style={{ marginTop: 12, padding: '8px 10px', background: 'var(--bg2)', borderRadius: 6, fontSize: 11 }}>
                  <div style={{ color: 'var(--muted)', marginBottom: 4 }}>Compliance summary</div>
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <span>Total flags: <strong style={{ color: 'var(--text)' }}>{mamResult.record.compliance.total}</strong></span>
                    <span>Brand safe: <strong style={{ color: mamResult.record.compliance.brand_safe ? 'var(--green)' : 'var(--red)' }}>
                      {mamResult.record.compliance.brand_safe ? 'Yes' : 'No'}</strong></span>
                  </div>
                </div>
              )}
              {mamResult.mam_path && (
                <div style={{ marginTop: 8, fontSize: 10, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                  Written to: {mamResult.mam_path}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'qoe' && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">Quality of Experience metrics</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
              Proxy QoE score derived from viral score and duration.
            </div>
            <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={() => videoId && qoeMutation.mutate(videoId)}
              disabled={!videoId || qoeMutation.isPending}>
              <Activity size={13} />
              {qoeMutation.isPending ? 'Analysing...' : 'Compute QoE'}
            </button>
          </div>
          {qoeResult && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
              <div className="metric-card">
                <div className="metric-label">QoE Score</div>
                <div className="metric-val" style={{ color: qoeResult.qoe?.qoe_score > 0.7 ? 'var(--green)' : 'var(--amber)' }}>
                  {((qoeResult.qoe?.qoe_score || 0) * 100).toFixed(0)}
                </div>
                <div className="metric-sub">out of 100</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Est. VMAF</div>
                <div className="metric-val" style={{ color: 'var(--cyan)' }}>
                  {(qoeResult.qoe?.estimated_vmaf || 0).toFixed(1)}
                </div>
                <div className="metric-sub">proxy score</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Mobile Optimised</div>
                <div className="metric-val" style={{ fontSize: 16,
                  color: qoeResult.qoe?.mobile_optimised ? 'var(--green)' : 'var(--red)' }}>
                  {qoeResult.qoe?.mobile_optimised ? 'YES' : 'NO'}
                </div>
                <div className="metric-sub">under 60s duration</div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'audit' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              {auditData?.count || 0} audit records
              {videoId && <span> for <code style={{ color: 'var(--cyan)', fontSize: 11 }}>{videoId}</code></span>}
            </div>
            <button className="btn-ghost" style={{ fontSize: 11, padding: '5px 10px' }}
              onClick={() => refetchAudit()}>Refresh</button>
          </div>
          {!auditData?.records?.length ? (
            <div className="empty">
              <Shield size={24} style={{ color: 'var(--border2)', marginBottom: 8 }} />
              <div>No audit records yet - submit a workflow to start logging</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th><th>Workflow</th><th>Video</th><th>State</th><th>Data keys</th>
                  </tr>
                </thead>
                <tbody>
                  {[...(auditData.records || [])].reverse().map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                        {new Date(r.ts).toLocaleTimeString()}
                      </td>
                      <td style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                        {(r.workflow_id || '').slice(0, 18)}...
                      </td>
                      <td style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>
                        {(r.video_id || '').slice(0, 16)}
                      </td>
                      <td>
                        <span style={{ fontSize: 9, fontFamily: 'var(--mono)', fontWeight: 700,
                          color: STATE_COLORS[r.state] || 'var(--muted)', padding: '1px 5px',
                          background: `${STATE_COLORS[r.state] || 'var(--border)'}18`, borderRadius: 2 }}>
                          {(r.state || '').replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td style={{ fontSize: 10, color: 'var(--muted)' }}>
                        {(r.data?.data_keys || []).join(', ').slice(0, 40)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


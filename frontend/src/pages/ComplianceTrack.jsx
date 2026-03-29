import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle, XCircle, AlertCircle, Plus, Download, Clock } from 'lucide-react';
import api from '../api.jsx';
import { motion, AnimatePresence } from 'framer-motion';
import { PageWrap, FadeUp, StaggerList, StaggerItem, CountUp, AnimatedBar, ScanLine, PopIn, SeverityPing, TimelineReveal } from '../animations.jsx';

const SEV_CONFIG = {
  critical: { color:'#ff1744', bg:'#ff174422', label:'Critical', weight:10 },
  high:     { color:'#ff4455', bg:'#ff445522', label:'High',     weight:5  },
  medium:   { color:'#ffb800', bg:'#ffb80022', label:'Medium',   weight:2  },
  low:      { color:'#00bfa5', bg:'#00bfa522', label:'Low',      weight:1  },
};

const RULESETS = [
  { value:'broadcast_standards', label:'Broadcast Standards', desc:'FCC, alcohol, violence, decency' },
  { value:'brand_guidelines',    label:'Brand Guidelines',    desc:'Competitor brands, logos, messaging' },
  { value:'platform_policies',   label:'Platform Policies',   desc:'YouTube, TikTok, streaming policies' },
  { value:'all',                 label:'All Rulesets',        desc:'Full compliance scan' },
];

function RiskMeter({ score }) {
  const max    = 20;
  const pct    = Math.min(score / max, 1);
  const level  = score === 0 ? 'clean' : score <= 3 ? 'low' : score <= 8 ? 'medium' : score <= 15 ? 'high' : 'critical';
  const color  = { clean:'#00e87a', low:'#00bfa5', medium:'#ffb800', high:'#ff4455', critical:'#ff1744' }[level];
  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
        <span style={{ fontSize:11, color:'var(--muted)' }}>Risk score</span>
        <span style={{ fontSize:13, fontWeight:700, color, fontFamily:'var(--mono)' }}>
          {score}  -  {level.toUpperCase()}
        </span>
      </div>
      <div style={{ height:6, background:'var(--bg3)', borderRadius:3, overflow:'hidden' }}>
        <motion.div initial={{ width:0 }} animate={{ width:`${pct*100}%` }}
          transition={{ duration:0.8, ease:'easeOut' }}
          style={{ height:'100%', background:color, borderRadius:3 }} />
      </div>
    </div>
  );
}

function FlagCard({ flag, index }) {
  const [open, setOpen]     = useState(false);
  const [decision, setDecision] = useState('');
  const [reviewer, setReviewer] = useState('');
  const [note, setNote]     = useState('');
  const qc = useQueryClient();

  const sev    = flag['f.severity'] || flag.severity || 'medium';
  const cfg    = SEV_CONFIG[sev] || SEV_CONFIG.medium;
  const flagId = flag['f.flag_id'] || flag.flag_id || `flag_${index}`;

  const reviewMutation = useMutation({
    mutationFn: () => api.reviewCompliance(flagId, { decision, reviewer, note }),
    onSuccess:  () => qc.invalidateQueries(['flags']),
  });

  return (
    <motion.div initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }}
      transition={{ delay: index * 0.06 }}
      style={{ background:'var(--bg2)', borderRadius:7, padding:12, marginBottom:8,
               borderLeft:`3px solid ${cfg.color}` }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, cursor:'pointer' }}
           onClick={() => setOpen(o => !o)}>
        <SeverityPing severity={sev} />
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, color:'var(--text)', fontWeight:500 }}>
            {flag['f.explanation'] || flag.explanation || flag['f.rule'] || 'Compliance flag'}
          </div>
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:2, display:'flex', gap:12 }}>
            <span><Clock size={10} style={{ verticalAlign:'middle', marginRight:3 }} />
              {flag['f.t_start'] ?? flag.t_start ?? 0}s -- {flag['f.t_end'] ?? flag.t_end ?? 0}s
            </span>
            <span style={{ background:cfg.bg, color:cfg.color, padding:'1px 6px',
                           borderRadius:3, fontSize:10, fontWeight:700 }}>{cfg.label}</span>
            {flag['f.review_status'] && (
              <span style={{ color:'var(--green)', fontSize:10 }}>o {flag['f.review_status']}</span>
            )}
          </div>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }}>
          <AlertCircle size={16} color={cfg.color} />
        </motion.div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ height:0, opacity:0 }} animate={{ height:'auto', opacity:1 }}
            exit={{ height:0, opacity:0 }} transition={{ duration:0.25 }}
            style={{ overflow:'hidden' }}>
            <div style={{ paddingTop:12, borderTop:`1px solid ${cfg.color}33`, marginTop:10 }}>
              {/* Evidence */}
              {(flag['f.evidence'] || flag.evidence) && (
                <div style={{ marginBottom:8 }}>
                  <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase',
                                fontFamily:'var(--mono)', marginBottom:4 }}>Evidence</div>
                  <div style={{ fontSize:12, color:'var(--text)', background:'var(--bg3)',
                                borderRadius:4, padding:'6px 10px' }}>
                    {flag['f.evidence'] || flag.evidence}
                  </div>
                </div>
              )}
              {/* Remediation */}
              {(flag['f.remediation'] || flag.remediation) && (
                <div style={{ marginBottom:10 }}>
                  <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase',
                                fontFamily:'var(--mono)', marginBottom:4 }}>Remediation</div>
                  <div style={{ fontSize:12, color:'var(--amber)', background:'rgba(255,184,0,0.08)',
                                borderRadius:4, padding:'6px 10px' }}>
                    {flag['f.remediation'] || flag.remediation}
                  </div>
                </div>
              )}
              {/* Confidence */}
              <div style={{ marginBottom:10 }}>
                <div style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--mono)', marginBottom:4 }}>
                  Confidence * false positive risk: {flag['f.false_positive_risk'] || flag.false_positive_risk || 'medium'}
                </div>
                <AnimatedBar value={flag['f.confidence'] || flag.confidence || 0.75} color={cfg.color} />
              </div>
              {/* Human review */}
              <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                {[
                  { v:'approve',  l:'Confirm violation', color:'#ff4455', icon:CheckCircle },
                  { v:'reject',   l:'False positive',    color:'#00e87a', icon:XCircle },
                  { v:'escalate', l:'Escalate',          color:'#ffb800', icon:AlertTriangle },
                ].map(({ v, l, color, icon: Icon }) => (
                  <motion.button key={v}
                    onClick={() => { setDecision(v); reviewMutation.mutate(); }}
                    whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }}
                    style={{ background: decision===v ? `${color}22` : 'var(--bg3)',
                             border:`1px solid ${decision===v ? color : 'var(--border)'}`,
                             borderRadius:5, padding:'5px 12px', cursor:'pointer',
                             color, fontSize:11, display:'flex', alignItems:'center', gap:5 }}>
                    <Icon size={11} />{l}
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function AuditEntry({ entry, index }) {
  const statusColor = { approve:'var(--green)', reject:'var(--muted)', escalate:'var(--amber)' };
  return (
    <motion.div initial={{ opacity:0, x:-16 }} animate={{ opacity:1, x:0 }}
      transition={{ delay: index * 0.04 }}
      style={{ display:'flex', gap:12, padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
      <div style={{ width:2, background: statusColor[entry['f.review_status']] || 'var(--border)',
                    borderRadius:2, flexShrink:0 }} />
      <div style={{ flex:1 }}>
        <div style={{ fontSize:12, color:'var(--text)' }}>{entry['f.explanation'] || entry['f.rule']}</div>
        <div style={{ fontSize:10, color:'var(--muted)', marginTop:2, fontFamily:'var(--mono)' }}>
          {entry['f.review_status']} * {entry['f.reviewer'] || 'anonymous'} * {entry['f.ruleset']}
        </div>
      </div>
      <span style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--mono)' }}>
        {entry['f.t_start']?.toFixed(1)}s
      </span>
    </motion.div>
  );
}

export default function ComplianceTrack() {
  const [videoId, setVideoId]   = useState('');
  const [ruleset, setRuleset]   = useState('broadcast_standards');
  const [activeTab, setActiveTab] = useState('flags');
  const [scanResult, setScanResult] = useState(null);
  const [newRule, setNewRule]   = useState({ rule:'', severity:'high', category:'custom' });

  const { data: flagsData }   = useQuery({ queryKey:['flags'],   queryFn:() => api.getFlags({}).then(r=>r.data) });
  const { data: summary }     = useQuery({ queryKey:['summary'], queryFn:() => api.getComplianceSummary().then(r=>r.data) });
  const { data: rulesetsData} = useQuery({ queryKey:['rulesets'],queryFn:() => api.getRulesets().then(r=>r.data) });
  const { data: riskData }    = useQuery({ queryKey:['risk'],    queryFn:() => api.getRiskScores().then(r=>r.data) });
  const { data: auditData }   = useQuery({ queryKey:['audit'],   queryFn:() => api.getComplianceAudit().then(r=>r.data) });

  const scanMutation = useMutation({
    mutationFn: async () => {
      const res = await api.runComplianceExplain(videoId, ruleset);
      return res.data;
    },
    onSuccess: (data) => setScanResult(data),
  });

  const addRuleMutation = useMutation({
    mutationFn: () => api.createComplianceRule(newRule),
    onSuccess:  () => setNewRule({ rule:'', severity:'high', category:'custom' }),
  });

  const flags = flagsData?.flags || [];
  const totalFlags = flags.length;
  const criticalCount = flags.filter(f => (f['f.severity']||f.severity) === 'critical').length;
  const pendingReview = flags.filter(f => !(f['f.review_status']||f.review_status)).length;

  return (
    <PageWrap>
      <div className="page">
        <FadeUp>
          <div className="page-header">
            <div className="page-title">Compliance Guardian</div>
            <div className="page-sub">TwelveLabs Marengo + Pegasus + Opus 4.6  -  explainable compliance review</div>
          </div>
        </FadeUp>

        {/* Metric cards */}
        <FadeUp delay={0.06}>
          <div className="metrics">
            {[
              { label:'Total flags',    val:totalFlags,    color:'var(--amber)' },
              { label:'Critical',       val:criticalCount, color:'#ff1744' },
              { label:'Pending review', val:pendingReview, color:'var(--cyan)' },
              { label:'Brand safe',     val:Math.max(0,500-totalFlags), color:'var(--green)' },
            ].map(({ label, val, color }, i) => (
              <motion.div key={label} className="metric-card"
                initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
                transition={{ delay: i * 0.08 }}>
                <div className="metric-label">{label}</div>
                <div className="metric-val" style={{ color }}>
                  <CountUp to={val} />
                </div>
              </motion.div>
            ))}
          </div>
        </FadeUp>

        {/* Scan panel */}
        <FadeUp delay={0.14}>
          <div className="card">
            <div className="card-title">Compliance scan with explainability</div>
            <div style={{ display:'flex', gap:8, marginBottom:8 }}>
              <input value={videoId} onChange={e=>setVideoId(e.target.value)}
                placeholder="Video ID" style={{ flex:1, background:'var(--bg2)',
                border:'1px solid var(--border2)', borderRadius:6, padding:'8px 12px',
                color:'var(--text)', fontSize:13 }} />
              <select value={ruleset} onChange={e=>setRuleset(e.target.value)}
                style={{ background:'var(--bg2)', border:'1px solid var(--border2)', borderRadius:6,
                         padding:'8px 12px', color:'var(--text)', fontSize:13, minWidth:180 }}>
                {RULESETS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
              <motion.button onClick={() => scanMutation.mutate()}
                disabled={scanMutation.isPending || !videoId.trim()}
                whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
                style={{ background:'var(--amber)', color:'var(--bg)', border:'none', borderRadius:6,
                         padding:'8px 18px', fontWeight:700, cursor:'pointer', fontSize:13 }}>
                {scanMutation.isPending ? 'Scanning...' : 'Scan'}
              </motion.button>
            </div>
            <AnimatePresence>{scanMutation.isPending && <ScanLine />}</AnimatePresence>
          </div>
        </FadeUp>

        {/* Scan result */}
        <PopIn show={!!scanResult}>
          {scanResult && (
            <FadeUp>
              <div className="card">
                <div style={{ marginBottom:12 }}>
                  <RiskMeter score={scanResult.risk_score||0} />
                </div>
                <div style={{ fontSize:11, color:'var(--muted)', marginBottom:10, fontFamily:'var(--mono)' }}>
                  {scanResult.rules_checked} rules checked * {scanResult.violation_count} violations * {scanResult.ruleset}
                </div>
                {(scanResult.violations||[]).map((v,i) => (
                  <FlagCard key={i} flag={v} index={i} />
                ))}
                {scanResult.violation_count === 0 && (
                  <motion.div initial={{ scale:0.8, opacity:0 }} animate={{ scale:1, opacity:1 }}
                    style={{ display:'flex', alignItems:'center', gap:10, padding:'16px',
                             background:'rgba(0,232,122,0.08)', borderRadius:6 }}>
                    <ShieldCheck size={24} color="var(--green)" />
                    <span style={{ color:'var(--green)', fontWeight:600 }}>No violations detected  -  content is compliant</span>
                  </motion.div>
                )}
              </div>
            </FadeUp>
          )}
        </PopIn>

        {/* Tabs */}
        <FadeUp delay={0.18}>
          <div className="card">
            <div style={{ display:'flex', gap:0, borderBottom:'1px solid var(--border)', marginBottom:14 }}>
              {['flags','rules','risk','audit'].map(tab => (
                <motion.button key={tab} onClick={() => setActiveTab(tab)}
                  style={{ padding:'6px 14px', fontSize:11, cursor:'pointer', border:'none',
                           background:'transparent', fontFamily:'var(--mono)',
                           color: activeTab===tab ? 'var(--cyan)' : 'var(--muted)',
                           borderBottom: activeTab===tab ? '2px solid var(--cyan)' : '2px solid transparent' }}>
                  {tab.toUpperCase()}
                </motion.button>
              ))}
            </div>

            {/* Flags tab */}
            <AnimatePresence mode="wait">
              {activeTab==='flags' && (
                <motion.div key="flags" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                  {!flags.length && <div style={{ color:'var(--muted)', fontSize:13 }}>No flags yet  -  run a scan</div>}
                  {flags.slice(0,15).map((f,i) => <FlagCard key={i} flag={f} index={i} />)}
                </motion.div>
              )}

              {/* Rules tab */}
              {activeTab==='rules' && (
                <motion.div key="rules" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                  {/* Add custom rule */}
                  <div style={{ background:'var(--bg2)', borderRadius:6, padding:12, marginBottom:14 }}>
                    <div className="card-title">Add custom rule</div>
                    <div style={{ display:'flex', gap:8, marginBottom:8 }}>
                      <input value={newRule.rule} placeholder='e.g. "No alcohol branding for under-21 audiences"'
                        onChange={e=>setNewRule(r=>({...r,rule:e.target.value}))}
                        style={{ flex:1, background:'var(--bg3)', border:'1px solid var(--border2)',
                                 borderRadius:5, padding:'7px 10px', color:'var(--text)', fontSize:12 }} />
                    </div>
                    <div style={{ display:'flex', gap:8 }}>
                      <select value={newRule.severity} onChange={e=>setNewRule(r=>({...r,severity:e.target.value}))}
                        style={{ background:'var(--bg3)', border:'1px solid var(--border2)', borderRadius:5,
                                 padding:'6px 10px', color:'var(--text)', fontSize:12 }}>
                        {['critical','high','medium','low'].map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <input value={newRule.category} placeholder="category"
                        onChange={e=>setNewRule(r=>({...r,category:e.target.value}))}
                        style={{ background:'var(--bg3)', border:'1px solid var(--border2)', borderRadius:5,
                                 padding:'6px 10px', color:'var(--text)', fontSize:12, width:120 }} />
                      <motion.button onClick={() => addRuleMutation.mutate()}
                        disabled={!newRule.rule.trim()} whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
                        style={{ background:'var(--cyan)', color:'var(--bg)', border:'none', borderRadius:5,
                                 padding:'6px 14px', fontWeight:700, cursor:'pointer', fontSize:12 }}>
                        <Plus size={12} style={{ marginRight:4, verticalAlign:'middle' }} />Add
                      </motion.button>
                    </div>
                  </div>
                  {/* Predefined rulesets */}
                  {rulesetsData && Object.entries(rulesetsData.predefined||{}).map(([name,rules]) => (
                    <FadeUp key={name}>
                      <div style={{ marginBottom:12 }}>
                        <div style={{ fontSize:11, color:'var(--cyan)', fontFamily:'var(--mono)',
                                      textTransform:'uppercase', marginBottom:6 }}>{name}</div>
                        <StaggerList>
                          {rules.map((r,i) => (
                            <StaggerItem key={i}>
                              <div style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 0',
                                            borderBottom:'1px solid var(--border)' }}>
                                <span style={{ fontSize:10, padding:'1px 6px', borderRadius:3, fontWeight:700,
                                               background: SEV_CONFIG[r.severity]?.bg,
                                               color: SEV_CONFIG[r.severity]?.color }}>
                                  {r.severity}
                                </span>
                                <span style={{ flex:1, fontSize:12, color:'var(--text)' }}>{r.rule}</span>
                              </div>
                            </StaggerItem>
                          ))}
                        </StaggerList>
                      </div>
                    </FadeUp>
                  ))}
                </motion.div>
              )}

              {/* Risk tab */}
              {activeTab==='risk' && (
                <motion.div key="risk" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                  {!riskData?.results?.length && <div style={{ color:'var(--muted)', fontSize:13 }}>No risk data yet</div>}
                  <StaggerList>
                    {(riskData?.results||[]).slice(0,10).map((r,i) => (
                      <StaggerItem key={i}>
                        <div style={{ padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
                          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                            <span style={{ fontSize:12, color:'var(--text)' }}>{r['v.title']||r['v.video_id']}</span>
                            <span style={{ fontSize:12, fontFamily:'var(--mono)', color:'#ff4455' }}>
                              score: {r.risk_score}
                            </span>
                          </div>
                          <RiskMeter score={r.risk_score||0} />
                        </div>
                      </StaggerItem>
                    ))}
                  </StaggerList>
                </motion.div>
              )}

              {/* Audit tab */}
              {activeTab==='audit' && (
                <motion.div key="audit" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                  {!auditData?.audit_trail?.length && (
                    <div style={{ color:'var(--muted)', fontSize:13 }}>No reviewed decisions yet  -  approve/reject flags first</div>
                  )}
                  {(auditData?.audit_trail||[]).map((e,i) => <AuditEntry key={i} entry={e} index={i} />)}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </FadeUp>
      </div>
    </PageWrap>
  );
}


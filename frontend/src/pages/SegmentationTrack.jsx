import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Scissors, Clock, Download, AlertCircle, CheckCircle, Zap } from 'lucide-react';
import api from '../api.jsx';
import { PageWrap, FadeUp, StaggerList, StaggerItem, CountUp, AnimatedBar, ScanLine, PopIn, SeverityPing, TimelineReveal } from '../animations.jsx';

const CONTENT_TYPES = [
  { value: 'auto',        label: 'Auto-detect' },
  { value: 'sports',      label: 'Sports Broadcast' },
  { value: 'news',        label: 'News Program' },
  { value: 'studio',      label: 'Studio Content' },
  { value: 'documentary', label: 'Documentary' },
];

const SEGMENT_COLORS = {
  teaser:'#00e5ff', opening_credits:'#7b61ff', pre_game:'#00bfa5', game_play:'#00e87a',
  instant_replay:'#ffb800', commercial_break_point:'#ff4455', cold_open:'#00e5ff',
  story_intro:'#00e87a', field_report:'#00bfa5', anchor_desk:'#7b61ff',
  weather:'#0288d1', breaking_news:'#ff4455', transition:'#546e7a',
  act_1:'#00e5ff', act_2:'#00e87a', act_3:'#ffb800', act_4:'#7b61ff',
  main_title:'#00bfa5', credits:'#546e7a', chapter:'#00e5ff',
  hook:'#ff6eb4', build:'#7b61ff', payoff:'#00e87a', cta:'#ffb800',
  ad_break_point:'#ff4455', story_boundary:'#00bfa5', default:'#4a7090',
};

function formatTime(s) {
  if (!s && s !== 0) return '--:--';
  return `${Math.floor(s/60)}:${Math.floor(s%60).toString().padStart(2,'0')}`;
}

function SegBadge({ type }) {
  const color = SEGMENT_COLORS[type] || SEGMENT_COLORS.default;
  return (
    <span style={{ background:`${color}22`, color, border:`1px solid ${color}44`,
                   borderRadius:3, padding:'2px 7px', fontSize:10,
                   fontFamily:'var(--mono)', fontWeight:700, whiteSpace:'nowrap' }}>
      {type}
    </span>
  );
}

function Timeline({ segments, duration }) {
  if (!segments?.length) return null;
  const total = duration || segments[segments.length-1]?.['sc.t_end'] || 100;
  return (
    <div style={{ marginTop:12 }}>
      <div style={{ fontSize:11, color:'var(--muted)', marginBottom:6,
                    fontFamily:'var(--mono)', textTransform:'uppercase', letterSpacing:'0.08em' }}>
        Visual timeline
      </div>
      <TimelineReveal>
        <div style={{ position:'relative', height:36, background:'var(--bg2)', borderRadius:4, overflow:'hidden' }}>
          {segments.map((seg, i) => {
            const t_s  = seg['sc.t_start'] ?? seg.t_start ?? 0;
            const t_e  = seg['sc.t_end']   ?? seg.t_end   ?? 0;
            const type = seg['sc.segment_type'] ?? seg.segment_type ?? '';
            const isAd = seg['sc.is_ad_break_candidate'] ?? seg.is_ad_break ?? false;
            const color = isAd ? '#ff4455' : (SEGMENT_COLORS[type] || SEGMENT_COLORS.default);
            return (
              <motion.div key={i}
                initial={{ scaleY: 0 }} animate={{ scaleY: 1 }}
                transition={{ duration: 0.4, delay: i * 0.02 }}
                title={`${type} @ ${formatTime(t_s)}--${formatTime(t_e)}`}
                style={{ position:'absolute', left:`${(t_s/total)*100}%`,
                         width:`${Math.max(((t_e-t_s)/total)*100,0.3)}%`,
                         height:'100%', background:color, opacity:0.85,
                         borderRight:'1px solid var(--bg)', transformOrigin:'bottom',
                         cursor:'pointer' }} />
            );
          })}
        </div>
      </TimelineReveal>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'var(--muted)', marginTop:3 }}>
        <span>0:00</span><span>{formatTime(total/2)}</span><span>{formatTime(total)}</span>
      </div>
      {/* Legend */}
      <div style={{ display:'flex', gap:12, marginTop:8, flexWrap:'wrap' }}>
        {[['#ff4455','Ad break'],['#00e87a','Story/act'],['#00e5ff','Opening'],['#ffb800','Replay'],['#7b61ff','Credits']].map(([c,l]) => (
          <div key={l} style={{ display:'flex', alignItems:'center', gap:4 }}>
            <div style={{ width:10, height:10, borderRadius:2, background:c }} />
            <span style={{ fontSize:10, color:'var(--muted)' }}>{l}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SegmentationTrack() {
  const [videoId, setVideoId]         = useState('');
  const [contentType, setContentType] = useState('auto');
  const [nBreaks, setNBreaks]         = useState(6);
  const [analyzed, setAnalyzed]       = useState(null);

  const { data: adBreaks }  = useQuery({ queryKey:['ad-breaks'],  queryFn:() => api.getAdBreaks({min_score:0.4,limit:20}).then(r=>r.data) });
  const { data: structure } = useQuery({ queryKey:['structure'],  queryFn:() => api.getStructureAnalysis().then(r=>r.data) });

  const analyzeMutation = useMutation({
    mutationFn: ({videoId,contentType}) => api.analyzeSegmentation(videoId,contentType).then(r=>r.data),
    onSuccess: (data) => setAnalyzed(data),
  });
  const optimizeMutation = useMutation({
    mutationFn: ({videoId,nBreaks}) => api.optimizeAdBreaks(videoId,nBreaks).then(r=>r.data),
    onSuccess: (data) => setAnalyzed(prev => ({...prev, optimized:data})),
  });

  const handleDownload = (fmt) => {
    window.open(`${process.env.REACT_APP_API_URL||'http://localhost:8008'}/segment/export/${videoId}?format=${fmt}`,'_blank');
  };

  return (
    <PageWrap>
      <div className="page">
        <FadeUp>
          <div className="page-header">
            <div className="page-title">Segmentation Track</div>
            <div className="page-sub">TwelveLabs Marengo + Pegasus via AWS Bedrock  -  semantic boundary detection</div>
          </div>
        </FadeUp>

        {/* Controls */}
        <FadeUp delay={0.08}>
          <div className="card">
            <div className="card-title">Analyze video</div>
            <div style={{ display:'flex', gap:8, marginBottom:10 }}>
              <input value={videoId} onChange={e=>setVideoId(e.target.value)}
                placeholder="Video ID" style={{ flex:1, background:'var(--bg2)',
                border:'1px solid var(--border2)', borderRadius:6, padding:'8px 12px',
                color:'var(--text)', fontSize:13 }} />
              <select value={contentType} onChange={e=>setContentType(e.target.value)}
                style={{ background:'var(--bg2)', border:'1px solid var(--border2)', borderRadius:6,
                         padding:'8px 12px', color:'var(--text)', fontSize:13, minWidth:160 }}>
                {CONTENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <input type="number" value={nBreaks} onChange={e=>setNBreaks(parseInt(e.target.value))}
                min={1} max={12} title="Ad breaks" style={{ width:60, background:'var(--bg2)',
                border:'1px solid var(--border2)', borderRadius:6, padding:'8px 10px',
                color:'var(--text)', fontSize:13 }} />
              <motion.button onClick={() => analyzeMutation.mutate({videoId,contentType})}
                disabled={analyzeMutation.isPending || !videoId.trim()}
                whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
                style={{ background:'var(--cyan)', color:'var(--bg)', border:'none', borderRadius:6,
                         padding:'8px 18px', fontWeight:700, cursor:'pointer', fontSize:13 }}>
                {analyzeMutation.isPending ? 'Analyzing...' : 'Analyze'}
              </motion.button>
            </div>
            <AnimatePresence>{analyzeMutation.isPending && <ScanLine />}</AnimatePresence>

            {/* Export buttons */}
            <div style={{ display:'flex', gap:6 }}>
              {['json','xml','edl','csv'].map(fmt => (
                <motion.button key={fmt} onClick={() => handleDownload(fmt)}
                  whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }}
                  style={{ background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4,
                           padding:'4px 10px', color:'var(--muted)', fontSize:11, cursor:'pointer',
                           fontFamily:'var(--mono)' }}>
                  <Download size={10} style={{ marginRight:4, verticalAlign:'middle' }} />{fmt.toUpperCase()}
                </motion.button>
              ))}
            </div>
          </div>
        </FadeUp>

        {/* Analysis results */}
        <PopIn show={!!analyzed}>
          {analyzed && (
            <div className="card">
              {/* Metric cards */}
              <div style={{ display:'flex', gap:16, marginBottom:12 }}>
                {[
                  {label:'Segments', val:analyzed.count||0, color:'var(--cyan)'},
                  {label:'Ad breaks', val:analyzed.ad_break_count||0, color:'#ff4455'},
                ].map(({label,val,color},i) => (
                  <FadeUp key={label} delay={i*0.08}>
                    <div className="metric-card" style={{ minWidth:100 }}>
                      <div className="metric-label">{label}</div>
                      <div className="metric-val" style={{ color }}>
                        <CountUp to={val} />
                      </div>
                    </div>
                  </FadeUp>
                ))}
                <FadeUp delay={0.16}>
                  <div className="metric-card" style={{ minWidth:120 }}>
                    <div className="metric-label">Content type</div>
                    <div className="metric-val" style={{ fontSize:16, color:'var(--amber)' }}>
                      {analyzed.content_type || 'auto'}
                    </div>
                  </div>
                </FadeUp>
              </div>

              <Timeline segments={analyzed.segments||[]} />

              {/* Optimize */}
              <div style={{ marginTop:12, display:'flex', gap:8, alignItems:'center' }}>
                <motion.button onClick={() => optimizeMutation.mutate({videoId,nBreaks})}
                  disabled={optimizeMutation.isPending}
                  whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
                  style={{ background:'#ff4455', color:'white', border:'none', borderRadius:6,
                           padding:'6px 14px', fontWeight:700, cursor:'pointer', fontSize:12 }}>
                  <Zap size={12} style={{ marginRight:4, verticalAlign:'middle' }} />
                  {optimizeMutation.isPending ? 'Optimizing...' : `Optimize ${nBreaks} ad breaks`}
                </motion.button>
                <span style={{ fontSize:11, color:'var(--muted)' }}>min 5-min gap * greedy by boundary quality</span>
              </div>

              {/* Optimized breaks */}
              <PopIn show={!!analyzed.optimized}>
                {analyzed.optimized && (
                  <div style={{ marginTop:12, background:'var(--bg2)', borderRadius:6, padding:12 }}>
                    <div style={{ fontSize:11, color:'var(--muted)', marginBottom:8,
                                  fontFamily:'var(--mono)', textTransform:'uppercase' }}>
                      Optimal {analyzed.optimized.n_found} ad break positions
                    </div>
                    <StaggerList>
                      {(analyzed.optimized.ad_breaks||[]).map((b,i) => (
                        <StaggerItem key={i}>
                          <div style={{ display:'flex', alignItems:'center', gap:10,
                                        padding:'5px 0', borderBottom:'1px solid var(--border)' }}>
                            <span style={{ fontSize:12, fontFamily:'var(--mono)', color:'#ff4455', minWidth:20 }}>{i+1}</span>
                            <span style={{ fontSize:13, color:'var(--cyan)', fontFamily:'var(--mono)' }}>
                              {formatTime(b['sc.t_start']||b.t_start)}
                            </span>
                            <span style={{ flex:1, fontSize:12, color:'var(--muted)' }}>{b['sc.label']||b.label||'natural pause'}</span>
                            <SegBadge type={b['sc.boundary_quality']||b.boundary_quality||'soft'} />
                          </div>
                        </StaggerItem>
                      ))}
                    </StaggerList>
                  </div>
                )}
              </PopIn>

              {/* Segment list */}
              <div style={{ marginTop:14 }}>
                <div className="card-title">All segments</div>
                <StaggerList>
                  {(analyzed.segments||[]).map((seg,i) => {
                    const t_s  = seg.t_start ?? seg['sc.t_start'] ?? 0;
                    const t_e  = seg.t_end   ?? seg['sc.t_end']   ?? 0;
                    const type = seg.segment_type ?? seg['sc.segment_type'] ?? '';
                    const label= seg.label ?? seg['sc.label'] ?? '';
                    const conf = seg.confidence ?? seg['sc.confidence'] ?? 0;
                    const isAd = seg.is_ad_break_candidate ?? seg['sc.is_ad_break_candidate'] ?? false;
                    return (
                      <StaggerItem key={i}>
                        <div style={{ display:'flex', alignItems:'center', gap:10,
                                      padding:'6px 0', borderBottom:'1px solid var(--border)' }}>
                          {isAd ? <AlertCircle size={13} color="#ff4455" /> : <CheckCircle size={13} color="var(--border2)" />}
                          <span style={{ fontSize:11, color:'var(--muted)', fontFamily:'var(--mono)', minWidth:80 }}>
                            {formatTime(t_s)}--{formatTime(t_e)}
                          </span>
                          <SegBadge type={type} />
                          <span style={{ flex:1, fontSize:12, color:'var(--text)' }}>{label}</span>
                          <div style={{ width:80 }}>
                            <AnimatedBar value={conf} color="var(--cyan)" delay={i*0.03} />
                          </div>
                        </div>
                      </StaggerItem>
                    );
                  })}
                </StaggerList>
              </div>
            </div>
          )}
        </PopIn>

        {/* Bottom two-col */}
        <FadeUp delay={0.2}>
          <div className="two-col">
            <div className="card">
              <div className="card-title">Ad breaks  -  corpus</div>
              {!adBreaks?.ad_breaks?.length && <div style={{ color:'var(--muted)', fontSize:13 }}>Run pipeline to populate</div>}
              <StaggerList>
                {(adBreaks?.ad_breaks||[]).slice(0,8).map((b,i) => (
                  <StaggerItem key={i}>
                    <div style={{ display:'flex', alignItems:'center', gap:8,
                                  padding:'6px 0', borderBottom:'1px solid var(--border)' }}>
                      <AlertCircle size={13} color="#ff4455" />
                      <span style={{ fontSize:12, fontFamily:'var(--mono)', color:'var(--cyan)', minWidth:42 }}>
                        {formatTime(b['sc.t_start']||0)}
                      </span>
                      <span style={{ flex:1, fontSize:11, color:'var(--muted)', overflow:'hidden',
                                     textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                        {b['v.title']||'archive clip'}
                      </span>
                      <span style={{ fontSize:11, fontFamily:'var(--mono)', color:'var(--green)' }}>
                        {Math.round((b['sc.viral_segment_score']||0)*100)}%
                      </span>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerList>
            </div>

            <div className="card">
              <div className="card-title">Segment distribution</div>
              {!structure?.distribution?.length && <div style={{ color:'var(--muted)', fontSize:13 }}>Run pipeline to populate</div>}
              {(structure?.distribution||[]).slice(0,10).map((d,i) => {
                const color = SEGMENT_COLORS[d.type]||SEGMENT_COLORS.default;
                const pct   = Math.round((d.count/(structure.distribution[0]?.count||1))*100);
                return (
                  <motion.div key={i} style={{ marginBottom:8 }}
                    initial={{ opacity:0, x:20 }} animate={{ opacity:1, x:0 }}
                    transition={{ delay:i*0.05 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
                      <SegBadge type={d.type} />
                      <span style={{ fontSize:11, color:'var(--muted)', fontFamily:'var(--mono)' }}>
                        {d.count} * {Math.round((d.avg_viral_score||0)*100)}%
                      </span>
                    </div>
                    <AnimatedBar value={pct/100} color={color} delay={i*0.06} />
                  </motion.div>
                );
              })}
            </div>
          </div>
        </FadeUp>
      </div>
    </PageWrap>
  );
}


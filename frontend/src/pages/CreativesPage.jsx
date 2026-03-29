import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Film, Play, ExternalLink, Zap, Image } from 'lucide-react';
import api from '../api.jsx';

const FORMAT_OPTIONS = [
  { value: '6s_bumper',   label: '6s Bumper',    desc: 'Pre-roll, high retention' },
  { value: '15s_preroll', label: '15s Pre-roll',  desc: 'Full story arc' },
  { value: 'thumbnail',   label: 'Thumbnail',     desc: 'Display inventory' },
];

const CAT_COLORS = {
  food_cooking: 'var(--cyan)', product_unboxing: 'var(--amber)',
  sports_highlights: 'var(--green)', satisfying_asmr: 'var(--purple)',
  life_hack_tutorial: 'var(--red)',
};

function CreativeCard({ creative }) {
  const isSimulated = creative.status === 'simulated';
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
      borderTop: `2px solid ${isSimulated ? 'var(--amber)' : 'var(--green)'}`,
    }}>
      {/* Thumbnail */}
      <div style={{
        height: 100, background: 'var(--bg3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {creative.thumbnail_url && !isSimulated ? (
          <img src={creative.thumbnail_url} alt="" style={{
            width: '100%', height: '100%', objectFit: 'cover',
          }} onError={e => { e.target.style.display = 'none'; }} />
        ) : (
          <Film size={28} style={{ color: 'var(--border2)' }} />
        )}
        <div style={{
          position: 'absolute', top: 5, right: 5,
          background: 'rgba(0,0,0,.75)', borderRadius: 3,
          padding: '2px 6px', fontSize: 9,
          fontFamily: 'var(--mono)',
          color: isSimulated ? 'var(--amber)' : 'var(--green)',
        }}>
          {isSimulated ? 'SIM' : 'LIVE'} * {creative.duration}s
        </div>
        <div style={{
          position: 'absolute', bottom: 5, left: 5,
          background: 'rgba(0,0,0,.75)', borderRadius: 3,
          padding: '2px 6px', fontSize: 9,
          fontFamily: 'var(--mono)', color: 'var(--text)',
        }}>
          {creative.ad_format}
        </div>
      </div>

      <div style={{ padding: '10px 12px' }}>
        <div style={{ fontSize: 10, fontFamily: 'var(--mono)',
          color: 'var(--muted)', marginBottom: 4 }}>
          {creative.creative_id?.slice(0, 20)}...
        </div>

        {creative.prompt && (
          <div style={{
            fontSize: 10, color: 'var(--muted)', lineHeight: 1.4,
            background: 'var(--bg1)', borderRadius: 4, padding: '5px 7px',
            marginBottom: 8,
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {creative.prompt.slice(0, 120)}...
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {creative.video_url && (
            <a href={creative.video_url} target="_blank" rel="noreferrer"
              style={{ fontSize: 10, color: 'var(--cyan)',
                display: 'flex', alignItems: 'center', gap: 3 }}>
              <Play size={10} /> Preview
            </a>
          )}
          {creative.cdn_url && creative.cdn_url !== creative.video_url && (
            <a href={creative.cdn_url} target="_blank" rel="noreferrer"
              style={{ fontSize: 10, color: 'var(--green)',
                display: 'flex', alignItems: 'center', gap: 3 }}>
              <ExternalLink size={10} /> CDN
            </a>
          )}
        </div>

        {isSimulated && (
          <div style={{ fontSize: 9, color: 'var(--amber)', marginTop: 6,
            fontFamily: 'var(--mono)' }}>
            Set LTX_API_KEY for real generation
          </div>
        )}
      </div>
    </div>
  );
}

export default function CreativesPage() {
  const [videoId, setVideoId] = useState('');
  const [adFormat, setAdFormat] = useState('6s_bumper');
  const [generatedCreatives, setGeneratedCreatives] = useState([]);
  const qc = useQueryClient();

  const { data: videos } = useQuery({
    queryKey: ['videos-for-creative'],
    queryFn: () => api.getVideos({ limit: 100 }).then(r => r.data),
  });

  const generateMutation = useMutation({
    mutationFn: ({ vid, fmt }) => api.generateCreative(vid, fmt).then(r => r.data),
    onSuccess: (data) => {
      setGeneratedCreatives(prev => [data.creative, ...prev]);
      qc.invalidateQueries(['creatives', videoId]);
    },
  });

  const { data: existingCreatives } = useQuery({
    queryKey: ['creatives', videoId],
    queryFn: () => videoId ? api.getVideoCreatives(videoId).then(r => r.data) : null,
    enabled: !!videoId,
  });

  const selectedVideo = videos?.videos?.find(v => v['v.video_id'] === videoId);

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">LTX Creative Generation</div>
        <div className="page-sub">
          AI-generated video ad creatives matched to placement moment  -  mood, objects, palette
        </div>
      </div>

      {/* Status */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '7px 12px', marginBottom: 20,
        background: 'rgba(123,97,255,.06)',
        border: '1px solid rgba(123,97,255,.2)', borderRadius: 7,
        fontSize: 12, color: 'var(--muted)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%',
          background: 'var(--amber)', display: 'inline-block', flexShrink: 0 }} />
        <span style={{ color: 'var(--purple)', fontFamily: 'var(--mono)',
          fontWeight: 700 }}>LTX Studio</span>
        Production-ready AI creative infrastructure  -  generates 6s bumpers
        and 15s pre-rolls matched to ZeroClick brief context
        <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: 'var(--mono)',
          color: 'var(--border2)' }}>
          Fallback: simulation when LTX_API_KEY not set
        </span>
      </div>

      {/* Generator */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="section-title">Generate creative from brief</div>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <select
            value={videoId}
            onChange={e => setVideoId(e.target.value)}
            style={{ flex: 2, minWidth: 200 }}
          >
            <option value="">Select a video with a ZeroClick brief...</option>
            {(videos?.videos || []).map(v => (
              <option key={v['v.video_id']} value={v['v.video_id']}>
                [{(v['v.category'] || '').replace('_', ' ')}]&nbsp;
                {(v['v.title'] || '').slice(0, 55)}
                {v.brief_headline ? ' *' : ''}
              </option>
            ))}
          </select>

          <div style={{ display: 'flex', gap: 6 }}>
            {FORMAT_OPTIONS.map(f => (
              <button key={f.value}
                onClick={() => setAdFormat(f.value)}
                style={{
                  padding: '7px 12px', fontSize: 11, cursor: 'pointer',
                  background: adFormat === f.value ? 'var(--purple)' : 'transparent',
                  color: adFormat === f.value ? '#fff' : 'var(--muted)',
                  border: `1px solid ${adFormat === f.value ? 'var(--purple)' : 'var(--border2)'}`,
                  borderRadius: 6, transition: 'all .15s',
                }}>
                {f.label}
              </button>
            ))}
          </div>

          <button
            className="btn-primary"
            onClick={() => generateMutation.mutate({ vid: videoId, fmt: adFormat })}
            disabled={!videoId || generateMutation.isPending}
            style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
          >
            <Film size={13} />
            {generateMutation.isPending ? 'Generating...' : 'Generate with LTX'}
          </button>
        </div>

        {/* Selected video brief preview */}
        {selectedVideo?.brief_headline && (
          <div style={{
            padding: '8px 12px', background: 'var(--bg2)',
            borderRadius: 6, border: '1px solid var(--border)',
            fontSize: 11, color: 'var(--muted)',
          }}>
            <span style={{ color: 'var(--amber)', marginRight: 6 }}>
              <Zap size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> Brief:
            </span>
            {selectedVideo.brief_headline}
          </div>
        )}

        {generateMutation.isError && (
          <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8 }}>
            Generation failed. Check LTX_API_KEY or try a video with a brief.
          </div>
        )}
      </div>

      {/* Just-generated creatives */}
      {generatedCreatives.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div className="section-title">Just generated ({generatedCreatives.length})</div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}>
            {generatedCreatives.map((c, i) => (
              <CreativeCard key={i} creative={c} />
            ))}
          </div>
        </div>
      )}

      {/* Existing creatives for selected video */}
      {existingCreatives?.creatives?.length > 0 && (
        <div>
          <div className="section-title">
            Existing creatives for this video ({existingCreatives.creatives.length})
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}>
            {existingCreatives.creatives.map((c, i) => (
              <CreativeCard key={i} creative={{
                creative_id: c['c.creative_id'],
                video_url: c['c.video_url'],
                thumbnail_url: c['c.thumbnail_url'],
                ad_format: c['c.ad_format'],
                duration: c['c.duration'],
                status: c['c.status'],
              }} />
            ))}
          </div>
        </div>
      )}

      {!videoId && generatedCreatives.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <Film size={32} style={{ color: 'var(--border2)', marginBottom: 12 }} />
          <div style={{ color: 'var(--muted)', fontSize: 14 }}>
            Select a video and click Generate  -  LTX builds a matched creative
            from the ZeroClick brief and TwelveLabs scene context
          </div>
          <div style={{ fontSize: 11, color: 'var(--border2)', marginTop: 8 }}>
            Mood * objects * palette * placement timestamp - production-ready bumper
          </div>
        </div>
      )}
    </div>
  );
}

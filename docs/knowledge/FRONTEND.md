# FRONTEND.md — React Frontend

## Stack

- React 18 + React Router v6
- TanStack Query (react-query) for data fetching + caching
- Framer Motion for page transitions
- Recharts for charts
- Lucide React for icons
- Custom CSS variables (Bloomberg Terminal dark aesthetic)

## File structure

```
frontend/src/
├── App.js          ← Router + Sidebar + nav
├── App.css         ← Design system (CSS variables, components)
├── api.js          ← All API calls (47 methods)
├── index.js        ← React entry point
├── index.css       ← Global resets
└── pages/
    ├── Dashboard.js          ← Graph stats + pipeline + top videos
    ├── VideoGrid.js          ← 500-video card grid
    ├── SearchTrack.js        ← Semantic search UI
    ├── SegmentationTrack.js  ← Ad breaks + timeline
    ├── ComplianceTrack.js    ← Compliance flags
    ├── AdvertiserBriefs.js   ← ZeroClick brief cards
    ├── Campaigns.js          ← Opus campaign matching
    ├── CreativesPage.js      ← LTX creative generation
    ├── TrackItPage.js        ← Workflow + MAM + QoE + audit
    └── Payments.js           ← Circle wallet + x402
```

---

## Navigation (App.js NAV array)

```javascript
const NAV = [
  { to: '/',           icon: BarChart2,  label: 'Dashboard'     },
  { to: '/videos',     icon: Database,   label: 'Video Graph'   },
  { to: '/search',     icon: Search,     label: 'Search Track'  },
  { to: '/segment',    icon: Scissors,   label: 'Segmentation'  },
  { to: '/compliance', icon: ShieldCheck,label: 'Compliance'    },
  { to: '/briefs',     icon: Zap,        label: 'Ad Briefs'     },
  { to: '/campaigns',  icon: Target,     label: 'Campaigns'     },
  { to: '/creatives',  icon: Film,       label: 'LTX Creatives' },
  { to: '/trackit',    icon: GitBranch,  label: 'TrackIt'       },
  { to: '/payments',   icon: Activity,   label: 'Payments'      },
];
```

To add a new page:
1. Create `frontend/src/pages/NewPage.js`
2. Import in `App.js`
3. Add to `NAV` array with icon + label
4. Add `<Route path="/newpath" element={<NewPage />} />`

---

## api.js — all API methods

```javascript
import api from '../api';

// Usage in a component
const { data, isLoading } = useQuery({
  queryKey: ['my-key'],
  queryFn: () => api.getVideos({ limit: 20 }).then(r => r.data),
  refetchInterval: 15000,
});
```

Key methods:
```javascript
// Pipeline
api.startPipeline()
api.getPipelineStatus()

// Graph
api.getGraphStats()
api.getVideos({ skip, limit, category })
api.getSimilarVideos(videoId)
api.getCategories()

// Search
api.semanticSearch({ query, category, limit, use_twelvelabs })
api.getTopHooks({ category, limit })

// Segment
api.getVideoSegments(videoId)
api.getAdBreaks({ category, min_score, limit })
api.getStructureAnalysis()

// Compliance
api.getComplianceFlags({ severity, category, limit })
api.getComplianceSummary()
api.checkCompliance(videoId)

// Briefs
api.getBriefs({ min_cpm, category, limit })
api.getBrief(videoId)

// Campaigns
api.matchCampaign(briefData)
api.getCampaigns()
api.getCampaign(campaignId)

// Deals
api.activateDeal(videoId, networks)
api.getDeals({ platform, status })
api.getRevenue()
api.refreshDealStats(dealId, platform)

// Ontology
api.inferOntology()
api.getOntologySchema()
api.getViralFormats()

// LTX
api.generateCreative(videoId, adFormat)
api.generateCampaignCreatives(campaignId, adFormat)
api.getVideoCreatives(videoId)

// TrackIt
api.submitWorkflow(videoId)
api.getWorkflowStatus(workflowId)
api.pushMAM(videoId)
api.getAuditTrail(videoId)
api.getQoE(videoId)
api.getTrackItPipelineStates()

// Circle / x402
api.getCircleWallet()
api.createPaymentIntent(queryType)
api.verifyPayment(transferId, queryType)
api.getCircleTransactions(limit)
api.getX402Stats()
api.getX402Pricing()
api.getMCPManifest()

// Trends
api.detectTrends()
```

---

## CSS Design System (App.css)

Dark Bloomberg Terminal theme. Key CSS variables:

```css
--bg:         #080c10   /* page background */
--bg1:        #0d1318   /* sidebar + cards */
--bg2:        #121920   /* input backgrounds */
--bg3:        #1a2530   /* hover/subtle */
--border:     #1e2e3a   /* primary border */
--border2:    #2a3f52   /* secondary border */
--cyan:       #00e5ff   /* primary accent */
--green:      #00e87a   /* success */
--amber:      #ffb800   /* warning/revenue */
--red:        #ff4455   /* danger/flags */
--purple:     #7b61ff   /* Opus/AI */
--pink:       #ff6eb4   /* payments */
--teal:       #00d4aa   /* TrackIt */
--text:       #ddeef8   /* primary text */
--muted:      #5a7a94   /* secondary text */
--mono:       'Courier New', monospace
```

Pre-built component classes:
```css
.card           /* bg1 + border + border-radius */
.card-title     /* uppercase mono label */
.metric-card    /* stat display card */
.metric-val     /* large number */
.metric-label   /* small label */
.score-bar      /* horizontal progress bar */
.score-bar-fill /* colored fill */
.badge          /* pill badge */
.b-cyan .b-green .b-amber .b-red .b-purple /* badge variants */
.btn-primary    /* cyan button */
.btn-ghost      /* outline button */
.table-wrap     /* scrollable table container */
.page           /* page container */
.page-header    /* page title + subtitle */
.two-col        /* 2-column grid */
.loading        /* spinner + text */
.empty          /* empty state */
```

---

## Pattern: adding a new page

```javascript
// frontend/src/pages/NewPage.js
import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api';

export default function NewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['new-data'],
    queryFn: () => api.getVideos({ limit: 10 }).then(r => r.data),
    refetchInterval: 15000,
  });

  if (isLoading) return (
    <div className="loading">
      <div className="spinner" />Loading...
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">New Page</div>
        <div className="page-sub">Description here</div>
      </div>

      <div className="metrics">
        <div className="metric-card">
          <div className="metric-label">Total</div>
          <div className="metric-val" style={{ color: 'var(--cyan)' }}>
            {data?.videos?.length ?? 0}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Section title</div>
        {/* content */}
      </div>
    </div>
  );
}
```

---

## QueryClient config (App.js)

```javascript
const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchInterval: 15000, retry: 1 } },
});
```

All queries auto-refetch every 15 seconds. Override per-query with `refetchInterval`.

---

## API base URL

Set via `REACT_APP_API_URL` env var (docker-compose sets it to `http://localhost:8000`).
```javascript
// api.js
const API = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
});
```

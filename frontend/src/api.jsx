import axios from 'axios';

const API = axios.create({
  baseURL: '',
  timeout: 30000,
});

export const api = {
  // Pipeline
  startPipeline: () => API.post('/pipeline/start'),
  getPipelineStatus: () => API.get('/pipeline/status'),
  getJob: (id) => API.get(`/pipeline/job/${id}`),

  // Graph
  getStats: () => API.get('/graph/stats'),
  getVideos: (params) => API.get('/videos', { params }),
  getCategories: () => API.get('/categories'),
  getSimilar: (id) => API.get(`/videos/${id}/similar`),

  // Search Track
  semanticSearch: (data) => API.post('/search/semantic', data),
  getTopHooks: (params) => API.get('/search/top-hooks', { params }),
  getProductMoments: (params) => API.get('/search/product-moments', { params }),

  // Segmentation Track
  getVideoSegments: (id) => API.get(`/segment/video/${id}`),
  getAdBreaks: (params) => API.get('/segment/ad-breaks', { params }),
  getStructureAnalysis: (params) => API.get('/segment/structure-analysis', { params }),
  analyzeSegmentation: (videoId, contentType) => API.post(`/segment/analyze/${videoId}`, null, { params: { content_type: contentType } }),
  optimizeAdBreaks: (videoId, nBreaks) => API.get(`/segment/ad-breaks/optimize/${videoId}`, { params: { n_breaks: nBreaks } }),
  getStoryBoundaries: (videoId) => API.get(`/segment/story-boundaries/${videoId}`),
  exportSegments: (videoId, format) => API.get(`/segment/export/${videoId}`, { params: { format } }),

  // Compliance Track
  getFlags: (params) => API.get('/compliance/flags', { params }),
  getComplianceSummary: () => API.get('/compliance/summary'),
  runComplianceCheck: (id) => API.post(`/compliance/check/${id}`),
  runComplianceExplain: (id, ruleset) => API.post(`/compliance/check/${id}/explain`, null, { params: { ruleset } }),
  getRulesets: () => API.get('/compliance/rulesets'),
  getComplianceFlags: (params) => API.get('/compliance/flags', { params }),
  reviewCompliance: (flagId, body) => API.post(`/compliance/review/${flagId}`, body),
  getRiskScores: (limit) => API.get('/compliance/risk-scores', { params: { limit } }),
  getComplianceAudit: (videoId) => API.get('/compliance/audit', { params: { video_id: videoId } }),
  createComplianceRule: (rule) => API.post('/compliance/rules', rule),
  createRule: (rule) => API.post('/compliance/rules', rule),
  reviewFlag: (flagId, body) => API.post(`/compliance/review/${flagId}`, body),
  getComplianceAuditTrail: (videoId) => API.get('/compliance/audit', { params: { video_id: videoId } }),

  // Briefs
  getBriefs: (params) => API.get('/briefs', { params }),
  getBrief: (id) => API.get(`/briefs/${id}`),

  // Ontology (Opus 4.6)
  inferOntology: () => API.post('/ontology/infer'),
  getSchema: () => API.get('/ontology/schema'),
  getViralFormats: () => API.get('/ontology/viral-formats'),

  // Campaign matching (Opus 4.6)
  matchCampaign: (brief) => API.post('/campaigns/match', brief),
  getCampaigns: (params) => API.get('/campaigns', { params }),
  getCampaign: (id) => API.get(`/campaigns/${id}`),

  // Ad network deals + revenue
  activateDeal: (videoId, networks) => API.post(`/deals/activate/${videoId}`, null, { params: { networks } }),
  getDeals: (params) => API.get('/deals', { params }),
  getRevenue: () => API.get('/revenue'),
  refreshDealStats: (dealId, platform) => API.get(`/revenue/deals/${dealId}/refresh`, { params: { platform } }),

  // Trend detection (Opus 4.6)
  detectTrends: () => API.post('/trends/detect'),

  // Circle / x402 micropayments
  getCircleWallet: () => API.get('/circle/wallet'),
  createPaymentIntent: (queryType) => API.post(`/circle/payment-intent?query_type=${queryType}`),
  verifyPayment: (transferId, queryType) => API.get(`/circle/verify/${transferId}?query_type=${queryType}`),
  getCircleTransactions: (limit = 20) => API.get('/circle/transactions', { params: { limit } }),
  getX402Stats: () => API.get('/x402/stats'),
  getX402Pricing: () => API.get('/x402/pricing'),
  getMCPManifest: () => API.get('/.well-known/mcp.json'),

  // LTX  -  AI creative generation
  generateCreative: (videoId, adFormat) =>
    API.post(`/creatives/generate/${videoId}`, null, { params: { ad_format: adFormat } }),
  generateCampaignCreatives: (campaignId, adFormat) =>
    API.post(`/creatives/campaign/${campaignId}`, null, { params: { ad_format: adFormat } }),
  getVideoCreatives: (videoId) => API.get(`/creatives/video/${videoId}`),

  // TrackIt  -  workflow + MAM + CDN + audit
  submitWorkflow: (videoId) => API.post(`/trackit/workflow/${videoId}`),
  getWorkflowStatus: (workflowId) => API.get(`/trackit/workflow/${workflowId}/status`),
  pushMAM: (videoId) => API.post(`/trackit/mam/${videoId}`),
  getAuditTrail: (videoId) => API.get('/trackit/audit', { params: { video_id: videoId } }),
  getQoE: (videoId) => API.get(`/trackit/qoe/${videoId}`),
  getTrackItPipelineStates: () => API.get('/trackit/pipeline-states'),
};

export default api;

import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: baseURL + '/api/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const operator = localStorage.getItem('operator_name') || ''
  if (operator) config.headers['X-Operator-Name'] = operator
  const token = localStorage.getItem('jwt_token') || ''
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

const CACHE_PREFIX = 'sgapi:'
const CACHE_TTL_MS = 60 * 60 * 1000
const MAX_RETRIES  = 3

const _cacheKey = (cfg) =>
  `${CACHE_PREFIX}${(cfg?.method || 'get').toUpperCase()}:${cfg?.url || ''}:${JSON.stringify(cfg?.params || {})}`

function _saveCache(cfg, data) {
  try {
    localStorage.setItem(_cacheKey(cfg), JSON.stringify({ ts: Date.now(), data }))
  } catch (_) {}
}

function _loadCache(cfg) {
  try {
    const raw = localStorage.getItem(_cacheKey(cfg))
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > CACHE_TTL_MS) return null
    return data
  } catch (_) { return null }
}

export function _clearCacheKey(urlFragment) {
  try {
    Object.keys(localStorage).forEach((key) => {
      if (key.startsWith(CACHE_PREFIX) && key.includes(urlFragment)) {
        localStorage.removeItem(key)
      }
    })
  } catch (_) {}
}

const _sleep = (ms) => new Promise((r) => setTimeout(r, ms))

api.interceptors.response.use(
  (r) => {
    if ((r.config?.method || 'get').toLowerCase() === 'get') _saveCache(r.config, r.data)
    return r
  },
  async (err) => {
    const cfg = err.config || {}
    const status = err.response?.status
    const isNetwork = !err.response
    const isServerErr = status && status >= 500
    const method = (cfg.method || 'get').toLowerCase()
    cfg._retries = cfg._retries || 0
    if ((isNetwork || isServerErr) && cfg._retries < MAX_RETRIES) {
      cfg._retries += 1
      await _sleep(400 * cfg._retries)
      return api(cfg)
    }
    const msg =
      err.response?.data?.detail ||
      (isNetwork ? 'Backend restarting — please wait a moment and try again' : err.message) ||
      'Request failed'
    err.friendly = msg
    if (method === 'get') {
      const cached = _loadCache(cfg)
      if (cached !== null) {
        return {
          data: { ...cached, _fromCache: true, _cacheError: msg },
          status: 200, statusText: 'OK (cache)', headers: {}, config: cfg,
        }
      }
    }
    return Promise.reject(err)
  }
)

// Endpoint wrappers

export const Health = () => api.get('/health').then((r) => r.data)
export const Me     = () => api.get('/auth/me').then((r) => r.data)

export const Login = (username, password) => {
  const form = new URLSearchParams({ username, password })
  return api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  }).then((r) => r.data)
}

export const GridScore  = ()               => api.get('/grid-score').then((r) => r.data)
export const Heatmap    = ()               => api.get('/heatmap').then((r) => r.data)
export const Timeline   = (bucket = 'day') => api.get('/timeline', { params: { bucket } }).then((r) => r.data)
export const Telemetry  = (limit = 100)   => api.get('/telemetry', { params: { limit } }).then((r) => r.data)
export const RecentRecs = (limit = 10)    => api.get('/recommendations', { params: { limit } }).then((r) => r.data)
export const QaHistory  = (limit = 20, unique = true) =>
  api.get('/qa-history', { params: { limit, unique } }).then((r) => r.data)

export const SearchIncidents = (params = {}) => api.get('/incidents', { params }).then((r) => r.data)
export const Analyze         = (payload)     => api.post('/analyze', payload).then((r) => r.data)
export const ValidateQuery   = (query)       => api.post('/guardrails/validate-query', { query }).then((r) => r.data)

const LONG_TIMEOUT = 600000

export const ListDatasets   = ()         => api.get('/datasets', { params: { _t: Date.now() } }).then((r) => r.data)
export const DeleteDataset  = (filename) => api.delete('/datasets/' + encodeURIComponent(filename)).then((r) => r.data)
export const ProcessDataset = (filename) =>
  api.post('/datasets/' + encodeURIComponent(filename) + '/process', null, { timeout: LONG_TIMEOUT })
     .then((r) => r.data)

export const EtlHistory = (limit = 20) =>
  api.get('/datasets/etl/history', { params: { limit } }).then((r) => r.data)
export const EtlLastRun = () =>
  api.get('/datasets/etl/last-run', { params: { _t: Math.floor(Date.now() / 10000) } }).then((r) => r.data)
export const ClearEtlCache = () => {
  _clearCacheKey('etl/last-run')
  _clearCacheKey('etl/history')
}

export const UploadDataset = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/datasets/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: LONG_TIMEOUT,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  }).then((r) => r.data)
}

export const RunIngest = (body = {}) => api.post('/ingest', body, { timeout: LONG_TIMEOUT }).then((r) => r.data)
export const RunEmbed  = (body = {}) => api.post('/embed',  body, { timeout: LONG_TIMEOUT }).then((r) => r.data)

export const Predict            = ()      => api.get('/predict').then((r) => r.data)
export const DemandForecast     = ()      => api.get('/forecast').then((r) => r.data)
export const AnomalyCorrelations = ()     => api.get('/correlations').then((r) => r.data)

export const Evaluate = (response, query) =>
  api.post('/evaluate', { query: query ?? response?.query, response }).then((r) => r.data)

export const ExportPdf = async (analyzeResponse) => {
  const res  = await api.post('/export/pdf', analyzeResponse, { responseType: 'blob' })
  const blob = new Blob([res.data], { type: 'application/pdf' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = 'analysis_' + Date.now() + '.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return true
}

// --- Admin / Model management (additive) ---
export const GetConfig    = ()       => api.get('/config').then((r) => r.data)
export const SetConfig    = (body)   => api.post('/config', body).then((r) => r.data)
export const ResetIndex   = ()       => api.post('/admin/reset-index', {}).then((r) => r.data)
export const ValidateRetrieval = (query) =>
  api.post('/admin/validate-retrieval', query ? { query } : {}).then((r) => r.data)

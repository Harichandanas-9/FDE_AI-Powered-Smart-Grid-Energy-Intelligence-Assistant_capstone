import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, Gauge, Zap, RefreshCw, Database,
  CheckCircle2, AlertOctagon,
} from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import MetricCard from '../components/cards/MetricCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import HealthGauge from '../components/charts/HealthGauge.jsx'
import RegionBars from '../components/charts/RegionBars.jsx'
import HeatmapGrid from '../components/charts/HeatmapGrid.jsx'
import TimelineArea from '../components/charts/TimelineArea.jsx'
import {
  GridScore, Heatmap, Timeline, RecentRecs, RunIngest, RunEmbed, EtlLastRun, Predict,
} from '../services/api.js'

function fmtAgo(iso) {
  if (!iso) return ''
  const dt = new Date(iso)
  const s = Math.floor((Date.now() - dt.getTime()) / 1000)
  if (s < 60)    return `${s}s ago`
  if (s < 3600)  return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return dt.toLocaleString()
}

function fmtTime(iso) {
  if (!iso) return ''
  const dt = new Date(iso)
  return dt.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric',
                                       hour: '2-digit', minute: '2-digit' })
}

export default function Dashboard() {
  const nav = useNavigate()
  const [score, setScore]     = useState(null)
  const [heat,  setHeat]      = useState(null)
  const [time,  setTime]      = useState(null)
  const [recs,  setRecs]      = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy]       = useState(false)
  const [toast, setToast]     = useState(null)
  const [errors,  setErrors]  = useState({})        // {gridScore, heatmap, timeline, recs}
  const [loadedAt, setLoadedAt] = useState(null)
  const [etl, setEtl]           = useState(null)    // last ETL run record
  const [predict, setPredict]   = useState(null)

  const load = async () => {
    console.log('[Dashboard] loading widgets...')
    setLoading(true)
    setErrors({})
    const errs = {}
    const [s, h, t, r, e, p] = await Promise.all([
      GridScore().catch((err) => { errs.gridScore = err.friendly || 'failed'; return null }),
      Heatmap().catch((err)   => { errs.heatmap   = err.friendly || 'failed'; return null }),
      Timeline('day').catch((err) => { errs.timeline = err.friendly || 'failed'; return null }),
      RecentRecs().catch((err) => { errs.recs    = err.friendly || 'failed'; return null }),
      EtlLastRun().catch(() => null),
      Predict().catch(() => null),
    ])
    console.log('[Dashboard] gridScore:', s, '| heatmap:', h, '| timeline:', t,
                '| recs:', r, '| etl:', e, '| predict:', p, '| errors:', errs)
    setScore(s); setHeat(h); setTime(t); setRecs(r); setEtl(e); setPredict(p)
    setErrors(errs)
    setLoadedAt(new Date())
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  // Auto-refresh every 60s (was 30s) — reduces backend load during demo
  useEffect(() => {
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  const refreshData = async () => {
    setBusy(true)
    try {
      const r1 = await RunIngest({})
      const r2 = await RunEmbed({ reset: false })
      setToast(`Ingest ${r1.chunks_written} chunks · Embed ${r2.chunks_embedded} (total ${r2.collection_total})`)
      await load()
    } catch (e) {
      setToast(e.friendly || 'Refresh failed')
    } finally {
      setBusy(false)
      setTimeout(() => setToast(null), 4000)
    }
  }

  const overall = score?.overall_score
  const nIncidents = score?.n_incidents ?? 0
  const outages = score?.outages ?? 0
  const regions = score?.per_region || {}

  // Show skeleton instead of full-page spinner — layout is visible instantly
  if (loading) return (
    <div className="space-y-4 animate-fade-up">
      <div className="glass-strong px-5 py-3 h-14 skeleton" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0,1,2,3].map(i => <div key={i} className="glass-strong h-24 skeleton" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="glass h-48 skeleton" />
        <div className="glass lg:col-span-2 h-48 skeleton" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="glass h-64 skeleton" />
        <div className="glass h-64 skeleton" />
      </div>
    </div>
  )

  const lastEtl = etl?.last_run
  // Fallback: if grid score shows incidents but no ETL history, data IS loaded
  const etlEffectivelyRan = lastEtl || (score?.n_incidents > 0)

  return (
    <div className="space-y-4 animate-fade-up">
      {/* ===== ETL status banner — always visible at the top of Dashboard ===== */}
      {etlEffectivelyRan ? (
        <motion.div
          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
          className="glass-strong border-l-4 px-5 py-3 flex flex-wrap items-center gap-3"
          style={{ borderLeftColor: '#2EB99B' }}
        >
          <CheckCircle2 className="w-5 h-5 text-mint-700 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-ink-900">
              ETL Run Completed
            </div>
            <div className="text-xs text-ink-500">
              Last run: <b>{fmtTime(lastEtl?.ts)}</b>
              {' '}<span className="text-ink-300">({fmtAgo(lastEtl?.ts)})</span>
              {' · '}<span className="font-mono">{lastEtl?.filename}</span>
              {' · '}{lastEtl?.chunks_written?.toLocaleString()} chunks
              {' · '}{lastEtl?.vectors_total?.toLocaleString()} vectors
              {' · '}{lastEtl?.duration_seconds}s
            </div>
          </div>
          <span className="text-[10px] uppercase tracking-wider font-bold bg-mint-500/20 text-mint-700 px-2 py-1 rounded-full">
            ✓ Completed
          </span>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
          className="glass-strong border-l-4 px-5 py-3 flex flex-wrap items-center gap-3"
          style={{ borderLeftColor: '#FFA552' }}
        >
          <AlertOctagon className="w-5 h-5 text-orange-700 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-ink-900">
              ETL Yet To Run
            </div>
            <div className="text-xs text-ink-500">
              Go to the <b>ETL</b> tab → click <b>Run ETL</b> on a dataset to populate the dashboard.
            </div>
          </div>
          <button onClick={() => nav('/etl')}
                  className="btn-accent text-xs !py-1.5 !px-3"
                  style={{ background: '#FFA552' }}>
            Open ETL tab
          </button>
        </motion.div>
      )}

      {/* Action row */}
      <div className="flex flex-wrap items-center gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Dashboard</h2>
        <span className="text-xs text-ink-300">
          Smart-grid operations overview
          {loadedAt && <> · widgets loaded at {loadedAt.toLocaleTimeString()}</>}
        </span>
        <div className="ml-auto flex gap-2">
          <button onClick={load} disabled={loading} className="btn-secondary !py-2"
                  title="Just re-fetch widget data — no ETL re-run">
            <RefreshCw className={'w-4 h-4 ' + (loading ? 'animate-spin' : '')} />
            Reload widgets
          </button>
          <button onClick={refreshData} disabled={busy}
                  className="btn-primary"
                  style={{ background: '#5EE6C8', color: '#0F1B2D' }}
                  title="Re-run ETL across all CSVs in datasets/">
            <RefreshCw className={'w-4 h-4 ' + (busy ? 'animate-spin' : '')} />
            Refresh Data (ETL)
          </button>
        </div>
      </div>

      {/* Error banner — show which endpoints failed, instead of silent empty state */}
      {Object.keys(errors).length > 0 && (
        <div className="glass-strong px-4 py-3 text-sm border-l-4" style={{ borderLeftColor: '#FF7A45' }}>
          <div className="font-semibold text-orange-700 mb-1">
            Some widgets couldn't load — check backend terminal for tracebacks
          </div>
          <ul className="text-xs text-ink-500 space-y-0.5">
            {Object.entries(errors).map(([k, v]) =>
              <li key={k}><b className="font-mono">{k}:</b> {v}</li>)}
          </ul>
          <p className="text-xs text-ink-300 mt-2">
            If you just ran ETL: wait a few seconds and click <b>Reload widgets</b>.
            If all show "failed": the backend is unhealthy — open
            {' '}<a href="http://localhost:8000/api/v1/health" target="_blank" rel="noreferrer"
              className="text-mint-700 underline">/api/v1/health</a>.
          </p>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Grid Health Score" value={overall != null ? Math.round(overall) : '—'}
                    sub={overall != null ? '0–100 · higher is better' : 'no incidents yet'}
                    accent="#5EE6C8" icon={Gauge} delay={0.0} />
        <MetricCard label="Incidents Indexed" value={nIncidents}
                    sub="in vector store" accent="#4DA8FF" icon={Activity} delay={0.05} />
        <MetricCard label="Outage Events" value={outages}
                    sub="from telemetry" accent="#FF7A45" icon={AlertTriangle} delay={0.10} />
        <MetricCard label="Regions Tracked" value={Object.keys(regions).length}
                    sub="per-region scores" accent="#B79CFF" icon={Zap} delay={0.15} />
      </div>

      {/* Gauge + region bars */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <GlassCard title="Health gauge" accent="#5EE6C8">
          <HealthGauge score={overall} />
        </GlassCard>

        <GlassCard title="Region health" subtitle="Click a bar to filter Failure Analysis"
                   className="lg:col-span-2" accent="#5EE6C8">
          <RegionBars perRegion={regions}
                      onSelect={(r) => nav(`/failure?region=${encodeURIComponent(r)}`)} />
        </GlassCard>
      </div>

      {/* Timeline + Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <GlassCard title="Incident timeline" subtitle="Severity over time" accent="#FFD166">
          <TimelineArea buckets={time?.buckets || []} series={time?.series || {}} height={240} />
        </GlassCard>

        <GlassCard title="Incident heatmap" subtitle="Click a cell to drill in"
                   accent="#F47B7B">
          <HeatmapGrid
            regions={heat?.regions || []}
            severities={heat?.severities || []}
            matrix={heat?.matrix || []}
            onSelect={(c) => c.count > 0 && nav(`/heatmap`)}
          />
        </GlassCard>
      </div>

      {/* Predictive Grid Failure Intelligence */}
      {predict && predict.status === 'ok' && (
        <GlassCard
          title="🔮 Predictive Grid Intelligence"
          subtitle={`${predict.n_incidents_analysed} windows analysed · ${predict.n_regions} regions · Highest risk: ${predict.highest_risk_region || 'N/A'}`}
          accent="#FF7A45"
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-3">
            <div className="surface p-3 text-center">
              <div className="text-[10px] text-ink-300 uppercase mb-1">Overall Risk Score</div>
              <div className={`text-2xl font-bold ${
                predict.overall.risk_level === 'critical' ? 'text-orange-700' :
                predict.overall.risk_level === 'high' ? 'text-orange-500' :
                predict.overall.risk_level === 'medium' ? 'text-yellow-600' : 'text-mint-700'
              }`}>{Math.round(predict.overall.risk_score * 100)}%</div>
              <div className={`pill mt-1 ${
                predict.overall.risk_level === 'critical' ? 'pill-critical' :
                predict.overall.risk_level === 'high' ? 'pill-high' :
                predict.overall.risk_level === 'medium' ? 'pill-medium' : 'pill-low'
              }`}>{predict.overall.risk_level}</div>
            </div>
            <div className="surface p-3 lg:col-span-2">
              <div className="text-[10px] text-ink-300 uppercase mb-2">Global Alerts</div>
              <ul className="space-y-1">
                {predict.global_alerts.slice(0, 3).map((a, i) => (
                  <li key={i} className="text-xs text-ink-700">{a}</li>
                ))}
              </ul>
            </div>
          </div>
          {predict.overall.recommendations?.length > 0 && (
            <div>
              <div className="text-[10px] text-ink-300 uppercase mb-2">Recommended Pre-emptive Actions</div>
              <ul className="space-y-1">
                {predict.overall.recommendations.slice(0, 3).map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span className={'pill ' + (r.priority === 'critical' ? 'pill-critical' : r.priority === 'high' ? 'pill-high' : 'pill-medium')}>{r.priority}</span>
                    <span className="text-ink-700">{r.action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </GlassCard>
      )}

      {/* Recent recommendations */}
      <GlassCard title="Recent recommendations" subtitle="Last operator queries"
                 accent="#6FE38A">
        {!recs?.recommendations?.length ? (
          <p className="text-sm text-ink-300">No recommendations yet. Use the Query Console.</p>
        ) : (
          <ul className="space-y-2">
            {recs.recommendations.slice(0, 5).map((r, i) => (
              <li key={i} className="surface p-3">
                <div className="text-xs text-ink-300">
                  {r.operator || 'operator'}
                  {r.ts != null ? ' · ' + (r.confidence != null ? Math.round(r.confidence * 100) + '% confidence' : '') : ''}
                </div>
                <div className="text-sm text-ink-700 mt-1">{r.query || ''}</div>
                {r.answer && (
                  <div className="text-xs text-ink-500 mt-1 line-clamp-2">{r.answer}</div>
                )}
                {Array.isArray(r.recommendations) && r.recommendations.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {r.recommendations.slice(0, 3).map((rec, j) => (
                      <li key={j} className="flex items-start gap-2 text-xs">
                        <span className={'pill ' + (rec.priority === 'critical' ? 'pill-critical' : rec.priority === 'high' ? 'pill-high' : rec.priority === 'medium' ? 'pill-medium' : 'pill-low')}>
                          {rec.priority || 'info'}
                        </span>
                        <span className="text-ink-700">{rec.action}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </GlassCard>
    </div>
  )
}

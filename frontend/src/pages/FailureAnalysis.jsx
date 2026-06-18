/**
 * FailureAnalysis page — lets operators filter incidents by severity/region,
 * view a severity distribution pie, inspect matched incident records, and study
 * the Pearson correlation matrix between key telemetry metrics.
 */
import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, ChevronDown } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import SeverityPie from '../components/charts/SeverityPie.jsx'
import { useApi } from '../hooks/useApi.js'
import { SearchIncidents, Heatmap, AnomalyCorrelations } from '../services/api.js'

const SEVERITIES = ['', 'low', 'medium', 'high', 'critical']

/**
 * Maps a Pearson r value to an RGBA colour string.
 * Positive correlations use mint-green; negative correlations use orange.
 * The alpha is the absolute value so stronger correlations appear more vivid.
 */
function corrColor(v) {
  if (v == null) return 'rgba(240,240,240,0.6)'
  const a = Math.abs(v).toFixed(2)
  return v >= 0
    ? ('rgba(94,230,200,' + a + ')')
    : ('rgba(255,122,69,' + a + ')')
}

/**
 * CorrelationMatrix — renders a colour-coded Pearson r table for anomaly metrics.
 * Shows a skeleton while loading and falls back gracefully to an empty-state message.
 */
function CorrelationMatrix({ data }) {
  if (!data) return (
    <div className="space-y-2">
      <div className="h-4 w-48 skeleton rounded" />
      <div className="grid grid-cols-6 gap-1">
        {Array.from({length:30}).map((_,i) => <div key={i} className="h-9 skeleton rounded-lg" />)}
      </div>
    </div>
  )
  const { metrics = [], matrix = [], insights = [], n_samples = 0 } = data
  if (!metrics.length) {
    return (
      <p className="text-sm text-ink-300 py-4 text-center">
        No telemetry data — run ETL first to compute correlations.
      </p>
    )
  }
  return (
    <div>
      <div className="text-xs text-ink-300 mb-3">
        {n_samples.toLocaleString()} telemetry windows
      </div>
      <div className="overflow-x-auto">
        <table className="text-xs border-separate border-spacing-1 mx-auto">
          <thead>
            <tr>
              <th className="w-28 text-right pr-2 text-ink-300 font-normal" />
              {metrics.map((m) => (
                <th key={m} className="text-center w-20 text-ink-500 font-medium pb-1 px-1 text-[10px]">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map((m1, i) => (
              <tr key={m1}>
                <td className="text-right pr-2 text-ink-500 font-medium text-[10px] whitespace-nowrap">{m1}</td>
                {(matrix[i] || []).map((v, j) => (
                  <td key={j}
                      className="text-center rounded-lg h-9 w-20 font-semibold transition-all"
                      style={{ background: corrColor(v), color: Math.abs(v || 0) > 0.4 ? '#0f1b2d' : '#7f8aa3' }}
                      title={m1 + ' vs ' + metrics[j] + ': r=' + v}>
                    {v != null ? (v === 1 ? '1.00' : v.toFixed(2)) : '--'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-center gap-6 mt-3 text-[10px] text-ink-300">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ background: 'rgba(255,122,69,0.8)' }} />
          Negative
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-white/60 border border-ink-200" />
          None
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ background: 'rgba(94,230,200,0.8)' }} />
          Positive
        </span>
      </div>
      {insights.length > 0 && (
        <div className="mt-4">
          <div className="text-[10px] text-ink-300 uppercase tracking-wide mb-2">Key Insights</div>
          <ul className="space-y-1.5">
            {insights.map((s, i) => (
              <li key={i} className="surface px-3 py-2 text-xs text-ink-700">{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function FailureAnalysis() {
  const [severity, setSeverity] = useState('critical')
  const [region,   setRegion]   = useState('')
  const [open,     setOpen]     = useState(null)

  const heat = useApi(Heatmap, [])
  const corr = useApi(AnomalyCorrelations, [])
  const inc  = useApi(
    () => SearchIncidents({ severity: severity || undefined, region: region || undefined, limit: 30 }),
    [severity, region],
  )

  /* Sum each severity column across all regions to get total counts for the pie chart. */
  const sevCounts = useMemo(() => {
    if (!heat.data) return {}
    const out = {}
    heat.data.severities.forEach((s, si) => {
      out[s] = heat.data.matrix.reduce((sum, row) => sum + (row[si] || 0), 0)
    })
    return out
  }, [heat.data])

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Failure Analysis</h2>
        <span className="text-xs text-ink-300">Severity distribution + Incidents + Anomaly Correlations</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <GlassCard title="Severity distribution" accent="#FF7A45">
          <SeverityPie counts={sevCounts} />
        </GlassCard>

        <GlassCard title="Filters" subtitle="Drill down by severity / region"
                   className="lg:col-span-2" accent="#FF7A45">
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="block text-xs text-ink-300 mb-1">Severity</label>
              <select value={severity} onChange={(e) => setSeverity(e.target.value)}
                      className="bg-white/80 border border-white/60 rounded-xl px-3 py-2 text-sm outline-none">
                {SEVERITIES.map((s) => <option key={s} value={s}>{s || 'any'}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-ink-300 mb-1">Region</label>
              <select value={region} onChange={(e) => setRegion(e.target.value)}
                      className="bg-white/80 border border-white/60 rounded-xl px-3 py-2 text-sm outline-none">
                <option value="">any</option>
                {(heat.data?.regions || []).map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div className="ml-auto self-end text-sm text-ink-500">
              {inc.data?.count ?? 0} incident(s) match
            </div>
          </div>
        </GlassCard>
      </div>

      <GlassCard title="Matching incidents" accent="#FF7A45">
        {inc.loading ? (
          <div className="space-y-2">
            {[0,1,2,3].map(i => <div key={i} className="h-12 skeleton rounded-xl" />)}
          </div>
        ) : !inc.data?.incidents?.length ? (
          <p className="text-sm text-ink-300">No incidents match these filters.</p>
        ) : (
          <ul className="space-y-1.5">
            {inc.data.incidents.map((c) => {
              const isOpen = open === c.id
              const sev = c.metadata?.severity || 'medium'
              return (
                <li key={c.id} className="surface">
                  <button onClick={() => setOpen(isOpen ? null : c.id)}
                          className="w-full text-left p-3 flex items-center gap-3">
                    <AlertTriangle className="w-4 h-4 text-orange-700 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-ink-300 font-mono truncate">{c.id}</div>
                      <div className="text-sm text-ink-900 truncate">
                        {c.metadata?.region} · {c.metadata?.source_dataset}
                      </div>
                    </div>
                    <span className={'pill pill-' + sev}>{sev}</span>
                    <ChevronDown className={'w-4 h-4 transition-transform ' + (isOpen ? 'rotate-180' : '')} />
                  </button>
                  {isOpen && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                className="px-3 pb-3 text-xs space-y-2">
                      <p className="text-ink-700 leading-relaxed">{c.text}</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-ink-500">
                        <div><b>voltage</b>: {c.metadata?.voltage_mean?.toFixed?.(1)}</div>
                        <div><b>frequency</b>: {c.metadata?.frequency_mean?.toFixed?.(2)}</div>
                        <div><b>demand</b>: {c.metadata?.demand_max?.toFixed?.(2)}</div>
                        <div><b>stability</b>: {c.metadata?.stability_score_mean?.toFixed?.(2)}</div>
                      </div>
                    </motion.div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </GlassCard>

      <GlassCard
        title="Anomaly Correlation Matrix"
        subtitle="Pearson r between voltage deviation, frequency drift, demand, stability, and outage events"
        accent="#B79CFF"
      >
        <CorrelationMatrix data={corr.data} />
      </GlassCard>
    </div>
  )
}

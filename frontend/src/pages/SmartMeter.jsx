/**
 * SmartMeter page — household consumption anomaly detection dashboard.
 * Shows KPI tiles, anomaly detection thresholds, severity pie, demand/voltage trend,
 * and an expandable incident inspector sorted worst-first.
 */
import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Gauge, AlertCircle, Activity, Zap, ChevronDown, Filter } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import TelemetryLineChart from '../components/charts/TelemetryLineChart.jsx'
import SeverityPie from '../components/charts/SeverityPie.jsx'
import MetricCard from '../components/cards/MetricCard.jsx'
import { useApi } from '../hooks/useApi.js'
import { SearchIncidents, Telemetry } from '../services/api.js'

const ANOMALY_THRESHOLDS = {
  voltage_low:   210,   // V — below this = under-voltage
  voltage_high:  250,   // V — above this = over-voltage
  demand_high:   2.5,   // kW — above this = high consumption
  stability_low: -0.2,  // below this = unstable window
}

/**
 * AnomalyBadge — displays a HIGH/LOW/OK pill for a single telemetry metric.
 * Compares `value` against optional `low` and `high` thresholds and picks the
 * appropriate severity colour.
 */
function AnomalyBadge({ value, low, high, unit }) {
  if (value == null) return null
  const v = parseFloat(value)
  if (high != null && v > high) return <span className="pill pill-critical">HIGH {v?.toFixed(1)}{unit}</span>
  if (low  != null && v < low)  return <span className="pill pill-high">LOW {v?.toFixed(1)}{unit}</span>
  return <span className="pill pill-low">OK {v?.toFixed(1)}{unit}</span>
}

export default function SmartMeter() {
  const [open, setOpen] = useState(null)
  const [severityFilter, setSeverityFilter] = useState('')

  const inc  = useApi(
    () => SearchIncidents({ source: 'household', limit: 100, severity: severityFilter || undefined }),
    [severityFilter]
  )
  const tele = useApi(() => Telemetry(200), [])

  const householdSamples = useMemo(
    () => (tele.data?.samples || []).filter(
      (s) => s.voltage != null || s.demand != null
    ),
    [tele.data]
  )

  const sevCounts = useMemo(() => {
    const out = { low: 0, medium: 0, high: 0, critical: 0 }
    inc.data?.incidents?.forEach((c) => {
      const s = c.metadata?.severity
      if (s in out) out[s]++
    })
    return out
  }, [inc.data])

  const anomalous = (inc.data?.incidents || []).filter(
    (c) => c.metadata?.severity === 'high' || c.metadata?.severity === 'critical'
  )
  const total = inc.data?.count ?? 0
  const anomalyRate = total > 0 ? Math.round((anomalous.length / total) * 100) : 0

  // Sort incidents: anomalous first, then by severity
  const sevOrder = { critical: 0, high: 1, medium: 2, low: 3 }
  const sorted = useMemo(() => {
    return [...(inc.data?.incidents || [])].sort(
      (a, b) => (sevOrder[a.metadata?.severity] ?? 4) - (sevOrder[b.metadata?.severity] ?? 4)
    )
  }, [inc.data])

  if (inc.loading) return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <div className="h-7 w-64 skeleton rounded-lg" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0,1,2,3].map(i => <div key={i} className="glass-strong h-24 skeleton" />)}
      </div>
      <div className="glass h-20 skeleton" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="glass h-48 skeleton" />
        <div className="glass lg:col-span-2 h-48 skeleton" />
      </div>
      <div className="glass h-64 skeleton" />
    </div>
  )

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Smart Meter Intelligence</h2>
        <span className="text-xs text-ink-300">Household consumption anomaly detection</span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Total Readings" value={total} accent="#B79CFF" icon={Gauge}
                    sub="household windows" delay={0.0} />
        <MetricCard label="Anomalous Windows" value={anomalous.length} accent="#FF7A45" icon={AlertCircle}
                    sub="high or critical severity" delay={0.05} />
        <MetricCard label="Anomaly Rate" value={anomalyRate + '%'} accent="#FFA552" icon={Activity}
                    sub={anomalyRate > 20 ? '⚠ Above 20% threshold' : 'Within normal range'} delay={0.1} />
        <MetricCard label="Critical Incidents" value={sevCounts.critical ?? 0} accent="#FF4444" icon={Zap}
                    sub="immediate attention needed" delay={0.15} />
      </div>

      {/* Anomaly thresholds info */}
      <GlassCard title="Anomaly Detection Thresholds" accent="#B79CFF"
                 subtitle="Windows exceeding these thresholds are flagged as anomalous">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          {[
            { label: 'Under-voltage', value: `< ${ANOMALY_THRESHOLDS.voltage_low}V`, color: '#4DA8FF' },
            { label: 'Over-voltage',  value: `> ${ANOMALY_THRESHOLDS.voltage_high}V`, color: '#FF7A45' },
            { label: 'High demand',   value: `> ${ANOMALY_THRESHOLDS.demand_high}kW`, color: '#FFD166' },
            { label: 'Instability',   value: `stability < ${ANOMALY_THRESHOLDS.stability_low}`, color: '#FF4444' },
          ].map((t) => (
            <div key={t.label} className="surface px-3 py-2 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: t.color }} />
              <div>
                <div className="font-medium text-ink-700">{t.label}</div>
                <div className="text-ink-300 font-mono">{t.value}</div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <GlassCard title="Severity Distribution" accent="#B79CFF">
          <SeverityPie counts={sevCounts} />
        </GlassCard>
        <GlassCard title="Demand & Voltage Trend" className="lg:col-span-2" accent="#B79CFF">
          {tele.loading
            ? <LoadingDots label="Loading telemetry" />
            : <TelemetryLineChart samples={householdSamples} series={['demand', 'voltage']} />
          }
        </GlassCard>
      </div>

      {/* Incident inspector */}
      <GlassCard
        title="Anomaly Inspector"
        subtitle={`${sorted.length} household incidents`}
        accent="#B79CFF"
        right={
          <div className="flex gap-2 items-center">
            <Filter className="w-3.5 h-3.5 text-ink-300" />
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}
                    className="bg-white/80 border border-white/60 rounded-lg px-2 py-1 text-xs outline-none">
              <option value="">All severities</option>
              {['critical', 'high', 'medium', 'low'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        }
      >
        {!sorted.length ? (
          <p className="text-sm text-ink-300 py-4 text-center">
            No household incidents found. Run ETL with household_power_consumption.csv to populate.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {sorted.slice(0, 20).map((c) => {
              const isOpen = open === c.id
              const sev = c.metadata?.severity || 'low'
              const isAnomaly = sev === 'high' || sev === 'critical'
              return (
                <li key={c.id} className={'surface ' + (isAnomaly ? 'ring-1 ring-orange-300/50' : '')}>
                  <button onClick={() => setOpen(isOpen ? null : c.id)}
                          className="w-full text-left p-3 flex items-center gap-3">
                    {isAnomaly
                      ? <AlertCircle className="w-4 h-4 text-orange-700 shrink-0 animate-pulse" />
                      : <Activity className="w-4 h-4 text-mint-700 shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-ink-300 font-mono truncate">{c.id}</div>
                      <div className="text-sm text-ink-900">
                        {c.metadata?.region || 'Unknown'} ·{' '}
                        <span className="text-ink-500">{c.metadata?.window_start || '—'}</span>
                      </div>
                    </div>
                    <span className={'pill pill-' + sev}>{sev}</span>
                    <ChevronDown className={'w-4 h-4 text-ink-300 transition-transform ' + (isOpen ? 'rotate-180' : '')} />
                  </button>
                  {isOpen && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                className="px-3 pb-3 text-xs space-y-2">
                      <p className="text-ink-700 leading-relaxed">{c.text}</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <div className="surface px-2 py-1.5">
                          <div className="text-ink-300">Voltage</div>
                          <AnomalyBadge value={c.metadata?.voltage_mean}
                            low={ANOMALY_THRESHOLDS.voltage_low} high={ANOMALY_THRESHOLDS.voltage_high} unit="V" />
                        </div>
                        <div className="surface px-2 py-1.5">
                          <div className="text-ink-300">Demand</div>
                          <AnomalyBadge value={c.metadata?.demand_max}
                            high={ANOMALY_THRESHOLDS.demand_high} unit="kW" />
                        </div>
                        <div className="surface px-2 py-1.5">
                          <div className="text-ink-300">Frequency</div>
                          <div className="font-mono font-semibold text-ink-700">
                            {c.metadata?.frequency_mean?.toFixed?.(2)} Hz
                          </div>
                        </div>
                        <div className="surface px-2 py-1.5">
                          <div className="text-ink-300">Stability</div>
                          <div className={`font-mono font-semibold ${
                            (c.metadata?.stability_score_mean || 0) < ANOMALY_THRESHOLDS.stability_low
                              ? 'text-orange-700' : 'text-mint-700'
                          }`}>{c.metadata?.stability_score_mean?.toFixed?.(3)}</div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </GlassCard>
    </div>
  )
}

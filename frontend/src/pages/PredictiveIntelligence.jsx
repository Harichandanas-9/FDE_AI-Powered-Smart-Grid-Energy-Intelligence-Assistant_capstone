import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, TrendingUp, Zap, RefreshCw } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import MetricCard from '../components/cards/MetricCard.jsx'
import { useApi } from '../hooks/useApi.js'
import { Predict } from '../services/api.js'

const RISK_COLOR = {
  critical: '#FF4444',
  high:     '#FF7A45',
  medium:   '#FFD166',
  low:      '#5EE6C8',
}

const RISK_PILL = {
  critical: 'pill-critical',
  high:     'pill-high',
  medium:   'pill-medium',
  low:      'pill-low',
}

export default function PredictiveIntelligence() {
  const { data, loading, reload } = useApi(Predict, [])

  if (loading) return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <div className="h-7 w-64 skeleton rounded-lg" />
        <div className="h-4 w-32 skeleton rounded ml-2" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0,1,2,3].map(i => <div key={i} className="glass-strong h-24 skeleton" />)}
      </div>
      <div className="glass h-32 skeleton" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[0,1,2,3].map(i => <div key={i} className="glass h-40 skeleton" />)}
      </div>
    </div>
  )

  const pred = data

  if (!pred || pred.status === 'no_data') {
    return (
      <div className="space-y-3 animate-fade-up">
        <h2 className="text-xl font-bold text-ink-900 px-1">Predictive Intelligence</h2>
        <GlassCard accent="#FF7A45">
          <div className="text-center py-8">
            <AlertTriangle className="w-8 h-8 text-ink-300 mx-auto mb-2" />
            <p className="text-sm text-ink-500">No telemetry data yet. Run ETL first.</p>
          </div>
        </GlassCard>
      </div>
    )
  }

  const overall = pred.overall || {}
  const perRegion = pred.per_region || {}

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">🔮 Predictive Grid Intelligence</h2>
        <span className="text-xs text-ink-300">
          {pred.n_incidents_analysed} windows · {pred.n_regions} regions
        </span>
        <button onClick={reload} className="btn-secondary !py-1.5 ml-auto">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Overall Risk"
          value={Math.round(overall.risk_score * 100) + '%'}
          sub={overall.risk_level}
          accent={RISK_COLOR[overall.risk_level] || '#5EE6C8'}
          icon={TrendingUp}
        />
        <MetricCard
          label="Voltage Deviation"
          value={overall.voltage_deviation_pct?.toFixed(1) + '%'}
          sub="from 230V nominal"
          accent="#4DA8FF"
          icon={Zap}
        />
        <MetricCard
          label="Frequency Drift"
          value={overall.frequency_deviation_hz?.toFixed(3) + ' Hz'}
          sub="from 50Hz nominal"
          accent="#4DE2F0"
          icon={Zap}
        />
        <MetricCard
          label="Transformer Overload"
          value={overall.transformer_overload_pct?.toFixed(0) + '%'}
          sub="of windows at risk"
          accent="#FF7A45"
          icon={AlertTriangle}
        />
      </div>

      {/* Global alerts */}
      <GlassCard title="Global Alerts" accent="#FF7A45">
        <ul className="space-y-2">
          {(pred.global_alerts || []).map((a, i) => (
            <li key={i} className="surface px-3 py-2 text-sm text-ink-700">{a}</li>
          ))}
        </ul>
      </GlassCard>

      {/* Overall recommendations */}
      {overall.recommendations?.length > 0 && (
        <GlassCard title="Pre-emptive Actions" subtitle="Recommended immediately based on predictive analysis" accent="#6FE38A">
          <ul className="space-y-2">
            {overall.recommendations.map((r, i) => (
              <motion.li key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                         transition={{ delay: i * 0.05 }}
                         className="surface p-3 flex items-start gap-3">
                <span className={'pill shrink-0 ' + (RISK_PILL[r.priority] || 'pill-medium')}>{r.priority}</span>
                <div>
                  <div className="text-sm text-ink-900">{r.action}</div>
                  <div className="text-xs text-ink-300 mt-0.5">Category: {r.category}</div>
                </div>
              </motion.li>
            ))}
          </ul>
        </GlassCard>
      )}

      {/* Per-region predictions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {Object.entries(perRegion)
          .sort(([, a], [, b]) => b.risk_score - a.risk_score)
          .map(([region, p]) => (
            <motion.div key={region} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard
                title={region}
                subtitle={`Risk: ${Math.round(p.risk_score * 100)}% · ${p.n_windows_analysed} windows`}
                accent={RISK_COLOR[p.risk_level] || '#5EE6C8'}
                right={<span className={'pill ' + (RISK_PILL[p.risk_level] || 'pill-low')}>{p.risk_level}</span>}
              >
                <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
                  <div className="surface py-2 px-3">
                    <div className="text-ink-300">Voltage Dev</div>
                    <div className="font-bold">{p.voltage_deviation_pct?.toFixed(1)}%</div>
                  </div>
                  <div className="surface py-2 px-3">
                    <div className="text-ink-300">Freq Drift</div>
                    <div className="font-bold">{p.frequency_deviation_hz?.toFixed(3)} Hz</div>
                  </div>
                  <div className="surface py-2 px-3">
                    <div className="text-ink-300">Stability</div>
                    <div className="font-bold">{p.avg_stability_index?.toFixed(3)}</div>
                  </div>
                  <div className="surface py-2 px-3">
                    <div className="text-ink-300">Outages</div>
                    <div className="font-bold text-orange-700">{p.outage_events}</div>
                  </div>
                </div>
                {p.alerts?.length > 0 && (
                  <div className="text-xs space-y-1">
                    {p.alerts.slice(0, 2).map((a, i) => (
                      <div key={i} className="text-ink-500">{a}</div>
                    ))}
                  </div>
                )}
              </GlassCard>
            </motion.div>
          ))}
      </div>
    </div>
  )
}

/**
 * GridStability page — displays the overall grid health score, per-region breakdown,
 * a live telemetry line chart, and a 3-day demand forecasting panel.
 */
import { TrendingUp } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import HealthGauge from '../components/charts/HealthGauge.jsx'
import RegionBars from '../components/charts/RegionBars.jsx'
import TelemetryLineChart from '../components/charts/TelemetryLineChart.jsx'
import { useApi } from '../hooks/useApi.js'
import { GridScore, Telemetry, DemandForecast } from '../services/api.js'

/**
 * ForecastChart — merges actuals, rolling average, and 3-day forecast series into a
 * single Recharts LineChart with a reference line separating historical from predicted data.
 */
function ForecastChart({ data }) {
  if (!data) return (
    <div className="space-y-2">
      <div className="flex gap-4 mb-3">
        {[0,1,2].map(i => <div key={i} className="h-3 w-24 skeleton rounded" />)}
      </div>
      <div className="h-64 skeleton rounded-xl" />
    </div>
  )

  const { actuals = [], rolling_avg = [], forecast = [], n_days = 0 } = data

  /* Merge the three series by date so Recharts can render them on a single axis. */
  const byDate = {}
  actuals.forEach(    ({ date, demand }) => { byDate[date] = { ...byDate[date], date, actual: demand } })
  rolling_avg.forEach(({ date, demand }) => { byDate[date] = { ...byDate[date], date, rolling: demand } })
  forecast.forEach(   ({ date, demand }) => { byDate[date] = { ...byDate[date], date, forecast: demand } })

  const chartData = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  const lastActualDate = actuals.at(-1)?.date

  if (!chartData.length) {
    return (
      <p className="text-sm text-ink-300 py-6 text-center">
        No demand data yet — run ETL to populate forecasting.
      </p>
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 mb-3 text-[11px] text-ink-400">
        <span className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 inline-block rounded" style={{ background: '#4DA8FF' }} />
          Actual (avg/day)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 inline-block rounded" style={{ background: '#5EE6C8' }} />
          3-day rolling avg
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-4 inline-block border-t-2 border-dashed" style={{ borderColor: '#FF7A45' }} />
          Forecast (+3 days)
        </span>
        <span className="ml-auto text-ink-300">{n_days} historical days</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(63,75,102,0.12)" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
          <YAxis tick={{ fontSize: 10 }} unit=" kW" width={58} />
          <Tooltip
            contentStyle={{ background: 'rgba(255,255,255,0.95)', border: 'none', borderRadius: 8, fontSize: 12 }}
            formatter={(v, name) => [v != null ? (Number(v).toFixed(2) + ' kW') : '--', name]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {lastActualDate && (
            <ReferenceLine x={lastActualDate} stroke="#d1d5db" strokeDasharray="4 2"
                           label={{ value: 'Forecast ->', position: 'insideTopRight', fontSize: 9, fill: '#9ca3af' }} />
          )}
          <Line type="monotone" dataKey="actual"   name="Actual"      stroke="#4DA8FF" strokeWidth={2} dot={false} connectNulls />
          <Line type="monotone" dataKey="rolling"  name="Rolling avg" stroke="#5EE6C8" strokeWidth={2} dot={false} connectNulls strokeDasharray="6 3" />
          <Line type="monotone" dataKey="forecast" name="Forecast"    stroke="#FF7A45" strokeWidth={2} dot={{ r: 5, fill: '#FF7A45' }} connectNulls strokeDasharray="4 4" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function GridStability() {
  const score    = useApi(GridScore, [])
  const tele     = useApi(() => Telemetry(150), [])
  const forecast = useApi(DemandForecast, [])

  if (score.loading) return (
    <div className="space-y-3 animate-fade-up">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="glass h-48 skeleton" />
        <div className="glass lg:col-span-2 h-48 skeleton" />
      </div>
      <div className="glass h-48 skeleton" />
      <div className="glass h-72 skeleton" />
    </div>
  )

  const s       = score.data || {}
  const samples = tele.data?.samples || []

  const nextDemand = forecast.data?.forecast?.[0]?.demand
  const lastActual = forecast.data?.actuals?.at(-1)?.demand
  const trendPct   = nextDemand && lastActual
    ? (((nextDemand - lastActual) / lastActual) * 100).toFixed(1)
    : null

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Grid Stability</h2>
        <span className="text-xs text-ink-300">Voltage · Frequency · Demand · Stability</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <GlassCard title="Overall health" accent="#4DA8FF">
          <HealthGauge score={s.overall_score} label="Grid Health" />
          <div className="grid grid-cols-2 gap-2 mt-2 text-center">
            <div className="surface py-2">
              <div className="text-[10px] text-ink-300 uppercase">Incidents</div>
              <div className="text-lg font-bold">{s.n_incidents ?? 0}</div>
            </div>
            <div className="surface py-2">
              <div className="text-[10px] text-ink-300 uppercase">Outages</div>
              <div className="text-lg font-bold text-orange-700">{s.outages ?? 0}</div>
            </div>
          </div>
        </GlassCard>

        <GlassCard title="Per-region scores" className="lg:col-span-2" accent="#4DA8FF">
          <RegionBars perRegion={s.per_region || {}} />
        </GlassCard>
      </div>

      <GlassCard title="Telemetry trend" subtitle="Voltage + frequency over time" accent="#4DA8FF">
        {tele.loading
          ? <LoadingDots label="Loading telemetry" />
          : <TelemetryLineChart samples={samples} series={['voltage', 'frequency']} />}
      </GlassCard>

      <GlassCard
        title="Demand Forecasting"
        subtitle={
          trendPct != null
            ? ('Next-day: ' + Number(nextDemand).toFixed(2) + ' kW  Trend: ' + (trendPct > 0 ? '+' : '') + trendPct + '% vs today')
            : '3-day rolling average + 3-day future projection'
        }
        accent="#FF7A45"
        right={
          trendPct != null && (
            <span className={('pill flex items-center gap-1 ' + (
              Math.abs(parseFloat(trendPct)) > 5 ? 'pill-high'
              : Math.abs(parseFloat(trendPct)) > 2 ? 'pill-medium'
              : 'pill-low'
            ))}>
              <TrendingUp className="w-3 h-3" />
              {trendPct > 0 ? '+' : ''}{trendPct}%
            </span>
          )
        }
      >
        <ForecastChart data={forecast.data} />
        {forecast.data?.forecast?.length > 0 && (
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
            {forecast.data.forecast.map((f, i) => (
              <div key={i} className="surface py-2 px-1">
                <div className="text-[10px] text-ink-300">{f.date?.slice(5)}</div>
                <div className="font-bold text-orange-600">{Number(f.demand).toFixed(2)} kW</div>
                <div className="text-[10px] text-ink-300">Day +{i + 1}</div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  )
}

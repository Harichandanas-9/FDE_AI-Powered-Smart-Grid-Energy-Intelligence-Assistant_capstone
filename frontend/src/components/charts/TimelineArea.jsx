import {
  AreaChart, Area, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  ResponsiveContainer,
} from 'recharts'

const COLORS = {
  low:      '#A7F1DE',
  medium:   '#D5C5FF',
  high:     '#FFA552',
  critical: '#FF7A45',
}

/**
 * Stacked area chart of incident counts over time, split by severity.
 * Props: { buckets: string[], series: { [sev]: number[] } }
 */
export default function TimelineArea({ buckets = [], series = {}, height = 280 }) {
  if (!buckets.length) {
    return (
      <div className="py-8 text-center">
        <div className="text-2xl mb-2">📅</div>
        <p className="text-sm font-medium text-ink-500">No timeline data yet</p>
        <p className="text-xs text-ink-300 mt-1">Go to the ETL tab and click Run ETL to populate this chart</p>
      </div>
    )
  }
  const data = buckets.map((b, i) => ({
    t: b,
    low:      series.low?.[i]      || 0,
    medium:   series.medium?.[i]   || 0,
    high:     series.high?.[i]     || 0,
    critical: series.critical?.[i] || 0,
  }))

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 5, right: 15, left: -10, bottom: 5 }}>
          <defs>
            {Object.entries(COLORS).map(([k, c]) => (
              <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={c} stopOpacity={0.7} />
                <stop offset="95%" stopColor={c} stopOpacity={0.05} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="rgba(63,75,102,0.08)" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: 'rgba(255,255,255,0.95)', borderRadius: 12,
                            border: '1px solid rgba(0,0,0,0.05)' }}
          />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          {Object.keys(COLORS).map((sev) => (
            <Area key={sev} type="monotone" dataKey={sev} stackId="1"
                  stroke={COLORS[sev]} fill={`url(#g-${sev})`} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

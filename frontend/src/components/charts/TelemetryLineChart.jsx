/**
 * TelemetryLineChart — multi-series time-series line chart for raw telemetry samples.
 * The `series` prop selects which metrics to render (e.g. ['voltage','frequency']).
 * Timestamps are trimmed to "MM-DD HH:mm" for readability on the x-axis.
 */
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  ResponsiveContainer,
} from 'recharts'

/**
 * Multi-series line chart for telemetry samples.
 *
 * Props:
 *   samples: [{ timestamp, voltage, frequency, demand, stability, severity, region }]
 *   series:  ['voltage','frequency','demand','stability']  (subset)
 *   height:  number
 */
const COLORS = {
  voltage:    '#4DA8FF',
  frequency:  '#5EE6C8',
  demand:     '#FFA552',
  stability:  '#B79CFF',
}

export default function TelemetryLineChart({
  samples = [], series = ['voltage', 'frequency'], height = 280,
}) {
  if (!samples.length) {
    return <p className="text-sm text-ink-300 py-6 text-center">No telemetry samples yet.</p>
  }
  const data = samples.map((s) => ({
    t: s.timestamp ? s.timestamp.slice(5, 16).replace('T', ' ') : '',
    voltage:   s.voltage,
    frequency: s.frequency,
    demand:    s.demand,
    stability: s.stability,
  }))

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 15, left: -10, bottom: 5 }}>
          <CartesianGrid stroke="rgba(63,75,102,0.08)" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: 'rgba(255,255,255,0.95)', borderRadius: 12,
                            border: '1px solid rgba(0,0,0,0.05)' }}
          />
          <Legend iconType="line" wrapperStyle={{ fontSize: 12 }} />
          {series.map((k) => (
            <Line key={k} type="monotone" dataKey={k} stroke={COLORS[k] || '#7F8AA3'}
                  dot={false} strokeWidth={2} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

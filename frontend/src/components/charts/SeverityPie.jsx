/**
 * SeverityPie — donut chart that visualises incident counts split by severity level.
 * Expects a `counts` object like { low: N, medium: N, high: N, critical: N }.
 */
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const COLORS = {
  low:      '#A7F1DE',
  medium:   '#D5C5FF',
  high:     '#FFA552',
  critical: '#FF7A45',
  unknown:  '#7F8AA3',
}

/** Filters out zero-count entries so they don't appear as empty slices. */
export default function SeverityPie({ counts = {}, title }) {
  const data = Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }))

  if (!data.length) {
    return <p className="text-sm text-ink-300 py-6 text-center">No severity data yet.</p>
  }

  return (
    <div className="w-full h-56">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name"
               innerRadius={50} outerRadius={80} paddingAngle={3}>
            {data.map((d) => (
              <Cell key={d.name} fill={COLORS[d.name] || '#7F8AA3'} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: 'rgba(255,255,255,0.95)', borderRadius: 12,
                            border: '1px solid rgba(0,0,0,0.05)' }}
          />
          <Legend iconType="circle" verticalAlign="bottom"
                  wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

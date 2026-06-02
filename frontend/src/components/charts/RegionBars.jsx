import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell,
} from 'recharts'

/**
 * Horizontal bar chart of per-region grid health scores.
 * Props: { perRegion: { regionName: score } }
 */
export default function RegionBars({ perRegion = {}, height = 260, onSelect }) {
  const data = Object.entries(perRegion)
    .map(([region, score]) => ({ region, score }))
    .sort((a, b) => a.score - b.score)

  if (!data.length) {
    return <p className="text-sm text-ink-300 py-6 text-center">No region data yet.</p>
  }

  const colorFor = (s) => s >= 75 ? '#5EE6C8' : s >= 50 ? '#FFA552' : '#FF7A45'

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical"
                  margin={{ top: 5, right: 15, left: 10, bottom: 5 }}>
          <CartesianGrid stroke="rgba(63,75,102,0.08)" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
          <YAxis type="category" dataKey="region" tick={{ fontSize: 11 }} width={100} />
          <Tooltip
            contentStyle={{ background: 'rgba(255,255,255,0.95)', borderRadius: 12,
                            border: '1px solid rgba(0,0,0,0.05)' }}
          />
          <Bar dataKey="score" radius={[0, 6, 6, 0]}
               onClick={(d) => onSelect?.(d.region)}
               style={{ cursor: onSelect ? 'pointer' : 'default' }}>
            {data.map((d) => <Cell key={d.region} fill={colorFor(d.score)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

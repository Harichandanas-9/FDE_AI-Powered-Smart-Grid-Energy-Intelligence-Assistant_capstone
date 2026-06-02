import { motion } from 'framer-motion'

/**
 * Semicircular SVG gauge. score in [0..100].
 * Color: red <50, orange <75, mint >=75. Smooth animated needle.
 */
export default function HealthGauge({ score = null, label = 'Grid Health', size = 220 }) {
  const s = typeof score === 'number' ? Math.max(0, Math.min(100, score)) : null
  const color = s == null ? '#7F8AA3'
    : s >= 75 ? '#5EE6C8'
    : s >= 50 ? '#FFA552'
    : '#FF7A45'

  // SVG arc geometry
  const r = (size - 30) / 2
  const cx = size / 2
  const cy = size / 2 + 10
  // semicircle from 180deg to 360deg (or 0)
  const startAngle = Math.PI
  const endAngle   = 2 * Math.PI
  const angleFor = (v) => startAngle + (v / 100) * (endAngle - startAngle)
  const polar = (a) => ({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) })

  const arcPath = (from, to) => {
    const a = polar(from), b = polar(to)
    const large = to - from > Math.PI ? 1 : 0
    return `M ${a.x} ${a.y} A ${r} ${r} 0 ${large} 1 ${b.x} ${b.y}`
  }

  const activeTo = angleFor(s == null ? 0 : s)

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 30} viewBox={`0 0 ${size} ${size / 2 + 30}`}>
        {/* track */}
        <path d={arcPath(startAngle, endAngle)} stroke="#E6FBF6" strokeWidth="14"
              fill="none" strokeLinecap="round" />
        {/* active arc */}
        <motion.path
          d={arcPath(startAngle, activeTo)}
          stroke={color} strokeWidth="14" fill="none" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 1.0, ease: 'easeOut' }}
        />
        {/* center text */}
        <text x={cx} y={cy - 12} textAnchor="middle" className="fill-ink-300"
              fontSize="11" fontWeight="500">{label}</text>
        <text x={cx} y={cy + 18} textAnchor="middle" fill="#0F1B2D"
              fontSize="36" fontWeight="700">
          {s == null ? '—' : Math.round(s)}
        </text>
      </svg>
      <div className="text-xs text-ink-300 -mt-2">
        {s == null ? 'no data yet'
         : s >= 75 ? 'Stable' : s >= 50 ? 'Caution' : 'Critical'}
      </div>
    </div>
  )
}

import { motion } from 'framer-motion'

/**
 * MetricCard — KPI tile with big number + label + optional trend.
 */
export default function MetricCard({
  label, value, sub, accent = '#5EE6C8', icon: Icon, delay = 0,
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      className="glass-strong p-4 flex items-center gap-4 hover:shadow-card-hover transition-shadow"
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: accent + '22', color: accent }}
      >
        {Icon ? <Icon className="w-5 h-5" /> : null}
      </div>
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wider text-ink-300">{label}</div>
        <div className="text-2xl font-bold text-ink-900 leading-tight truncate">
          {value ?? '—'}
        </div>
        {sub && <div className="text-xs text-ink-500 mt-0.5">{sub}</div>}
      </div>
    </motion.div>
  )
}

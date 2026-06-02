import { motion } from 'framer-motion'

/**
 * GlassCard — base premium card. Use `accent` to tint the top border.
 * Props: { accent?: string, title?, subtitle?, right?, className?, children }
 */
export default function GlassCard({
  accent, title, subtitle, right, className = '', children, delay = 0,
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      className={'glass relative overflow-hidden ' + className}
    >
      {accent && (
        <div
          className="absolute inset-x-0 top-0 h-[3px]"
          style={{ background: `linear-gradient(90deg, ${accent}, ${accent}55 60%, transparent)` }}
        />
      )}
      {(title || right) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div>
            {title    && <h3 className="font-semibold text-ink-900">{title}</h3>}
            {subtitle && <p className="text-xs text-ink-300 mt-0.5">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </motion.section>
  )
}

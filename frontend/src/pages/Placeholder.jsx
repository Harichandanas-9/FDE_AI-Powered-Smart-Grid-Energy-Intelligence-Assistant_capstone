/**
 * Placeholder — scaffold component shown for pages whose backend endpoints exist
 * but whose chart visualisations and interactive widgets are not yet implemented.
 * Accepts `title`, `accent`, `description`, and `step` props.
 */
import GlassCard from '../components/cards/GlassCard.jsx'

/** Generic placeholder for pages filled in STEP 11. */
export default function Placeholder({ title, accent = '#5EE6C8', description, step = 'STEP 11' }) {
  return (
    <div className="animate-fade-up">
      <GlassCard title={title} accent={accent} subtitle={description}>
        <div className="text-center py-8">
          <div className="inline-block px-3 py-1 rounded-full bg-mint-100 text-mint-700 text-xs font-semibold mb-3">
            Coming in {step}
          </div>
          <p className="text-sm text-ink-500 max-w-md mx-auto">
            This page is scaffolded. The backend endpoints are already live —
            the chart visualizations and interactive widgets land in {step}.
          </p>
        </div>
      </GlassCard>
    </div>
  )
}

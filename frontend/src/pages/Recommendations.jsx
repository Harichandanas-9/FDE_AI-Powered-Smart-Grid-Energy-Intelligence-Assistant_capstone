/**
 * Recommendations page — displays a paginated grid of the last 20 /analyze responses
 * cached by the backend, showing the query, AI answer, and prioritised action items.
 */
import { motion } from 'framer-motion'
import { Lightbulb, MessageSquare } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import { useApi } from '../hooks/useApi.js'
import { RecentRecs } from '../services/api.js'

export default function Recommendations() {
  const { data, loading, reload } = useApi(() => RecentRecs(20), [])
  const items = data?.recommendations || []

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Recommendations</h2>
        <span className="text-xs text-ink-300">Recent /analyze responses cached on the backend</span>
        <button onClick={reload} className="btn-secondary !py-1.5 ml-auto">Reload</button>
      </div>

      {loading ? <LoadingDots />
       : !items.length ? (
          <GlassCard accent="#6FE38A">
            <div className="text-center py-8">
              <MessageSquare className="w-8 h-8 text-ink-300 mx-auto mb-2" />
              <p className="text-sm text-ink-500">
                No recommendations yet. Use the Query Console to ask the assistant a question.
              </p>
            </div>
          </GlassCard>
       ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((r, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}>
              <GlassCard accent="#6FE38A">
                <div className="text-xs text-ink-300 mb-1">
                  {r.operator || 'anonymous'} ·
                  confidence {Math.round((r.confidence || 0) * 100)}%
                </div>
                <div className="text-sm font-medium text-ink-900 mb-2 line-clamp-2">
                  {r.query}
                </div>
                <p className="text-xs text-ink-700 line-clamp-3 mb-2">{r.answer}</p>
                {r.recommendations?.length > 0 && (
                  <ul className="space-y-1 text-xs">
                    {r.recommendations.slice(0, 3).map((x, j) => (
                      <li key={j} className="flex items-start gap-2">
                        <Lightbulb className="w-3.5 h-3.5 text-mint-700 shrink-0 mt-0.5" />
                        <span>
                          <span className={'pill mr-1 pill-' + (x.priority || 'medium')}>{x.priority}</span>
                          {x.action}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </GlassCard>
            </motion.div>
          ))}
        </div>
       )}
    </div>
  )
}

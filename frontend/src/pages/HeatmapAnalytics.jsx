import { useState } from 'react'
import { motion } from 'framer-motion'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import HeatmapGrid from '../components/charts/HeatmapGrid.jsx'
import { useApi } from '../hooks/useApi.js'
import { Heatmap, SearchIncidents } from '../services/api.js'

export default function HeatmapAnalytics() {
  const [sel, setSel] = useState(null)
  const heat = useApi(Heatmap, [])
  const drill = useApi(
    () => sel ? SearchIncidents({ region: sel.region, severity: sel.severity, limit: 15 })
              : Promise.resolve(null),
    [sel?.region, sel?.severity],
  )

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Heatmap Analytics</h2>
        <span className="text-xs text-ink-300">Click a cell to drill into the matching incidents</span>
      </div>

      <GlassCard title="Region × severity" accent="#F47B7B">
        {heat.loading ? <LoadingDots /> : (
          <HeatmapGrid
            regions={heat.data?.regions || []}
            severities={heat.data?.severities || []}
            matrix={heat.data?.matrix || []}
            onSelect={(c) => c.count > 0 && setSel(c)}
          />
        )}
      </GlassCard>

      {sel && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <GlassCard
            title={`${sel.region} · ${sel.severity}`}
            subtitle={`${sel.count} incident(s) — top 15 below`}
            accent="#F47B7B"
            right={
              <button onClick={() => setSel(null)} className="btn-secondary !py-1 !px-3 text-xs">
                Clear
              </button>
            }
          >
            {drill.loading ? <LoadingDots />
             : !drill.data?.incidents?.length
                ? <p className="text-sm text-ink-300">No incidents found.</p>
                : (
                  <ul className="space-y-1.5">
                    {drill.data.incidents.map((c) => (
                      <li key={c.id} className="surface p-2 text-xs">
                        <div className="text-ink-300 font-mono truncate">{c.id}</div>
                        <div className="text-ink-700 line-clamp-2">{c.text}</div>
                      </li>
                    ))}
                  </ul>
                )}
          </GlassCard>
        </motion.div>
      )}
    </div>
  )
}

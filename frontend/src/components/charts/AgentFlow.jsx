/**
 * AgentFlow — visual pipeline card that renders each step of an agent trace as a
 * labelled card connected by chevrons. Status icons show pass/fail per agent.
 */
import { motion } from 'framer-motion'
import {
  ShieldCheck, Search, Activity, AlertTriangle, Lightbulb, ChevronRight,
  CheckCircle2, XCircle,
} from 'lucide-react'

const ICONS = {
  guardrails:               ShieldCheck,
  retrieval_agent:          Search,
  stability_agent:          Activity,
  failure_analysis_agent:   AlertTriangle,
  recommendation_agent:     Lightbulb,
}

const COLORS = {
  guardrails:               '#5EE6C8',
  retrieval_agent:          '#4DA8FF',
  stability_agent:          '#4DE2F0',
  failure_analysis_agent:   '#FF7A45',
  recommendation_agent:     '#6FE38A',
}

/**
 * Visual multi-agent pipeline. Props: { trace: AgentTraceItem[] }
 */
export default function AgentFlow({ trace = [] }) {
  if (!trace.length) {
    return (
      <p className="text-sm text-ink-300 py-6 text-center">
        No agent trace yet — run a query in Query Console first.
      </p>
    )
  }

  return (
    <div className="flex flex-wrap items-stretch gap-2">
      {trace.map((t, i) => {
        const Icon = ICONS[t.agent] || ChevronRight
        const color = COLORS[t.agent] || '#7F8AA3'
        const okIcon = t.status === 'ok' ? CheckCircle2 : XCircle
        const StatusIcon = okIcon
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="flex items-center"
          >
            <div className="surface px-3 py-2 min-w-[180px]"
                 style={{ borderLeft: `4px solid ${color}` }}>
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" style={{ color }} />
                <span className="text-xs font-mono text-ink-700 flex-1 truncate">
                  {t.agent}
                </span>
                <StatusIcon className="w-3.5 h-3.5"
                            style={{ color: t.status === 'ok' ? '#2EB99B' : '#FF7A45' }} />
              </div>
              <div className="text-[10px] text-ink-300 mt-0.5">{t.duration_ms}ms</div>
              <div className="text-[11px] text-ink-500 mt-1 line-clamp-2">{t.summary}</div>
            </div>
            {i < trace.length - 1 && (
              <ChevronRight className="w-4 h-4 text-ink-300 mx-1 shrink-0" />
            )}
          </motion.div>
        )
      })}
    </div>
  )
}

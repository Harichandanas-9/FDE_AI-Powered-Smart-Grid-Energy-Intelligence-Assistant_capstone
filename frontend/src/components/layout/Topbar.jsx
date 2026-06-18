/**
 * Topbar — top navigation bar showing the app title, a live backend health pill,
 * an operator name input (persisted to localStorage), and a health refresh button.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { User, RefreshCw, Activity } from 'lucide-react'
import { Health } from '../../services/api.js'

/** Fetches /health on mount and whenever the user clicks Refresh. */
export default function Topbar() {
  const [operator, setOperator] = useState(localStorage.getItem('operator_name') || '')
  const [health, setHealth]     = useState({ status: 'ok' })  // optimistic default
  const [busy, setBusy]         = useState(false)

  const refresh = async () => {
    setBusy(true)
    try { setHealth(await Health()) } catch { setHealth({ status: 'error' }) }
    setBusy(false)
  }
  useEffect(() => { refresh() }, [])

  /** Persists the operator name both in React state and localStorage so requests include it. */
  const updateOperator = (v) => {
    setOperator(v)
    localStorage.setItem('operator_name', v)
  }

  const status = health?.status
  const pillStyle =
    status === 'ok'       ? 'bg-mint-100 text-mint-700'
    : status === 'warn'   ? 'bg-lavender-100 text-lavender-700'
    : 'bg-orange-300 text-ink-900'

  // Build a friendly tooltip listing per-component states
  const tooltip = health?.components
    ? Object.entries(health.components)
        .map(([k, v]) => `${k}: ${v}`).join('\n')
    : ''

  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-strong mx-3 mt-3 mb-2 px-5 py-3 flex items-center justify-between gap-4"
    >
      <div>
        <div className="text-xs uppercase tracking-wider text-ink-300">
          Operations Console
        </div>
        <div className="text-lg font-semibold text-ink-900">
          AI-Powered Smart Grid Energy Intelligence Assistant
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Health pill — hover to see per-component status */}
        <div className={'px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2 cursor-help ' + pillStyle}
             title={tooltip || 'Backend connectivity'}>
          <Activity className="w-3.5 h-3.5" />
          {health ? (status || '—') : 'checking…'}
        </div>

        {/* Operator input */}
        <div className="flex items-center gap-2 bg-white/70 border border-white/60 rounded-xl px-3 py-1.5">
          <User className="w-4 h-4 text-ink-500" />
          <input
            value={operator}
            onChange={(e) => updateOperator(e.target.value)}
            placeholder="Operator name"
            className="bg-transparent outline-none text-sm w-40 placeholder:text-ink-300"
          />
        </div>

        <button onClick={refresh} disabled={busy} className="btn-secondary !py-1.5" title="Refresh health">
          <RefreshCw className={'w-4 h-4 ' + (busy ? 'animate-spin' : '')} />
        </button>
      </div>
    </motion.header>
  )
}

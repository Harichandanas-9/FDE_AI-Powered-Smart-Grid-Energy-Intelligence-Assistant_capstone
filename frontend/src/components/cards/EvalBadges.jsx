/**
 * EvalBadges — lazy evaluation widget rendered below a bot response in the Query Console.
 * Shows a "Run evaluation" button until clicked; then fetches /evaluate and displays
 * Faithfulness, LLM-Judge, and Format scores as colour-coded chips.
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck, Sparkles, Gauge } from 'lucide-react'
import { Evaluate } from '../../services/api.js'

/**
 * EvalBadges — given an /analyze response, lazily fetches /evaluate and
 * renders three score chips (Faithfulness · LLM Judge · Format).
 */
export default function EvalBadges({ payload }) {
  const [data, setData]   = useState(null)
  const [busy, setBusy]   = useState(false)
  const [err,  setErr]    = useState(null)

  const run = async () => {
    if (busy || data) return
    setBusy(true); setErr(null)
    try { setData(await Evaluate(payload, payload?.query)) }
    catch (e) { setErr(e.friendly || 'Eval failed') }
    finally { setBusy(false) }
  }

  if (!payload || payload.status !== 'ok') return null

  if (!data) {
    return (
      <button onClick={run} disabled={busy}
              className="btn-secondary !py-1 !px-3 text-xs">
        <Sparkles className="w-3.5 h-3.5" />
        {busy ? 'Scoring…' : 'Run evaluation'}
      </button>
    )
  }

  const pct = (v) => Math.round((v || 0) * 100)
  const faith = pct(data.deepeval?.faithfulness)
  const judge = pct(data.llm_judge?.accuracy)
  const fmt   = pct(data.deepeval?.format_correctness)
  const overall = pct(data.summary?.overall)

  /* Map a 0–100 score to a CSS pill class: green ≥75, yellow ≥50, red <50. */
  const color = (v) => v >= 75 ? 'pill-low' : v >= 50 ? 'pill-medium' : 'pill-high'

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-ink-300 font-medium pr-1">eval:</span>
      <span className={color(faith)} title="Heuristic faithfulness (answer-evidence overlap)">
        <ShieldCheck className="w-3 h-3 mr-1" /> faith {faith}%
      </span>
      <span className={color(judge)} title="LLM-as-judge accuracy">
        <Sparkles className="w-3 h-3 mr-1" /> judge {judge}%
      </span>
      <span className={color(fmt)} title="Schema correctness">
        <Gauge className="w-3 h-3 mr-1" /> fmt {fmt}%
      </span>
      <span className="text-ink-700 font-semibold">overall {overall}%</span>
      <span className="text-ink-300 ml-1">(via {data.deepeval?.provider})</span>
    </motion.div>
  )
}

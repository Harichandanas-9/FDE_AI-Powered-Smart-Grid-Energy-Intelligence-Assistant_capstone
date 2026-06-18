/**
 * AgentVisualization — interactive page that lets operators run a query through the
 * 5-stage multi-agent pipeline and inspect each agent's execution trace, timing,
 * root causes, recommendations, and retrieved evidence chunks.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Loader2, Network, ShieldCheck, Search, Activity,
  AlertTriangle, Lightbulb, ChevronRight, CheckCircle2, XCircle,
  Clock, Database,
} from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import { Analyze } from '../services/api.js'

const AGENT_META = {
  guardrails:               { icon: ShieldCheck,  color: '#5EE6C8', label: 'Guardrails',      desc: 'PII block · Topic check' },
  retrieval_agent:          { icon: Search,        color: '#4DA8FF', label: 'Retrieval Agent', desc: 'Hybrid BM25 + Semantic' },
  stability_agent:          { icon: Activity,      color: '#4DE2F0', label: 'Stability Agent', desc: 'Telemetry correlation' },
  failure_analysis_agent:   { icon: AlertTriangle, color: '#FF7A45', label: 'Failure Agent',   desc: 'Root-cause detection' },
  recommendation_agent:     { icon: Lightbulb,     color: '#6FE38A', label: 'Recommendation', desc: 'LLM synthesis' },
}

/** Renders a proportional timing bar so agents' latencies are easy to compare visually. */
function TimingBar({ ms, maxMs }) {
  const pct = maxMs > 0 ? Math.min(100, (ms / maxMs) * 100) : 0
  return (
    <div className="w-full h-1 bg-white/30 rounded-full overflow-hidden mt-1.5">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="h-full rounded-full bg-current opacity-60"
      />
    </div>
  )
}

/**
 * AgentCard — one tile in the execution trace representing a single agent step.
 * Displays the agent label, pass/fail icon, timing bar, summary, and any
 * domain-specific metadata extracted from the result (e.g. chunk count).
 */
function AgentCard({ t, idx, maxMs, result }) {
  const meta = AGENT_META[t.agent] || { icon: ChevronRight, color: '#7F8AA3', label: t.agent, desc: '' }
  const Icon = meta.icon
  const isOk = t.status === 'ok'

  let extraData = null
  if (t.agent === 'retrieval_agent' && result?.retrieved)
    extraData = `${result.retrieved.length} incidents retrieved`
  else if (t.agent === 'stability_agent' && result?.stability_analysis?.grid_health_score != null)
    extraData = `Health: ${result.stability_analysis.grid_health_score}`
  else if (t.agent === 'failure_analysis_agent' && result?.root_causes)
    extraData = `${result.root_causes.length} root cause(s)`
  else if (t.agent === 'recommendation_agent' && result?.recommendations)
    extraData = `${result.recommendations.length} rec(s) · ${Math.round((result.confidence || 0) * 100)}% conf`
  else if (t.agent === 'guardrails')
    extraData = isOk ? 'Query accepted' : 'Query refused'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.12 }}
      className="flex flex-col items-center"
    >
      <div className="surface p-3 min-w-[155px] max-w-[185px]"
           style={{ borderTop: `3px solid ${meta.color}` }}>
        <div className="flex items-center gap-2 mb-1">
          <Icon className="w-4 h-4 shrink-0" style={{ color: meta.color }} />
          <span className="text-xs font-semibold text-ink-900 truncate flex-1">{meta.label}</span>
          {isOk
            ? <CheckCircle2 className="w-3.5 h-3.5 text-mint-700 shrink-0" />
            : <XCircle className="w-3.5 h-3.5 text-orange-700 shrink-0" />}
        </div>
        <div className="text-[10px] text-ink-300">{meta.desc}</div>
        <div className="flex items-center gap-1 mt-1.5 text-[10px] text-ink-400">
          <Clock className="w-2.5 h-2.5" />
          <span style={{ color: meta.color }}>{t.duration_ms?.toFixed(0)}ms</span>
        </div>
        <TimingBar ms={t.duration_ms || 0} maxMs={maxMs} />
        {t.summary && (
          <div className="text-[10px] text-ink-500 mt-1.5 line-clamp-2">{t.summary}</div>
        )}
        {extraData && (
          <div className="mt-1.5 text-[10px] font-semibold" style={{ color: meta.color }}>
            {extraData}
          </div>
        )}
      </div>
    </motion.div>
  )
}

const SAMPLE_QUERIES = [
  'Voltage instability in South Zone during evening peak — likely causes?',
  'Transformer overload recurring in North Zone — mitigation steps?',
  'Smart meter anomalies detected in residential area — investigation needed',
  'Frequency drift causing grid balancing issues — corrective action?',
]

export default function AgentVisualization() {
  const [query,  setQuery]  = useState(SAMPLE_QUERIES[0])
  const [busy,   setBusy]   = useState(false)
  const [result, setResult] = useState(null)
  const [err,    setErr]    = useState(null)

  const run = async () => {
    if (busy || !query.trim()) return
    setBusy(true); setErr(null); setResult(null)
    try { setResult(await Analyze({ query })) }
    catch (e) { setErr(e.friendly || 'Analysis failed — check the backend is running') }
    finally { setBusy(false) }
  }

  const trace   = result?.agent_trace || []
  const maxMs   = Math.max(...trace.map((t) => t.duration_ms || 0), 1)
  const totalMs = trace.reduce((a, t) => a + (t.duration_ms || 0), 0)

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Header */}
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Multi-Agent Pipeline</h2>
        <span className="text-xs text-ink-300">
          5-stage sequential orchestration · Guardrails → Retrieval → Stability → Failure → Recommendation
        </span>
      </div>

      {/* Architecture overview */}
      <GlassCard title="Pipeline Architecture" accent="#9D8BFF"
                 subtitle="Each agent contributes a deterministic layer. Only Recommendation calls an LLM.">
        <div className="flex flex-wrap items-center gap-1 text-center text-[10px]">
          {Object.entries(AGENT_META).map(([key, meta], i) => {
            const Icon = meta.icon
            return (
              <div key={key} className="flex items-center gap-1">
                <div className="surface px-3 py-2 flex flex-col items-center gap-1 min-w-[90px]">
                  <Icon className="w-4 h-4" style={{ color: meta.color }} />
                  <span className="font-medium text-ink-700">{meta.label}</span>
                  <span className="text-ink-300">{meta.desc}</span>
                </div>
                {i < 4 && <ChevronRight className="w-4 h-4 text-ink-300 shrink-0" />}
              </div>
            )
          })}
        </div>
      </GlassCard>

      {/* Query input */}
      <GlassCard title="Run a Query" accent="#9D8BFF">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {SAMPLE_QUERIES.map((q, i) => (
            <button key={i} onClick={() => setQuery(q)}
                    className={'surface px-3 py-1 text-xs cursor-pointer hover:shadow-card-hover transition ' +
                      (query === q ? 'ring-2 ring-lavender-500 shadow-card' : '')}>
              {q.length > 52 ? q.slice(0, 52) + '…' : q}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            className="flex-1 bg-white/80 border border-white/60 rounded-xl px-4 py-2.5 outline-none text-sm"
            placeholder="Ask about grid stability, voltage, outages, transformers…"
          />
          <button onClick={run} disabled={busy}
                  className="btn-primary" style={{ background: '#9D8BFF', color: 'white' }}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {busy ? 'Running…' : 'Run'}
          </button>
        </div>
      </GlassCard>

      {err && (
        <GlassCard accent="#FF7A45">
          <p className="text-sm text-orange-700 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {err}
          </p>
        </GlassCard>
      )}

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">

            {/* Execution trace */}
            <GlassCard
              title="Execution Trace"
              subtitle={`Total ${totalMs.toFixed(0)} ms · Provider: ${result.provider || 'template'} · Status: ${result.status}`}
              accent="#9D8BFF"
              right={
                <span className={'pill ' + (result.status === 'ok' ? 'pill-low' : 'pill-high')}>
                  {result.status}
                </span>
              }
            >
              <div className="flex flex-wrap items-center gap-1 overflow-x-auto pb-2">
                {trace.map((t, i) => (
                  <div key={i} className="flex items-center">
                    <AgentCard t={t} idx={i} maxMs={maxMs} result={result} />
                    {i < trace.length - 1 && (
                      <ChevronRight className="w-5 h-5 text-ink-300 mx-1 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Detailed outputs */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">

              <GlassCard title="Generated Answer" accent="#6FE38A">
                <p className="text-sm text-ink-900 whitespace-pre-line leading-relaxed">
                  {result.answer || '—'}
                </p>
                <div className="mt-2 text-xs text-ink-300">
                  Confidence: {Math.round((result.confidence || 0) * 100)}% · Provider: {result.provider}
                </div>
              </GlassCard>

              <GlassCard title="Stability Analysis" accent="#4DE2F0">
                <dl className="grid grid-cols-2 gap-1.5 text-xs">
                  {Object.entries(result.stability_analysis || {}).map(([k, v]) => (
                    <div key={k} className="surface px-2 py-1.5 flex justify-between gap-2">
                      <dt className="text-ink-400 font-mono truncate">{k.replace(/_/g, ' ')}</dt>
                      <dd className="text-ink-900 font-semibold text-right shrink-0">
                        {typeof v === 'object' ? JSON.stringify(v) : (v == null ? '—' : String(v))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </GlassCard>

              <GlassCard title="Root Causes"
                         subtitle={`${result.root_causes?.length || 0} identified by Failure Agent`}
                         accent="#FF7A45">
                {!result.root_causes?.length
                  ? <p className="text-sm text-ink-300">No causes derived from retrieved evidence.</p>
                  : (
                    <ul className="space-y-2">
                      {result.root_causes.map((rc, i) => (
                        <li key={i} className="surface p-2">
                          <div className="flex justify-between items-start gap-2">
                            <span className="text-sm text-ink-900 font-medium">{rc.cause}</span>
                            <span className="pill pill-high shrink-0">
                              p={Math.round((rc.probability || 0) * 100)}%
                            </span>
                          </div>
                          {rc.evidence?.length > 0 && (
                            <div className="text-[10px] text-ink-300 mt-1 font-mono">
                              Evidence: {rc.evidence.join(', ')}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
              </GlassCard>

              <GlassCard title="Recommendations"
                         subtitle={`${result.recommendations?.length || 0} prioritised actions`}
                         accent="#6FE38A">
                {!result.recommendations?.length
                  ? <p className="text-sm text-ink-300">No recommendations generated.</p>
                  : (
                    <ul className="space-y-2">
                      {result.recommendations.map((r, i) => (
                        <li key={i} className="surface p-2 flex items-start gap-2">
                          <span className={'pill shrink-0 pill-' + (r.priority || 'medium')}>
                            {r.priority}
                          </span>
                          <span className="text-sm text-ink-900">{r.action}</span>
                        </li>
                      ))}
                    </ul>
                  )}
              </GlassCard>
            </div>

            {/* Retrieved evidence */}
            <GlassCard
              title="Retrieved Evidence"
              subtitle={`${result.retrieved?.length || 0} chunks · Hybrid BM25 + Semantic + RRF fusion`}
              accent="#4DA8FF"
            >
              {!result.retrieved?.length
                ? <p className="text-sm text-ink-300">No chunks retrieved — run ETL first to populate ChromaDB.</p>
                : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {result.retrieved.slice(0, 6).map((c, i) => (
                      <div key={i} className="surface p-2 text-xs">
                        <div className="flex items-center gap-2 mb-1">
                          <Database className="w-3 h-3 text-blue-500 shrink-0" />
                          <span className="font-mono text-ink-300 truncate flex-1">{c.id}</span>
                          <span className="text-ink-400 shrink-0">RRF {c.score?.toFixed(4)}</span>
                        </div>
                        <p className="text-ink-700 line-clamp-3 leading-relaxed">{c.text}</p>
                        <div className="mt-1 text-ink-300 flex gap-2 items-center">
                          <span className={'pill pill-' + (c.metadata?.severity || 'low')}>
                            {c.metadata?.severity}
                          </span>
                          <span>{c.metadata?.region}</span>
                          <span className="ml-auto font-mono">{c.metadata?.source_dataset}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
            </GlassCard>

          </motion.div>
        )}
      </AnimatePresence>

      {!result && !err && (
        <GlassCard accent="#9D8BFF">
          <div className="text-center py-10">
            <Network className="w-10 h-10 text-ink-300 mx-auto mb-3" />
            <p className="text-sm text-ink-500 font-medium">
              Hit <b>Run</b> to execute the 5-stage agent pipeline.
            </p>
            <p className="text-xs text-ink-300 mt-1">
              Each agent contributes a deterministic layer — only the Recommendation Agent calls an LLM.
            </p>
          </div>
        </GlassCard>
      )}
    </div>
  )
}

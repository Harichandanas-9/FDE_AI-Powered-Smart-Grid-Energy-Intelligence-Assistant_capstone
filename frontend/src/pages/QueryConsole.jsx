import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Loader2, Bot, User as UserIcon, AlertTriangle, ShieldAlert,
  History, RefreshCw,
} from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import EvalBadges from '../components/cards/EvalBadges.jsx'
import { Analyze, QaHistory } from '../services/api.js'

// Persist chat across tab navigation
const CHAT_KEY = 'qc_history'
const QUERY_KEY = 'qc_query_draft'

export default function QueryConsole() {
  const [query, setQuery] = useState(
    () => sessionStorage.getItem(QUERY_KEY) ||
          'Voltage instability is increasing in South Zone during evening peak demand. What are the likely causes?'
  )
  const [busy,  setBusy]  = useState(false)
  const [history, setHistory] = useState(() => {
    try {
      const raw = sessionStorage.getItem(CHAT_KEY)
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })

  // Past questions from the persistent history file on the backend
  const [past, setPast]     = useState(null)
  const [pastBusy, setPB]   = useState(false)

  const loadPast = async () => {
    setPB(true)
    try { setPast(await QaHistory(15, true)) }
    catch { setPast({ questions: [], total_questions: 0 }) }
    finally { setPB(false) }
  }
  useEffect(() => { loadPast() }, [])
  useEffect(() => { sessionStorage.setItem(QUERY_KEY, query) }, [query])
  useEffect(() => { sessionStorage.setItem(CHAT_KEY, JSON.stringify(history.slice(-20))) }, [history])

  const send = async (e) => {
    e?.preventDefault?.()
    const q = query.trim()
    if (!q || busy) return
    setBusy(true)
    const userMsg = { role: 'user', query: q, ts: Date.now() }
    setHistory((h) => [...h, userMsg])
    setQuery('')
    try {
      const r = await Analyze({ query: q })
      setHistory((h) => [...h, { role: 'bot', payload: r, ts: Date.now() }])
      // refresh FAQ panel so the new question shows up
      loadPast()
    } catch (err) {
      setHistory((h) => [...h, {
        role: 'bot', payload: { status: 'error', answer: err.friendly || 'Request failed' },
      }])
    } finally { setBusy(false) }
  }

  const useQuestion = (q) => {
    setQuery(q)
    // small UX touch — scroll the input into view
    setTimeout(() => {
      document.querySelector('input[placeholder*="South Zone"]')?.focus()
    }, 50)
  }

  const clearChat = () => {
    setHistory([])
    sessionStorage.removeItem(CHAT_KEY)
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-3 animate-fade-up">
      {/* Chat column */}
      <div className="xl:col-span-2 space-y-3 min-h-0">
        {/* Recent / common questions strip */}
        <GlassCard
          accent="#FFD166"
          title="Common questions from past operators"
          subtitle={past ? `${past.total_questions} total · ${past.unique_operators ?? 0} operator(s) · persisted across restarts` : 'loading…'}
          right={
            <button onClick={loadPast} className="btn-secondary !py-1 !px-2 text-xs">
              <RefreshCw className={'w-3.5 h-3.5 ' + (pastBusy ? 'animate-spin' : '')} />
            </button>
          }
        >
          {!past?.questions?.length ? (
            <p className="text-xs text-ink-300">
              No questions in history yet. The first questions asked here will appear for everyone.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
              {past.questions.map((q, i) => (
                <button key={i} onClick={() => useQuestion(q.query)}
                        className="surface px-3 py-1.5 text-xs text-left hover:shadow-card-hover transition
                                   flex items-center gap-2 max-w-md"
                        title={`${q.operator || 'anonymous'} · ${q.ts || ''}`}>
                  <History className="w-3 h-3 text-mint-700 shrink-0" />
                  <span className="line-clamp-1">{q.query}</span>
                </button>
              ))}
            </div>
          )}
        </GlassCard>

        <GlassCard title="Query Console"
                   subtitle="Ask the smart-grid assistant" accent="#5EE6C8"
                   right={
                     history.length > 0 && (
                       <button onClick={clearChat} className="btn-secondary !py-1 !px-2 text-xs">
                         Clear chat
                       </button>
                     )
                   }>

          <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
            {history.length === 0 && (
              <p className="text-sm text-ink-300">
                Start by asking a question about grid stability, outages, or smart-meter anomalies.
              </p>
            )}
            <AnimatePresence initial={false}>
              {history.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-2"
                >
                  {m.role === 'user' ? (
                    <>
                      <div className="w-7 h-7 rounded-full bg-mint-500/30 text-mint-700 flex items-center justify-center shrink-0">
                        <UserIcon className="w-4 h-4" />
                      </div>
                      <div className="surface px-3 py-2 text-sm">{m.query}</div>
                    </>
                  ) : (
                    <>
                      <div className="w-7 h-7 rounded-full bg-lavender-500/30 text-lavender-700 flex items-center justify-center shrink-0">
                        <Bot className="w-4 h-4" />
                      </div>
                      <BotBubble p={m.payload} />
                    </>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          <form onSubmit={send} className="mt-3 flex gap-2">
            <input
              value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder='e.g. "Voltage drop in South Zone evening peak"'
              className="flex-1 bg-white/80 border border-white/60 rounded-xl px-4 py-2.5 outline-none"
            />
            <button className="btn-primary" disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send
            </button>
          </form>
        </GlassCard>
      </div>

      {/* Side column — last response details */}
      <div className="space-y-3">
        <SidePanel last={history.slice().reverse().find((m) => m.role === 'bot')?.payload} />
      </div>
    </div>
  )
}

function BotBubble({ p }) {
  if (!p) return null
  if (p.status === 'refused') {
    return (
      <div className="surface px-3 py-2 text-sm">
        <div className="flex items-center gap-2 text-orange-700 font-medium">
          <ShieldAlert className="w-4 h-4" /> Refused
        </div>
        <p className="mt-1 text-ink-700">{p.answer}</p>
      </div>
    )
  }
  if (p.status === 'error') {
    return (
      <div className="surface px-3 py-2 text-sm">
        <div className="flex items-center gap-2 text-orange-700 font-medium">
          <AlertTriangle className="w-4 h-4" /> Error
        </div>
        <p className="mt-1 text-ink-700">{p.answer}</p>
      </div>
    )
  }
  return (
    <div className="surface px-3 py-2 text-sm w-full">
      <div className="flex items-center gap-2 mb-1">
        <div className="text-xs text-ink-300">
          provider: {p.provider} · confidence {Math.round((p.confidence || 0) * 100)}%
        </div>
      </div>
      <p className="text-ink-900 whitespace-pre-line">{p.answer}</p>
      {p.recommendations?.length > 0 && (
        <ul className="mt-2 space-y-1">
          {p.recommendations.map((r, i) => (
            <li key={i} className="text-xs">
              <span className={'pill mr-1 pill-' + (r.priority || 'medium')}>{r.priority}</span>
              {r.action}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 pt-2 border-t border-white/40">
        <EvalBadges payload={p} />
      </div>
    </div>
  )
}

function SidePanel({ last }) {
  if (!last) {
    return (
      <GlassCard title="Inspector" subtitle="Last response detail" accent="#B79CFF">
        <p className="text-sm text-ink-300">No analysis yet.</p>
      </GlassCard>
    )
  }
  return (
    <>
      <GlassCard title="Agent trace" accent="#9D8BFF">
        {(last.agent_trace || []).length === 0 ? (
          <p className="text-sm text-ink-300">No trace recorded.</p>
        ) : (
          <ol className="space-y-1.5 text-xs">
            {last.agent_trace.map((t, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className={
                  'w-1.5 h-1.5 rounded-full ' +
                  (t.status === 'ok' ? 'bg-mint-500'
                   : t.status === 'refused' ? 'bg-orange-500' : 'bg-orange-700')
                } />
                <span className="font-mono text-ink-700 w-44 truncate">{t.agent}</span>
                <span className="font-mono text-ink-300 w-14 text-right">{t.duration_ms}ms</span>
                <span className="text-ink-500 truncate">{t.summary}</span>
              </li>
            ))}
          </ol>
        )}
      </GlassCard>

      <GlassCard title="Root causes" accent="#FF7A45">
        {(last.root_causes || []).length === 0 ? (
          <p className="text-sm text-ink-300">No causes derived.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {last.root_causes.map((rc, i) => (
              <li key={i} className="surface p-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-ink-900 font-medium">{rc.cause}</span>
                  <span className="text-xs text-ink-300">p={rc.probability}</span>
                </div>
                {rc.evidence?.length > 0 && (
                  <div className="text-xs text-ink-300 mt-1 font-mono truncate">
                    {rc.evidence.join(', ')}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </GlassCard>

      <GlassCard title="Retrieved evidence" subtitle={`${last.retrieved?.length || 0} chunks`} accent="#4DA8FF">
        {(last.retrieved || []).slice(0, 4).map((c, i) => (
          <div key={i} className="surface p-2 mb-2 text-xs">
            <div className="text-ink-300 mb-1 font-mono">{c.id} · score {c.score?.toFixed?.(3)}</div>
            <div className="text-ink-700 line-clamp-3">{c.text}</div>
          </div>
        ))}
      </GlassCard>
    </>
  )
}

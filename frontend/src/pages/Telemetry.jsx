import { useState } from 'react'
import { Pause, Play, Radio, Wifi, WifiOff } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import TelemetryLineChart from '../components/charts/TelemetryLineChart.jsx'
import { useApi } from '../hooks/useApi.js'
import { useWebSocket } from '../hooks/useWebSocket.js'
import { Telemetry as TelemetryAPI } from '../services/api.js'

export default function Telemetry() {
  const [mode, setMode]   = useState('poll')     // 'poll' | 'live'
  const [limit, setLimit] = useState(150)

  // --- Polling mode ---
  const poll = useApi(() => TelemetryAPI(limit), [limit],
                      mode === 'poll' ? { pollMs: 5000 } : {})

  // --- WebSocket live mode ---
  const ws = useWebSocket('/api/v1/ws/telemetry', {
    enabled: mode === 'live',
    maxMessages: 200,
    query: { mode: 'auto', rate: 2.0 },
  })

  const samples = mode === 'live' ? ws.messages : (poll.data?.samples || [])
  const loading = mode === 'poll' && poll.loading && !samples.length

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex flex-wrap items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Telemetry</h2>
        <span className="text-xs text-ink-300">
          {samples.length} sample(s) ·{' '}
          {mode === 'live'
            ? <span className="inline-flex items-center gap-1">
                {ws.status === 'open'
                  ? <Wifi className="w-3 h-3 text-mint-700" />
                  : <WifiOff className="w-3 h-3 text-orange-700" />}
                WS {ws.status}
              </span>
            : `polling ${5000}ms`}
        </span>

        <div className="ml-auto flex gap-2 items-center">
          <div className="bg-white/80 border border-white/60 rounded-xl p-1 flex">
            <button onClick={() => setMode('poll')}
                    className={'px-3 py-1.5 rounded-lg text-sm ' +
                      (mode === 'poll' ? 'bg-mint-500 text-ink-900 font-medium' : 'text-ink-500')}>
              <Play className="w-3.5 h-3.5 inline mr-1" />Poll
            </button>
            <button onClick={() => setMode('live')}
                    className={'px-3 py-1.5 rounded-lg text-sm ' +
                      (mode === 'live' ? 'bg-lavender-500 text-white font-medium' : 'text-ink-500')}>
              <Radio className="w-3.5 h-3.5 inline mr-1" />Live (WS)
            </button>
          </div>

          {mode === 'poll' && (
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}
                    className="bg-white/80 border border-white/60 rounded-xl px-3 py-2 text-sm outline-none">
              <option value={50}>50</option>
              <option value={150}>150</option>
              <option value={500}>500</option>
            </select>
          )}
          {mode === 'live' && (
            <button onClick={ws.clear} className="btn-secondary !py-1.5">
              <Pause className="w-4 h-4" /> Clear
            </button>
          )}
        </div>
      </div>

      {loading ? <LoadingDots /> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <GlassCard title="Voltage & frequency" accent="#4DE2F0">
            <TelemetryLineChart samples={samples} series={['voltage', 'frequency']} />
          </GlassCard>
          <GlassCard title="Demand & stability" accent="#4DE2F0">
            <TelemetryLineChart samples={samples} series={['demand', 'stability']} />
          </GlassCard>
        </div>
      )}
    </div>
  )
}

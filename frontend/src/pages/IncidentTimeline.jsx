/**
 * IncidentTimeline page — stacked area chart of incidents over time grouped by severity.
 * Operators can toggle between 'day' and 'hour' time bucket granularity.
 */
import { useState } from 'react'
import GlassCard from '../components/cards/GlassCard.jsx'
import LoadingDots from '../components/cards/LoadingDots.jsx'
import TimelineArea from '../components/charts/TimelineArea.jsx'
import { useApi } from '../hooks/useApi.js'
import { Timeline } from '../services/api.js'

export default function IncidentTimeline() {
  const [bucket, setBucket] = useState('day')
  const { data, loading } = useApi(() => Timeline(bucket), [bucket])

  return (
    <div className="space-y-3 animate-fade-up">
      <div className="flex items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">Incident Timeline</h2>
        <span className="text-xs text-ink-300">
          {data?.n_incidents ?? 0} incidents across {data?.buckets?.length ?? 0} {bucket}s
        </span>
        <div className="ml-auto flex gap-1">
          {['day', 'hour'].map((b) => (
            <button key={b} onClick={() => setBucket(b)}
                    className={'px-3 py-1.5 rounded-xl text-sm font-medium ' +
                      (bucket === b ? 'bg-mint-500 text-ink-900' : 'bg-white/70 text-ink-500')}>
              {b}
            </button>
          ))}
        </div>
      </div>

      <GlassCard title="Severity over time" accent="#FFD166">
        {loading ? <LoadingDots /> :
          <TimelineArea buckets={data?.buckets || []} series={data?.series || {}} height={360} />}
      </GlassCard>
    </div>
  )
}

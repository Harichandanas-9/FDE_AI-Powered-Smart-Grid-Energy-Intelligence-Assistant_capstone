/**
 * LoadingDots — three-dot animated loading indicator used as a placeholder
 * while async data is being fetched. Accepts an optional `label` string.
 */
export default function LoadingDots({ label = 'Loading' }) {
  return (
    <div className="flex items-center gap-2 text-ink-300 text-sm py-6 justify-center">
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-mint-500 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-lavender-500 animate-bounce" style={{ animationDelay: '120ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '240ms' }} />
      </div>
      <span>{label}…</span>
    </div>
  )
}

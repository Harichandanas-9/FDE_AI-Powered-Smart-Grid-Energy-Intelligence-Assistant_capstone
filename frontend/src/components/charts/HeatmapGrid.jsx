/**
 * HeatmapGrid — interactive region × severity matrix.
 * Each cell is coloured by its severity hue and shaded by count intensity relative to
 * the maximum count in the matrix. Clicking a non-empty cell calls onSelect({ region, severity, count }).
 */
const COLORS = {
  low:      '#A7F1DE',
  medium:   '#D5C5FF',
  high:     '#FFA552',
  critical: '#FF7A45',
}

export default function HeatmapGrid({
  regions = [], severities = ['low', 'medium', 'high', 'critical'],
  matrix = [], onSelect,
}) {
  if (!regions.length) {
    return (
      <div className="py-8 text-center">
        <div className="text-2xl mb-2">🗺️</div>
        <p className="text-sm font-medium text-ink-500">No regional data yet</p>
        <p className="text-xs text-ink-300 mt-1">Go to ETL tab → click Run ETL to populate the heatmap</p>
      </div>
    )
  }
  /* Normalise cell opacity against the highest count so low-count cells remain visible. */
  const maxV = matrix.flat().reduce((m, x) => Math.max(m, x), 0) || 1

  return (
    <div className="overflow-x-auto">
      <table className="text-xs w-full">
        <thead>
          <tr className="text-ink-300">
            <th className="text-left font-medium pr-3 pb-2 sticky left-0 bg-white/40">Region</th>
            {severities.map((s) => (
              <th key={s} className="text-center font-medium pb-2 px-1.5 capitalize">{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {regions.map((r, ri) => (
            <tr key={r} className="border-t border-white/40">
              <td className="py-1.5 pr-3 text-ink-700 sticky left-0 bg-white/40">{r}</td>
              {severities.map((s, si) => {
                const v = matrix[ri]?.[si] || 0
                const opacity = v ? Math.min(1, 0.25 + (v / maxV) * 0.75) : 0.15
                return (
                  <td key={s} className="text-center py-1.5 px-1">
                    <button
                      onClick={() => onSelect?.({ region: r, severity: s, count: v })}
                      disabled={!v}
                      className="inline-flex items-center justify-center min-w-[40px] h-8
                                 rounded-lg text-ink-900 font-semibold transition-transform
                                 hover:scale-110 disabled:cursor-default"
                      style={{ background: COLORS[s], opacity }}
                    >{v || '·'}</button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface MetricTileProps {
  label: string
  value: string
  state?: string
  note?: string
}

export default function MetricTile({ label, value, state, note }: MetricTileProps) {
  return (
    <div className="metric-tile" data-reveal>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      {state ? <p className="metric-state">{state}</p> : null}
      {note ? <p className="metric-note">{note}</p> : null}
    </div>
  )
}

import { vnd } from './MockPrimitives'

interface BarPoint { label: string; value: number }

/** Dependency-free SVG bar chart. Values are exposed in a table-like <title> per bar for screen readers. */
export function BarChart({ data, height = 160, format = vnd, label }: { data: BarPoint[]; height?: number; format?: (value: number) => string; label: string }) {
  const max = Math.max(1, ...data.map((point) => point.value))
  const width = 100 / Math.max(1, data.length)
  return (
    <figure>
      <svg role="img" aria-label={label} viewBox={`0 0 100 ${height / 4}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
        {data.map((point, index) => {
          const barHeight = (point.value / max) * (height / 4 - 2)
          return (
            <rect key={point.label} x={index * width + width * 0.15} y={height / 4 - barHeight} width={width * 0.7} height={barHeight} rx={0.6} className="fill-primary-600">
              <title>{`${point.label}: ${format(point.value)}`}</title>
            </rect>
          )
        })}
      </svg>
      <figcaption className="mt-1 flex justify-between text-[11px] text-muted" aria-hidden="true">
        {data.length > 0 && <><span>{data[0].label}</span><span>{data[data.length - 1].label}</span></>}
      </figcaption>
    </figure>
  )
}

export function FunnelBars({ steps }: { steps: { step: string; value: number }[] }) {
  const top = Math.max(1, steps[0]?.value ?? 1)
  return (
    <ol className="space-y-3">
      {steps.map((step) => (
        <li key={step.step}>
          <div className="flex justify-between text-sm"><span>{step.step}</span><strong className="tabular-nums">{new Intl.NumberFormat('vi-VN').format(step.value)}</strong></div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-primary-600" style={{ width: `${Math.max(2, (step.value / top) * 100)}%` }} /></div>
        </li>
      ))}
    </ol>
  )
}

export function ShareBars({ items }: { items: { name: string; share: number; gmv: number }[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.name}>
          <div className="flex justify-between text-sm"><span>{item.name}</span><span className="tabular-nums text-muted">{item.share}% · {vnd(item.gmv)}</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-primary-500" style={{ width: `${item.share}%` }} /></div>
        </li>
      ))}
    </ul>
  )
}

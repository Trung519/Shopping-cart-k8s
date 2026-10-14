import { Check, Truck } from 'lucide-react'
import { useShipment } from '@/hooks/useMock'
import { cn } from '@/utils/cn'
import { DemoBadge, shortDate } from './MockPrimitives'

/** Order tracking driven by the BFF mock clock; it advances on its own while the page is open. */
export default function ShipmentTimeline({ orderId }: { orderId: string }) {
  const { data, isLoading, isError } = useShipment(orderId)
  if (isLoading) return <div className="h-40 animate-pulse rounded-card bg-slate-100" aria-hidden="true" />
  if (isError || !data) return null

  const blocked = data.status === 'WAITING_PAYMENT' || data.status === 'PAYMENT_FAILED'
  return (
    <section className="surface-card p-5" aria-label="Theo dõi vận chuyển">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold"><Truck className="h-5 w-5 text-primary-600" aria-hidden="true" /> Theo dõi vận chuyển <DemoBadge /></h2>
        <p className="text-sm text-muted">{data.carrier} · <span className="font-mono">{data.trackingCode}</span></p>
      </div>
      {data.status === 'WAITING_PAYMENT' && <p className="mt-3 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning">Đang chờ thanh toán. Đơn sẽ được xử lý ngay khi thanh toán thành công.</p>}
      {data.status === 'PAYMENT_FAILED' && <p className="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">Thanh toán chưa thành công nên đơn chưa được xử lý.</p>}
      <ol className="mt-5 space-y-0">
        {data.steps.map((step, index) => {
          const current = !blocked && index === data.currentStep && data.status !== 'DELIVERED'
          return (
            <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0" aria-current={current ? 'step' : undefined}>
              {index < data.steps.length - 1 && <span className={cn('absolute left-[13px] top-7 h-[calc(100%-1.75rem)] w-0.5', step.done && data.steps[index + 1].done ? 'bg-primary-600' : 'bg-line')} aria-hidden="true" />}
              <span className={cn('z-10 flex h-7 w-7 flex-none items-center justify-center rounded-full border-2 text-xs font-bold', step.done ? 'border-primary-600 bg-primary-600 text-white' : current ? 'border-primary-600 bg-white text-primary-600' : 'border-line bg-white text-muted')}>
                {step.done ? <Check className="h-4 w-4" aria-hidden="true" /> : index + 1}
              </span>
              <div className="min-w-0">
                <p className={cn('text-sm font-semibold', !step.done && !current && 'text-muted')}>{step.label}</p>
                {step.at && <p className="text-xs text-muted">{shortDate(step.at)}</p>}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

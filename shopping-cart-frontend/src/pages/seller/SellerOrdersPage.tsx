import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, StatusBadge, shortDate, vnd } from '@/components/mock/MockPrimitives'
import { useSellerOrderAction, useSellerOrders } from '@/hooks/useMock'
import type { SellerOrder, SellerOrderStatus } from '@/types/mock'
import { cn } from '@/utils/cn'

const tabs: { value: SellerOrderStatus | ''; label: string }[] = [
  { value: '', label: 'Tất cả' }, { value: 'NEW', label: 'Mới' }, { value: 'CONFIRMED', label: 'Đã xác nhận' },
  { value: 'PACKED', label: 'Đã đóng gói' }, { value: 'SHIPPED', label: 'Đang giao' }, { value: 'DELIVERED', label: 'Đã giao' }, { value: 'CANCELLED', label: 'Đã huỷ' },
]

const next: Partial<Record<SellerOrderStatus, { action: 'confirm' | 'pack' | 'ship'; label: string }>> = {
  NEW: { action: 'confirm', label: 'Xác nhận' },
  CONFIRMED: { action: 'pack', label: 'Đóng gói' },
  PACKED: { action: 'ship', label: 'Giao cho vận chuyển' },
}

export default function SellerOrdersPage() {
  const [status, setStatus] = useState<SellerOrderStatus | ''>('')
  const orders = useSellerOrders(status || undefined)
  const act = useSellerOrderAction()
  const counts = orders.data?.counts

  return (
    <MockPage title="Đơn bán" description="Xác nhận, đóng gói và giao đơn cho người mua.">
      <div role="tablist" aria-label="Lọc theo trạng thái" className="flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((tab) => (
          <button key={tab.value} type="button" role="tab" aria-selected={status === tab.value} onClick={() => setStatus(tab.value)} className={cn('focus-ring min-h-11 whitespace-nowrap border-b-2 px-4 text-sm font-semibold', status === tab.value ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink')}>
            {tab.label}{tab.value && counts ? ` (${counts[tab.value] ?? 0})` : ''}
          </button>
        ))}
      </div>
      <div className="mt-5">
        {act.error && <div className="mb-3"><ErrorLine error={act.error} /></div>}
        {orders.isLoading ? <SkeletonRows /> : orders.isError ? <ErrorLine error={orders.error} /> : orders.data?.items.length === 0 ? <EmptyLine>Không có đơn nào ở trạng thái này.</EmptyLine> : (
          <ul className="space-y-3">{orders.data?.items.map((order) => <OrderRow key={order.id} order={order} pending={act.isPending && act.variables?.id === order.id} onAct={(action) => act.mutate({ id: order.id, action })} />)}</ul>
        )}
      </div>
    </MockPage>
  )
}

function OrderRow({ order, pending, onAct }: { order: SellerOrder; pending: boolean; onAct: (action: 'confirm' | 'pack' | 'ship' | 'cancel') => void }) {
  const step = next[order.status]
  return (
    <li className="surface-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">{order.id} <span className="font-normal text-muted">· {order.buyer} · {order.city}</span></p>
        <div className="flex items-center gap-3"><time dateTime={order.createdAt} className="text-xs text-muted">{shortDate(order.createdAt)}</time><StatusBadge status={order.status} /></div>
      </div>
      <ul className="mt-3 space-y-1 text-sm text-muted">{order.items.map((item) => <li key={item.name}>{item.qty} × {item.name} · {vnd(item.price)}</li>)}</ul>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <p className="font-bold tabular-nums text-price">{vnd(order.total)}</p>
        <div className="flex gap-2">
          {step && <Button type="button" size="sm" loading={pending} onClick={() => onAct(step.action)}>{step.label}</Button>}
          {(order.status === 'NEW' || order.status === 'CONFIRMED') && <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => onAct('cancel')}>Huỷ đơn</Button>}
        </div>
      </div>
    </li>
  )
}

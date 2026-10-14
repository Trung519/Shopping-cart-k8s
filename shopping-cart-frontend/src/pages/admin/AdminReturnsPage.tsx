import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, StatusBadge, shortDate, vnd } from '@/components/mock/MockPrimitives'
import { useAdminReturnAction, useAdminReturns } from '@/hooks/useMock'
import type { ReturnReason, ReturnStatus } from '@/types/mock'
import { cn } from '@/utils/cn'

const reasonLabel: Record<ReturnReason, string> = {
  DEFECTIVE: 'Sản phẩm lỗi', NOT_AS_DESCRIBED: 'Không đúng mô tả', WRONG_ITEM: 'Giao sai hàng', CHANGED_MIND: 'Đổi ý',
}

const tabs: { value: ReturnStatus | ''; label: string }[] = [
  { value: '', label: 'Tất cả' }, { value: 'REQUESTED', label: 'Chờ duyệt' }, { value: 'APPROVED', label: 'Đã duyệt' }, { value: 'REFUNDED', label: 'Đã hoàn tiền' }, { value: 'REJECTED', label: 'Từ chối' },
]

export default function AdminReturnsPage() {
  const [status, setStatus] = useState<ReturnStatus | ''>('')
  const returns = useAdminReturns(status || undefined)
  const act = useAdminReturnAction()
  const counts = returns.data?.counts

  return (
    <MockPage title="Đổi trả & tranh chấp" description="Duyệt yêu cầu đổi trả của người mua và hoàn tiền.">
      <div role="tablist" aria-label="Lọc theo trạng thái" className="flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((tab) => (
          <button key={tab.value} type="button" role="tab" aria-selected={status === tab.value} onClick={() => setStatus(tab.value)} className={cn('focus-ring min-h-11 whitespace-nowrap border-b-2 px-4 text-sm font-semibold', status === tab.value ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink')}>
            {tab.label}{tab.value && counts ? ` (${counts[tab.value] ?? 0})` : ''}
          </button>
        ))}
      </div>
      <div className="mt-5">
        {act.error && <div className="mb-3"><ErrorLine error={act.error} /></div>}
        {returns.isLoading ? <SkeletonRows /> : returns.isError ? <ErrorLine error={returns.error} /> : returns.data?.items.length === 0 ? <EmptyLine>Không có yêu cầu nào.</EmptyLine> : (
          <ul className="space-y-3">
            {returns.data?.items.map((item) => {
              const busy = act.isPending && act.variables?.id === item.id
              return (
                <li key={item.id} className="surface-card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">{item.orderRef} <span className="font-normal text-muted">· {item.buyer} → {item.shop}</span></p>
                    <div className="flex items-center gap-3"><time dateTime={item.createdAt} className="text-xs text-muted">{shortDate(item.createdAt)}</time><StatusBadge status={item.status} /></div>
                  </div>
                  <p className="mt-2 text-sm"><strong>{reasonLabel[item.reason] ?? item.reason}</strong>{item.note && <span className="text-muted"> — {item.note}</span>}</p>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
                    <p className="font-bold tabular-nums">{item.amount > 0 ? vnd(item.amount) : 'Chưa xác định số tiền'}</p>
                    <div className="flex gap-2">
                      {item.status === 'REQUESTED' && <><Button type="button" size="sm" loading={busy} onClick={() => act.mutate({ id: item.id, action: 'approve' })}>Duyệt</Button><Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => act.mutate({ id: item.id, action: 'reject' })}>Từ chối</Button></>}
                      {item.status === 'APPROVED' && <Button type="button" size="sm" loading={busy} onClick={() => act.mutate({ id: item.id, action: 'refund' })}>Hoàn tiền</Button>}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </MockPage>
  )
}

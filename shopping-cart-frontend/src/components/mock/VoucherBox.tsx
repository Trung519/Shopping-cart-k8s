import { useEffect, useState, type FormEvent } from 'react'
import { BadgePercent, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useApplyVoucher, useMockEnabled, useVouchers } from '@/hooks/useMock'
import { useVoucherStore } from '@/stores/voucherStore'
import { DemoBadge } from './MockPrimitives'
import { vnd } from './MockPrimitives'

/** Voucher entry for cart and checkout. Hidden entirely when the mock API is off. */
export default function VoucherBox({ subtotal }: { subtotal: number }) {
  const { enabled } = useMockEnabled()
  const applied = useVoucherStore((state) => state.applied)
  const apply = useVoucherStore((state) => state.apply)
  const clear = useVoucherStore((state) => state.clear)
  const vouchers = useVouchers(subtotal)
  const mutation = useApplyVoucher()
  const [code, setCode] = useState('')

  // A voucher chosen earlier may stop qualifying when the cart changes; re-check and drop it if so.
  const appliedCode = applied?.code
  useEffect(() => {
    if (!enabled || !appliedCode) return
    mutation.mutate({ code: appliedCode, subtotal }, { onSuccess: apply, onError: clear })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, appliedCode, subtotal])

  if (!enabled) return null

  const submit = (event: FormEvent, override?: string) => {
    event.preventDefault()
    const value = (override ?? code).trim()
    if (!value) return
    mutation.mutate({ code: value, subtotal }, { onSuccess: (voucher) => { apply(voucher); setCode('') } })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold"><BadgePercent className="h-4 w-4 text-primary-600" aria-hidden="true" /> Mã giảm giá <DemoBadge /></div>
      {applied ? (
        <div className="flex items-center justify-between gap-2 rounded-md bg-primary-50 px-3 py-2 text-sm">
          <span><strong>{applied.code}</strong> · {applied.title}</span>
          <button type="button" aria-label="Bỏ mã giảm giá" onClick={clear} className="focus-ring flex h-8 w-8 items-center justify-center rounded-md hover:bg-white"><X className="h-4 w-4" /></button>
        </div>
      ) : (
        <form onSubmit={submit} className="flex gap-2">
          <label htmlFor="voucher-code" className="sr-only">Mã giảm giá</label>
          <input id="voucher-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Nhập mã, ví dụ SALE50" className="focus-ring h-11 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm" />
          <Button type="submit" variant="outline" loading={mutation.isPending}>Áp dụng</Button>
        </form>
      )}
      {mutation.isError && !applied && <p role="alert" className="text-sm text-danger">{mutation.error.message}</p>}
      {!applied && vouchers.data && (
        <ul className="flex flex-wrap gap-2" aria-label="Mã gợi ý">
          {vouchers.data.filter((v) => v.eligible).map((v) => (
            <li key={v.code}><button type="button" onClick={(e) => submit(e as unknown as FormEvent, v.code)} className="focus-ring rounded-full border border-dashed border-primary-300 bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-800 hover:bg-primary-100" title={v.description}>{v.code}</button></li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">Voucher giả lập: chỉ minh hoạ giao diện{applied && applied.discount + applied.shippingDiscount > 0 ? ` (giảm ${vnd(applied.discount + applied.shippingDiscount)})` : ''}, tổng tiền của đơn thật không thay đổi.</p>
    </div>
  )
}

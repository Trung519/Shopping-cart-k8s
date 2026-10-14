import { useEffect, useRef } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { useCancelMockPayment, useMockPayment } from '@/hooks/useMock'
import type { MockPayment } from '@/types/mock'
import { DemoBadge, vnd } from './MockPrimitives'

const methodName: Record<string, string> = { momo: 'MoMo', vnpay: 'VNPay', zalopay: 'ZaloPay', cod: 'COD' }

/** Draws the decorative matrix the BFF returns. It does not encode anything scannable. */
export function QrCode({ matrix, label }: { matrix: string[]; label: string }) {
  const size = matrix.length
  return (
    <svg role="img" aria-label={label} viewBox={`-2 -2 ${size + 4} ${size + 4}`} className="h-48 w-48 rounded-md border border-line bg-white" shapeRendering="crispEdges">
      {matrix.flatMap((row, y) => row.split('').map((cell, x) => (cell === '1' ? <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} className="fill-ink" /> : null)))}
    </svg>
  )
}

interface Props {
  paymentId: string
  initial: MockPayment
  onSuccess: () => void
  onClose: () => void
  onRetry: () => void
}

export default function PaymentQrModal({ paymentId, initial, onSuccess, onClose, onRetry }: Props) {
  const query = useMockPayment(paymentId)
  const cancel = useCancelMockPayment()
  const payment = query.data ?? initial
  // The parent passes a fresh callback every render; read it through a ref so a re-render
  // cannot cancel the pending redirect.
  const onSuccessRef = useRef(onSuccess)
  onSuccessRef.current = onSuccess

  useEffect(() => {
    if (payment.status !== 'SUCCESS') return
    const timer = window.setTimeout(() => onSuccessRef.current(), 1400) // let the success state be seen before leaving
    return () => window.clearTimeout(timer)
  }, [payment.status])

  const elapsed = Math.max(0, payment.expiresInSeconds - payment.remainingSeconds)
  const progress = payment.expiresInSeconds > 0 ? Math.min(100, (elapsed / payment.expiresInSeconds) * 100) : 100
  const name = methodName[payment.method] ?? payment.method

  return (
    <Modal title={`Thanh toán ${name}`} onClose={payment.status === 'PENDING' ? () => cancel.mutate(payment.id, { onSettled: onClose }) : onClose}>
      <div className="flex flex-col items-center text-center" aria-live="polite">
        <DemoBadge />
        {payment.status === 'PENDING' && payment.qr && (
          <>
            <p className="mt-3 text-sm text-muted">Quét mã bằng ứng dụng {name} để thanh toán</p>
            <div className="mt-4"><QrCode matrix={payment.qr.matrix} label={`Mã QR thanh toán ${name} giả lập`} /></div>
            <p className="mt-3 text-xs text-muted">{payment.qr.notice}</p>
            <p className="mt-3 text-2xl font-bold tabular-nums text-price">{vnd(payment.amount)}</p>
            <div className="mt-4 h-2 w-full max-w-xs overflow-hidden rounded bg-slate-100" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)}>
              <div className="h-full rounded bg-primary-600 transition-[width] duration-1000 ease-linear" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-2 text-sm font-semibold">Đang chờ thanh toán… còn {payment.remainingSeconds}s</p>
            <Button type="button" variant="ghost" className="mt-4" loading={cancel.isPending} onClick={() => cancel.mutate(payment.id, { onSettled: onClose })}>Huỷ thanh toán</Button>
          </>
        )}
        {payment.status === 'SUCCESS' && (
          <>
            <CheckCircle2 className="mt-5 h-16 w-16 text-primary-600" aria-hidden="true" />
            <h3 className="mt-3 text-xl font-bold">Thanh toán thành công</h3>
            <p className="mt-1 text-sm text-muted">Đang chuyển đến đơn hàng của bạn…</p>
          </>
        )}
        {(payment.status === 'FAILED' || payment.status === 'CANCELLED') && (
          <>
            <XCircle className="mt-5 h-16 w-16 text-danger" aria-hidden="true" />
            <h3 className="mt-3 text-xl font-bold">{payment.status === 'FAILED' ? 'Thanh toán thất bại' : 'Đã huỷ thanh toán'}</h3>
            <p className="mt-1 text-sm text-muted">Đơn hàng vẫn được giữ ở trạng thái chờ thanh toán.</p>
            <div className="mt-5 flex gap-3"><Button type="button" onClick={onRetry}>Thử lại</Button><Button type="button" variant="outline" onClick={onSuccess}>Xem đơn hàng</Button></div>
          </>
        )}
      </div>
    </Modal>
  )
}

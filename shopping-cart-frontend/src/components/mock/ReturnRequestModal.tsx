import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { useCreateReturn } from '@/hooks/useMock'
import type { ReturnReason } from '@/types/mock'
import { DemoBadge, ErrorLine } from './MockPrimitives'

const reasons: { value: ReturnReason; label: string }[] = [
  { value: 'DEFECTIVE', label: 'Sản phẩm bị lỗi' },
  { value: 'NOT_AS_DESCRIBED', label: 'Không đúng mô tả' },
  { value: 'WRONG_ITEM', label: 'Giao sai hàng' },
  { value: 'CHANGED_MIND', label: 'Đổi ý' },
]

export default function ReturnRequestModal({ orderId, amount, onClose }: { orderId: string; amount: number; onClose: () => void }) {
  const create = useCreateReturn()
  const [reason, setReason] = useState<ReturnReason>('DEFECTIVE')
  const [note, setNote] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await create.mutateAsync({ orderId, reason, note, amount })
    onClose()
  }

  return (
    <Modal title="Yêu cầu đổi trả" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <p className="flex items-center gap-2 text-sm text-muted">Yêu cầu sẽ hiện ở hàng đợi của quản trị viên. <DemoBadge /></p>
        <label className="block space-y-1.5 text-sm font-semibold"><span>Lý do</span>
          <select value={reason} onChange={(e) => setReason(e.target.value as ReturnReason)} className="focus-ring min-h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm font-normal">
            {reasons.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm font-semibold"><span>Mô tả thêm</span><textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} className="focus-ring w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
        {create.error && <ErrorLine error={create.error} />}
        <div className="flex justify-end gap-3"><Button type="button" variant="ghost" onClick={onClose}>Huỷ</Button><Button type="submit" loading={create.isPending}>Gửi yêu cầu</Button></div>
      </form>
    </Modal>
  )
}

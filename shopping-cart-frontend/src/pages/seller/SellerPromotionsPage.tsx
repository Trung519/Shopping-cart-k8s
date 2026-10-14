import { useState, type FormEvent } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Overlay'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, StatusBadge, vnd } from '@/components/mock/MockPrimitives'
import { useSellerCreatePromotion, useSellerPromotions, useSellerTogglePromotion } from '@/hooks/useMock'
import type { Promotion } from '@/types/mock'

const kindLabel = { percent: 'Giảm theo %', amount: 'Giảm số tiền', freeship: 'Miễn phí vận chuyển' } as const
const describe = (p: Promotion) => (p.kind === 'percent' ? `Giảm ${p.value}%` : p.kind === 'amount' ? `Giảm ${vnd(p.value)}` : `Hỗ trợ ship ${vnd(p.value)}`) + (p.minSpend > 0 ? ` cho đơn từ ${vnd(p.minSpend)}` : '')

export default function SellerPromotionsPage() {
  const promos = useSellerPromotions()
  const toggle = useSellerTogglePromotion()
  const [creating, setCreating] = useState(false)
  return (
    <MockPage title="Khuyến mãi" description="Tạo chương trình giảm giá cho gian hàng." actions={<Button type="button" onClick={() => setCreating(true)}><Plus className="mr-2 h-4 w-4" /> Tạo khuyến mãi</Button>}>
      {promos.isLoading ? <SkeletonRows rows={2} /> : promos.isError ? <ErrorLine error={promos.error} /> : promos.data?.length === 0 ? <EmptyLine>Chưa có khuyến mãi nào.</EmptyLine> : (
        <ul className="space-y-3">
          {promos.data?.map((promo) => (
            <li key={promo.id} className="surface-card flex flex-wrap items-center justify-between gap-3 p-4">
              <div><p className="font-semibold">{promo.name}</p><p className="mt-1 text-sm text-muted">{describe(promo)} · đã dùng {promo.used} lần</p></div>
              <div className="flex items-center gap-3"><StatusBadge status={promo.status} /><Button type="button" size="sm" variant="outline" loading={toggle.isPending && toggle.variables === promo.id} onClick={() => toggle.mutate(promo.id)}>{promo.status === 'ACTIVE' ? 'Tạm dừng' : 'Kích hoạt'}</Button></div>
            </li>
          ))}
        </ul>
      )}
      {creating && <CreateForm onClose={() => setCreating(false)} />}
    </MockPage>
  )
}

function CreateForm({ onClose }: { onClose: () => void }) {
  const create = useSellerCreatePromotion()
  const [form, setForm] = useState({ name: '', kind: 'percent' as Promotion['kind'], value: '10', minSpend: '0' })
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await create.mutateAsync({ name: form.name, kind: form.kind, value: Number(form.value), minSpend: Number(form.minSpend) })
    onClose()
  }
  return (
    <Modal title="Tạo khuyến mãi" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4">
        <label className="space-y-1.5 text-sm font-semibold"><span>Tên chương trình</span><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required minLength={3} maxLength={60} /></label>
        <label className="space-y-1.5 text-sm font-semibold"><span>Loại</span>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Promotion['kind'], value: e.target.value === 'percent' ? '10' : '30000' })} className="focus-ring min-h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm">
            {Object.entries(kindLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="space-y-1.5 text-sm font-semibold"><span>{form.kind === 'percent' ? 'Phần trăm giảm (1–90)' : 'Giá trị giảm (₫)'}</span><Input inputMode="numeric" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required /></label>
        <label className="space-y-1.5 text-sm font-semibold"><span>Đơn tối thiểu (₫)</span><Input inputMode="numeric" value={form.minSpend} onChange={(e) => setForm({ ...form, minSpend: e.target.value })} /></label>
        {create.error && <ErrorLine error={create.error} />}
        <div className="flex justify-end gap-3"><Button type="button" variant="ghost" onClick={onClose}>Huỷ</Button><Button type="submit" loading={create.isPending}>Tạo</Button></div>
      </form>
    </Modal>
  )
}

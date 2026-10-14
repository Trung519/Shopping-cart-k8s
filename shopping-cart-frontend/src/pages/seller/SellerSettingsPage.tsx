import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorLine, MockPage, SkeletonRows } from '@/components/mock/MockPrimitives'
import { useSellerSaveSettings, useSellerSettings } from '@/hooks/useMock'
import type { SellerSettings } from '@/types/mock'

export default function SellerSettingsPage() {
  const settings = useSellerSettings()
  const save = useSellerSaveSettings()
  const [form, setForm] = useState<SellerSettings | null>(null)

  useEffect(() => {
    if (settings.data) setForm(settings.data)
  }, [settings.data])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (form) await save.mutateAsync(form)
  }
  const set = <K extends keyof SellerSettings>(key: K, value: SellerSettings[K]) => setForm((current) => (current ? { ...current, [key]: value } : current))

  return (
    <MockPage title="Thiết lập shop" description="Thông tin hiển thị, chính sách đổi trả và thông báo.">
      {settings.isLoading || !form ? (settings.isError ? <ErrorLine error={settings.error} /> : <SkeletonRows rows={3} />) : (
        <form onSubmit={submit} className="max-w-2xl space-y-5">
          <label className="block space-y-1.5 text-sm font-semibold"><span>Tên gian hàng</span><Input value={form.shopName} onChange={(e) => set('shopName', e.target.value)} required minLength={2} maxLength={60} /></label>
          <label className="block space-y-1.5 text-sm font-semibold"><span>Giới thiệu</span><textarea value={form.description} onChange={(e) => set('description', e.target.value)} maxLength={300} rows={3} className="focus-ring w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm font-semibold"><span>Số điện thoại</span><Input type="tel" value={form.phone} onChange={(e) => set('phone', e.target.value)} pattern="[0-9+ ]{9,15}" /></label>
            <label className="block space-y-1.5 text-sm font-semibold"><span>Đổi trả trong (ngày)</span><Input type="number" min={0} max={30} value={form.returnDays} onChange={(e) => set('returnDays', Number(e.target.value))} /></label>
          </div>
          <fieldset className="space-y-3 rounded-card border border-line p-4">
            <legend className="px-1 text-sm font-semibold">Tuỳ chọn</legend>
            <Toggle label="Chế độ nghỉ (tạm ngừng nhận đơn)" checked={form.vacationMode} onChange={(v) => set('vacationMode', v)} />
            <Toggle label="Thông báo khi có đơn mới" checked={form.notifyOrders} onChange={(v) => set('notifyOrders', v)} />
            <Toggle label="Thông báo khi có tin nhắn" checked={form.notifyMessages} onChange={(v) => set('notifyMessages', v)} />
          </fieldset>
          {save.error && <ErrorLine error={save.error} />}
          <div className="flex items-center gap-3"><Button type="submit" loading={save.isPending}>Lưu thay đổi</Button>{save.isSuccess && !save.isPending && <span role="status" className="text-sm text-primary-700">Đã lưu</span>}</div>
        </form>
      )}
    </MockPage>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-primary-600" />{label}</label>
}

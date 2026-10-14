import { useState, type FormEvent } from 'react'
import { MapPin, Pencil, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Overlay'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows } from '@/components/mock/MockPrimitives'
import { useAddresses, useCreateAddress, useDeleteAddress, useSetDefaultAddress, useUpdateAddress } from '@/hooks/useMock'
import type { MockAddress, MockAddressInput } from '@/types/mock'

const blank: MockAddressInput = { fullName: '', phone: '', province: '', district: '', ward: '', street: '', isDefault: false }

export default function AddressesPage() {
  const list = useAddresses()
  const remove = useDeleteAddress()
  const makeDefault = useSetDefaultAddress()
  const [editing, setEditing] = useState<MockAddress | 'new' | null>(null)

  return (
    <MockPage
      title="Sổ địa chỉ"
      description="Quản lý nơi nhận hàng. Địa chỉ mặc định được điền sẵn ở bước thanh toán."
      actions={<Button type="button" onClick={() => setEditing('new')}><Plus className="mr-2 h-4 w-4" /> Thêm địa chỉ</Button>}
    >
      {list.isLoading ? <SkeletonRows rows={2} /> : list.isError ? <ErrorLine error={list.error} /> : list.data?.length === 0 ? (
        <EmptyLine>Chưa có địa chỉ nào. Thêm địa chỉ để thanh toán nhanh hơn.</EmptyLine>
      ) : (
        <ul className="space-y-3">
          {list.data?.map((address) => (
            <li key={address.id} className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex gap-3">
                <MapPin className="mt-0.5 h-5 w-5 flex-none text-primary-600" aria-hidden="true" />
                <div>
                  <p className="font-semibold">{address.fullName} <span className="font-normal text-muted">· {address.phone}</span>{address.isDefault && <span className="ml-2 rounded bg-primary-100 px-2 py-0.5 text-xs font-semibold text-primary-800">Mặc định</span>}</p>
                  <p className="mt-1 text-sm text-muted">{address.street}, {address.ward}, {address.district}, {address.province}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {!address.isDefault && <Button type="button" variant="outline" size="sm" loading={makeDefault.isPending} onClick={() => makeDefault.mutate(address.id)}>Đặt mặc định</Button>}
                <Button type="button" variant="ghost" size="sm" aria-label={`Sửa địa chỉ của ${address.fullName}`} onClick={() => setEditing(address)}><Pencil className="h-4 w-4" /></Button>
                <Button type="button" variant="ghost" size="sm" aria-label={`Xoá địa chỉ của ${address.fullName}`} loading={remove.isPending} onClick={() => remove.mutate(address.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {editing && <AddressForm address={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </MockPage>
  )
}

export function AddressForm({ address, onClose, onSaved }: { address: MockAddress | null; onClose: () => void; onSaved?: (address: MockAddress) => void }) {
  const create = useCreateAddress()
  const update = useUpdateAddress()
  const [form, setForm] = useState<MockAddressInput>(address ? { ...address } : blank)
  const mutation = address ? update : create
  const set = (field: keyof MockAddressInput, value: string | boolean) => setForm((current) => ({ ...current, [field]: value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const saved = address ? await update.mutateAsync({ id: address.id, input: form }) : await create.mutateAsync(form)
    onSaved?.(saved)
    onClose()
  }

  return (
    <Modal title={address ? 'Sửa địa chỉ' : 'Thêm địa chỉ'} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Họ và tên"><Input value={form.fullName} onChange={(e) => set('fullName', e.target.value)} required /></Field>
        <Field label="Số điện thoại"><Input type="tel" inputMode="tel" value={form.phone} onChange={(e) => set('phone', e.target.value)} pattern="[0-9+ ]{9,15}" required /></Field>
        <Field label="Tỉnh / thành phố"><Input value={form.province} onChange={(e) => set('province', e.target.value)} required /></Field>
        <Field label="Quận / huyện"><Input value={form.district} onChange={(e) => set('district', e.target.value)} required /></Field>
        <Field label="Phường / xã"><Input value={form.ward} onChange={(e) => set('ward', e.target.value)} required /></Field>
        <Field label="Địa chỉ cụ thể"><Input value={form.street} onChange={(e) => set('street', e.target.value)} required /></Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={form.isDefault} onChange={(e) => set('isDefault', e.target.checked)} className="h-4 w-4 accent-primary-600" /> Đặt làm địa chỉ mặc định</label>
        {mutation.error && <div className="sm:col-span-2"><ErrorLine error={mutation.error} /></div>}
        <div className="flex justify-end gap-3 sm:col-span-2"><Button type="button" variant="ghost" onClick={onClose}>Huỷ</Button><Button type="submit" loading={mutation.isPending}>Lưu địa chỉ</Button></div>
      </form>
    </Modal>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="space-y-1.5 text-sm font-semibold"><span>{label}</span>{children}</label>
}

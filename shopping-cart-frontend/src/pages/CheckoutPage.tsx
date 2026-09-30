import { useState, type FormEvent, type ReactNode } from 'react'
import { ArrowLeft, Check, CreditCard, MapPin, PackageCheck, ShieldCheck, Truck } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import ProductImage from '@/components/product/ProductImage'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCart, useCheckout } from '@/hooks/useCart'
import { formatCurrency } from '@/utils/format'
import type { CheckoutAddress } from '@/types'

const initialAddress: CheckoutAddress = {
  fullName: '', phone: '', street: '', ward: '', district: '', province: '', city: '', state: '', postalCode: '700000', country: 'VN',
}

const steps = [
  { label: 'Địa chỉ', icon: MapPin },
  { label: 'Vận chuyển', icon: Truck },
  { label: 'Thanh toán', icon: CreditCard },
  { label: 'Xác nhận', icon: PackageCheck },
]

export default function CheckoutPage() {
  const navigate = useNavigate()
  const cartQuery = useCart()
  const checkout = useCheckout()
  const [step, setStep] = useState(1)
  const [address, setAddress] = useState(initialAddress)
  const [shipping, setShipping] = useState('standard')
  const [payment, setPayment] = useState('mock')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const cart = cartQuery.data

  if (cartQuery.isLoading) return <div className="flex min-h-[60vh] items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (!cart || cart.items.length === 0) return <Navigate to="/cart" replace />

  const setField = (field: keyof CheckoutAddress, value: string) => setAddress((current) => ({ ...current, [field]: value, ...(field === 'province' ? { city: value } : {}) }))
  const nextFromAddress = (event: FormEvent) => { event.preventDefault(); setStep(2) }
  const placeOrder = async () => {
    setSubmitError(null)
    try {
      const result = await checkout.mutateAsync(address)
      navigate(result.orderId ? `/orders/${result.orderId}` : '/orders', { replace: true })
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Không thể tạo đơn hàng')
    }
  }

  return (
    <div className="market-container py-7 sm:py-10">
      <button type="button" onClick={() => step === 1 ? navigate('/cart') : setStep((value) => value - 1)} className="focus-ring mb-5 inline-flex items-center gap-2 rounded-xl text-sm font-semibold text-slate-600 hover:text-primary-600"><ArrowLeft className="h-4 w-4" /> Quay lại</button>
      <div className="surface-card mb-8 grid grid-cols-4 px-2 py-4 sm:px-6">{steps.map(({ label, icon: Icon }, index) => { const number = index + 1; const active = number === step; const done = number < step; return <div key={label} className="relative flex flex-col items-center gap-2 text-center"><span className={`z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 ${done ? 'border-emerald bg-emerald text-white' : active ? 'border-primary-600 bg-primary-600 text-white' : 'border-slate-200 bg-white text-slate-400'}`}>{done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</span><span className={`text-xs font-semibold ${active ? 'text-primary-600' : done ? 'text-emerald' : 'text-slate-400'}`}>{label}</span>{index < steps.length - 1 && <span className={`absolute left-[62%] top-4 h-0.5 w-[76%] ${done ? 'bg-emerald' : 'bg-slate-200'}`} />}</div> })}</div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="surface-card p-5 sm:p-7">
          {step === 1 && <AddressStep address={address} setField={setField} submit={nextFromAddress} />}
          {step === 2 && <ShippingStep value={shipping} setValue={setShipping} next={() => setStep(3)} />}
          {step === 3 && <PaymentStep value={payment} setValue={setPayment} next={() => setStep(4)} />}
          {step === 4 && <ReviewStep address={address} shipping={shipping} payment={payment} submit={placeOrder} pending={checkout.isPending} error={submitError} />}
        </section>
        <aside className="surface-card sticky top-28 p-5"><h2 className="font-extrabold">Đơn hàng ({cart.items.length} sản phẩm)</h2><div className="mt-4 max-h-64 space-y-3 overflow-y-auto pr-1">{cart.items.map((item) => <div key={item.id} className="flex gap-3"><div className="h-14 w-14 flex-none overflow-hidden rounded-xl bg-slate-100"><ProductImage src={item.imageUrl} alt={item.name} className="h-full w-full object-cover" /></div><div className="min-w-0 flex-1"><p className="line-clamp-2 text-xs font-semibold">{item.name}</p><p className="mt-1 text-xs text-slate-500">x{item.quantity}</p></div><p className="text-xs font-bold">{formatCurrency(item.subTotal, cart.currency)}</p></div>)}</div><div className="my-5 border-t border-slate-200" /><div className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-500">Tạm tính</span><span>{formatCurrency(cart.totalAmount, cart.currency)}</span></div><div className="flex justify-between"><span className="text-slate-500">Vận chuyển</span><span className="text-slate-500">Tính ở bước sau</span></div></div><div className="my-5 border-t border-slate-200" /><div className="flex items-end justify-between"><span className="font-bold">Tổng cộng</span><span className="text-xl font-extrabold text-primary-600">{formatCurrency(cart.totalAmount, cart.currency)}</span></div></aside>
      </div>
    </div>
  )
}

function AddressStep({ address, setField, submit }: { address: CheckoutAddress; setField: (field: keyof CheckoutAddress, value: string) => void; submit: (event: FormEvent) => void }) {
  return <form onSubmit={submit}><h1 className="text-xl font-black">Địa chỉ nhận hàng</h1><p className="mt-1 text-sm text-gray-500">Thông tin này được lưu vào đơn hàng, không dùng địa chỉ giả.</p><div className="mt-6 grid gap-4 sm:grid-cols-2"><Field label="Họ và tên"><Input value={address.fullName} onChange={(event) => setField('fullName', event.target.value)} required /></Field><Field label="Số điện thoại"><Input type="tel" inputMode="tel" value={address.phone} onChange={(event) => setField('phone', event.target.value)} pattern="[0-9+ ]{9,15}" required /></Field><Field label="Tỉnh / thành phố"><Input value={address.province} onChange={(event) => setField('province', event.target.value)} placeholder="TP. Hồ Chí Minh" required /></Field><Field label="Quận / huyện"><Input value={address.district} onChange={(event) => setField('district', event.target.value)} placeholder="Quận 1" required /></Field><Field label="Phường / xã"><Input value={address.ward} onChange={(event) => setField('ward', event.target.value)} placeholder="Phường Bến Nghé" required /></Field><Field label="Địa chỉ cụ thể"><Input value={address.street} onChange={(event) => setField('street', event.target.value)} placeholder="Số nhà, tên đường" required /></Field></div><div className="mt-7 flex justify-end"><Button type="submit" size="lg">Tiếp tục</Button></div></form>
}

function ShippingStep({ value, setValue, next }: { value: string; setValue: (value: string) => void; next: () => void }) { return <div><h1 className="text-xl font-black">Phương thức vận chuyển</h1><p className="mt-1 text-sm text-gray-500">Adapter vận chuyển local mô phỏng báo giá và thời gian giao.</p><div className="mt-6 space-y-3"><Choice selected={value === 'standard'} onSelect={() => setValue('standard')} title="Giao hàng tiêu chuẩn" detail="Dự kiến 2-4 ngày · Miễn phí" icon={Truck} /><Choice selected={value === 'express'} onSelect={() => setValue('express')} title="Giao hàng nhanh" detail="Dự kiến 1-2 ngày · Mô phỏng 30.000đ" icon={PackageCheck} /></div><div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={next}>Tiếp tục</Button></div></div> }
function PaymentStep({ value, setValue, next }: { value: string; setValue: (value: string) => void; next: () => void }) { return <div><h1 className="text-xl font-black">Phương thức thanh toán</h1><p className="mt-1 text-sm text-gray-500">Không kết nối tài khoản thanh toán bên ngoài trong môi trường local.</p><div className="mt-6 space-y-3"><Choice selected={value === 'mock'} onSelect={() => setValue('mock')} title="Thanh toán mô phỏng" detail="Kiểm thử luồng payment và idempotency, không thu tiền thật" icon={CreditCard} /><Choice selected={value === 'cod'} onSelect={() => setValue('cod')} title="Thanh toán khi nhận hàng" detail="COD mô phỏng cho đơn local" icon={PackageCheck} /></div><div className="mt-5 flex items-start gap-2 rounded-lg border border-emerald/30 bg-emerald/5 p-4 text-sm leading-6 text-emerald"><ShieldCheck className="mt-0.5 h-5 w-5 flex-none" /> Thông tin thẻ thô không được gửi hoặc lưu trong giao diện này.</div><div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={next}>Xem lại đơn</Button></div></div> }
function ReviewStep({ address, shipping, payment, submit, pending, error }: { address: CheckoutAddress; shipping: string; payment: string; submit: () => void; pending: boolean; error: string | null }) { return <div><h1 className="text-xl font-black">Xác nhận đặt hàng</h1><div className="mt-6 divide-y rounded-lg border"><ReviewRow label="Người nhận" value={`${address.fullName} · ${address.phone}`} /><ReviewRow label="Địa chỉ" value={`${address.street}, ${address.ward}, ${address.district}, ${address.province}`} /><ReviewRow label="Vận chuyển" value={shipping === 'express' ? 'Giao hàng nhanh' : 'Giao hàng tiêu chuẩn'} /><ReviewRow label="Thanh toán" value={payment === 'cod' ? 'Thanh toán khi nhận hàng' : 'Thanh toán mô phỏng'} /></div>{error && <p className="mt-4 rounded-md bg-primary-50 p-3 text-sm text-primary-700">{error}</p>}<div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={submit} loading={pending}>Đặt hàng</Button></div></div> }
function Choice({ selected, onSelect, title, detail, icon: Icon }: { selected: boolean; onSelect: () => void; title: string; detail: string; icon: typeof Truck }) { return <button type="button" onClick={onSelect} className={`focus-ring flex w-full items-center gap-4 rounded-lg border-2 p-4 text-left ${selected ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}`}><span className={`flex h-11 w-11 flex-none items-center justify-center rounded-md ${selected ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-500'}`}><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><strong className="block text-sm">{title}</strong><span className="mt-1 block text-xs text-gray-500">{detail}</span></span><span className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${selected ? 'border-primary-600 bg-primary-600 text-white' : 'border-gray-300'}`}>{selected && <Check className="h-3 w-3" />}</span></button> }
function ReviewRow({ label, value }: { label: string; value: string }) { return <div className="grid gap-1 p-4 sm:grid-cols-[130px_1fr]"><span className="text-sm text-gray-500">{label}</span><span className="text-sm font-semibold">{value}</span></div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="space-y-2 text-sm font-semibold text-gray-700"><span>{label}</span>{children}</label> }

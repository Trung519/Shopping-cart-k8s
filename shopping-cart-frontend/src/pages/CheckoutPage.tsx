import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { ArrowLeft, Check, CreditCard, MapPin, PackageCheck, Plus, ShieldCheck, Truck } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import ProductImage from '@/components/product/ProductImage'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCart, useCheckout } from '@/hooks/useCart'
import { useAddresses, useCreateMockPayment, useMockEnabled } from '@/hooks/useMock'
import { formatCurrency } from '@/utils/format'
import { useVoucherStore } from '@/stores/voucherStore'
import { DemoBadge } from '@/components/mock/MockPrimitives'
import PaymentQrModal from '@/components/mock/PaymentQrModal'
import VoucherBox from '@/components/mock/VoucherBox'
import { AddressForm } from '@/pages/buyer/AddressesPage'
import type { Cart, CheckoutAddress } from '@/types'
import type { MockAddress, MockPayment, MockPaymentMethod } from '@/types/mock'

const initialAddress: CheckoutAddress = {
  fullName: '', phone: '', street: '', ward: '', district: '', province: '', city: '', state: '', postalCode: '700000', country: 'VN',
}

const steps = [
  { label: 'Địa chỉ', icon: MapPin },
  { label: 'Vận chuyển', icon: Truck },
  { label: 'Thanh toán', icon: CreditCard },
  { label: 'Xác nhận', icon: PackageCheck },
]

const walletMethods: MockPaymentMethod[] = ['momo', 'vnpay', 'zalopay']
const paymentLabels: Record<string, string> = { mock: 'Thanh toán mô phỏng', cod: 'Thanh toán khi nhận hàng', momo: 'Ví MoMo (QR giả lập)', vnpay: 'VNPay (QR giả lập)', zalopay: 'ZaloPay (QR giả lập)' }

interface QrState { orderId: string; payment: MockPayment; amount: number }

export default function CheckoutPage() {
  const navigate = useNavigate()
  const cartQuery = useCart()
  const checkout = useCheckout()
  const mock = useMockEnabled()
  const addresses = useAddresses()
  const createPayment = useCreateMockPayment()
  const applied = useVoucherStore((state) => state.applied)
  const [step, setStep] = useState(1)
  const [address, setAddress] = useState(initialAddress)
  const [shipping, setShipping] = useState('standard')
  const [payment, setPayment] = useState('mock')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [qr, setQr] = useState<QrState | null>(null)
  const placing = useRef(false)
  const lastCart = useRef<Cart | undefined>(undefined)

  // Checkout empties the server cart; keep the last non-empty cart on screen while the payment modal is open.
  const liveCart = cartQuery.data
  const hasItems = Boolean(liveCart && liveCart.items.length > 0)
  if (hasItems) lastCart.current = liveCart
  const cart = hasItems ? liveCart : placing.current || qr ? lastCart.current : undefined

  const method = mock.enabled && payment === 'mock' ? 'momo' : payment
  const discount = applied?.discount ?? 0

  const fillFrom = (saved: MockAddress) => setAddress((current) => ({ ...current, fullName: saved.fullName, phone: saved.phone, province: saved.province, city: saved.province, district: saved.district, ward: saved.ward, street: saved.street }))
  const defaultAddress = addresses.data?.find((item) => item.isDefault)
  useEffect(() => {
    if (defaultAddress && !address.fullName && !address.street) fillFrom(defaultAddress)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultAddress?.id])

  if (cartQuery.isLoading) return <div className="flex min-h-[60vh] items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (!cart || cart.items.length === 0) return <Navigate to="/cart" replace />

  const payable = Math.max(0, cart.totalAmount - discount)
  const setField = (field: keyof CheckoutAddress, value: string) => setAddress((current) => ({ ...current, [field]: value, ...(field === 'province' ? { city: value } : {}) }))
  const nextFromAddress = (event: FormEvent) => { event.preventDefault(); setStep(2) }
  const goToOrder = (orderId: string) => navigate(`/orders/${orderId}`, { replace: true })

  const startMockPayment = async (orderId: string) => {
    const created = await createPayment.mutateAsync({ orderId, method: method as MockPaymentMethod, amount: payable })
    if (created.status === 'SUCCESS') return goToOrder(orderId) // COD has no QR step
    setQr({ orderId, payment: created, amount: payable })
  }

  const placeOrder = async () => {
    setSubmitError(null)
    placing.current = true
    try {
      const result = await checkout.mutateAsync(address)
      if (mock.enabled && result.orderId && (walletMethods.includes(method as MockPaymentMethod) || method === 'cod')) {
        await startMockPayment(result.orderId)
        return
      }
      navigate(result.orderId ? `/orders/${result.orderId}` : '/orders', { replace: true })
    } catch (error) {
      placing.current = false
      setSubmitError(error instanceof Error ? error.message : 'Không thể tạo đơn hàng')
    }
  }

  const retryPayment = async () => {
    if (!qr) return
    const created = await createPayment.mutateAsync({ orderId: qr.orderId, method: method as MockPaymentMethod, amount: qr.amount })
    setQr({ ...qr, payment: created })
  }

  return (
    <div className="market-container py-7 sm:py-10">
      <button type="button" onClick={() => step === 1 ? navigate('/cart') : setStep((value) => value - 1)} className="focus-ring mb-5 inline-flex items-center gap-2 rounded-md text-sm font-semibold text-slate-600 hover:text-primary-600"><ArrowLeft className="h-4 w-4" /> Quay lại</button>
      <div className="surface-card mb-8 grid grid-cols-4 px-2 py-4 sm:px-6">{steps.map(({ label, icon: Icon }, index) => { const number = index + 1; const active = number === step; const done = number < step; return <div key={label} className="relative flex flex-col items-center gap-2 text-center"><span className={`z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 ${done ? 'border-emerald bg-emerald text-white' : active ? 'border-primary-600 bg-primary-600 text-white' : 'border-line bg-white text-muted'}`}>{done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</span><span className={`text-xs font-semibold ${active ? 'text-primary-600' : done ? 'text-emerald' : 'text-muted'}`}>{label}</span>{index < steps.length - 1 && <span className={`absolute left-[62%] top-4 h-0.5 w-[76%] ${done ? 'bg-emerald' : 'bg-slate-200'}`} />}</div> })}</div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="surface-card p-5 sm:p-7">
          {step === 1 && <AddressStep address={address} setField={setField} submit={nextFromAddress} onPick={fillFrom} />}
          {step === 2 && <ShippingStep value={shipping} setValue={setShipping} next={() => setStep(3)} />}
          {step === 3 && <PaymentStep value={method} setValue={setPayment} next={() => setStep(4)} mockEnabled={mock.enabled} />}
          {step === 4 && <ReviewStep address={address} shipping={shipping} payment={method} submit={placeOrder} pending={checkout.isPending || createPayment.isPending} error={submitError || (createPayment.error ? createPayment.error.message : null)} />}
        </section>
        <aside className="surface-card sticky top-28 p-5"><h2 className="font-extrabold">Đơn hàng ({cart.items.length} sản phẩm)</h2><div className="mt-4 max-h-64 space-y-3 overflow-y-auto pr-1">{cart.items.map((item) => <div key={item.id} className="flex gap-3"><div className="h-14 w-14 flex-none overflow-hidden rounded-md bg-slate-100"><ProductImage src={item.imageUrl} alt={item.name} className="h-full w-full object-cover" /></div><div className="min-w-0 flex-1"><p className="line-clamp-2 text-xs font-semibold">{item.name}</p><p className="mt-1 text-xs text-muted">x{item.quantity}</p></div><p className="text-xs font-bold">{formatCurrency(item.subTotal, cart.currency)}</p></div>)}</div><div className="my-5 border-t border-line" /><VoucherBox subtotal={cart.totalAmount} /><div className="my-5 border-t border-line" /><div className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-muted">Tạm tính</span><span>{formatCurrency(cart.totalAmount, cart.currency)}</span></div><div className="flex justify-between"><span className="text-muted">Vận chuyển</span><span className="text-muted">Tính ở bước sau</span></div>{discount > 0 && <div className="flex justify-between"><span className="text-muted">Giảm giá (demo)</span><span>-{formatCurrency(discount, cart.currency)}</span></div>}</div><div className="my-5 border-t border-line" /><div className="flex items-end justify-between"><span className="font-bold">Tổng cộng</span><span className="text-xl font-bold text-price">{formatCurrency(payable, cart.currency)}</span></div></aside>
      </div>

      {qr && <PaymentQrModal key={qr.payment.id} paymentId={qr.payment.id} initial={qr.payment} onSuccess={() => goToOrder(qr.orderId)} onClose={() => goToOrder(qr.orderId)} onRetry={retryPayment} />}
    </div>
  )
}

function SavedAddresses({ onPick }: { onPick: (address: MockAddress) => void }) {
  const mock = useMockEnabled()
  const list = useAddresses()
  const [adding, setAdding] = useState(false)
  if (!mock.enabled) return null
  return (
    <div className="mt-5">
      <div className="flex items-center justify-between"><p className="flex items-center gap-2 text-sm font-semibold">Địa chỉ đã lưu <DemoBadge /></p><Button type="button" variant="ghost" size="sm" onClick={() => setAdding(true)}><Plus className="mr-1 h-4 w-4" /> Thêm mới</Button></div>
      {list.data && list.data.length > 0 ? (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {list.data.map((item) => (
            <li key={item.id}>
              <button type="button" onClick={() => onPick(item)} className="focus-ring w-full rounded-md border border-line p-3 text-left text-sm hover:border-primary-300">
                <span className="font-semibold">{item.fullName}</span>{item.isDefault && <span className="ml-2 rounded bg-primary-100 px-1.5 py-0.5 text-xs font-semibold text-primary-800">Mặc định</span>}
                <span className="mt-1 block text-xs text-muted">{item.street}, {item.ward}, {item.district}, {item.province}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="mt-2 text-sm text-muted">Chưa có địa chỉ đã lưu. Nhập bên dưới hoặc thêm mới.</p>}
      {adding && <AddressForm address={null} onClose={() => setAdding(false)} onSaved={onPick} />}
    </div>
  )
}

function AddressStep({ address, setField, submit, onPick }: { address: CheckoutAddress; setField: (field: keyof CheckoutAddress, value: string) => void; submit: (event: FormEvent) => void; onPick: (address: MockAddress) => void }) {
  return <form onSubmit={submit}><h1 className="text-xl font-black">Địa chỉ nhận hàng</h1><p className="mt-1 text-sm text-muted">Thông tin này được lưu vào đơn hàng.</p><SavedAddresses onPick={onPick} /><div className="mt-6 grid gap-4 sm:grid-cols-2"><Field label="Họ và tên"><Input value={address.fullName} onChange={(event) => setField('fullName', event.target.value)} required /></Field><Field label="Số điện thoại"><Input type="tel" inputMode="tel" value={address.phone} onChange={(event) => setField('phone', event.target.value)} pattern="[0-9+ ]{9,15}" required /></Field><Field label="Tỉnh / thành phố"><Input value={address.province} onChange={(event) => setField('province', event.target.value)} placeholder="TP. Hồ Chí Minh" required /></Field><Field label="Quận / huyện"><Input value={address.district} onChange={(event) => setField('district', event.target.value)} placeholder="Quận 1" required /></Field><Field label="Phường / xã"><Input value={address.ward} onChange={(event) => setField('ward', event.target.value)} placeholder="Phường Bến Nghé" required /></Field><Field label="Địa chỉ cụ thể"><Input value={address.street} onChange={(event) => setField('street', event.target.value)} placeholder="Số nhà, tên đường" required /></Field></div><div className="mt-7 flex justify-end"><Button type="submit" size="lg">Tiếp tục</Button></div></form>
}

function ShippingStep({ value, setValue, next }: { value: string; setValue: (value: string) => void; next: () => void }) { return <div><h1 className="text-xl font-black">Phương thức vận chuyển</h1><p className="mt-1 text-sm text-muted">Adapter vận chuyển local mô phỏng báo giá và thời gian giao.</p><div className="mt-6 space-y-3"><Choice selected={value === 'standard'} onSelect={() => setValue('standard')} title="Giao hàng tiêu chuẩn" detail="Dự kiến 2-4 ngày · Miễn phí" icon={Truck} /><Choice selected={value === 'express'} onSelect={() => setValue('express')} title="Giao hàng nhanh" detail="Dự kiến 1-2 ngày · Mô phỏng 30.000đ" icon={PackageCheck} /></div><div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={next}>Tiếp tục</Button></div></div> }

function PaymentStep({ value, setValue, next, mockEnabled }: { value: string; setValue: (value: string) => void; next: () => void; mockEnabled: boolean }) {
  return (
    <div>
      <h1 className="text-xl font-black">Phương thức thanh toán</h1>
      <p className="mt-1 text-sm text-muted">{mockEnabled ? 'Ví điện tử là giả lập: hiện mã QR ảo rồi tự xác nhận sau vài giây.' : 'Không kết nối tài khoản thanh toán bên ngoài trong môi trường local.'}</p>
      <div className="mt-6 space-y-3">
        {mockEnabled ? (
          <>
            <Choice selected={value === 'momo'} onSelect={() => setValue('momo')} title="Ví MoMo" detail="Quét mã QR giả lập · Demo" icon={CreditCard} />
            <Choice selected={value === 'vnpay'} onSelect={() => setValue('vnpay')} title="VNPay" detail="Quét mã QR giả lập · Demo" icon={CreditCard} />
            <Choice selected={value === 'zalopay'} onSelect={() => setValue('zalopay')} title="ZaloPay" detail="Quét mã QR giả lập · Demo" icon={CreditCard} />
          </>
        ) : (
          <Choice selected={value === 'mock'} onSelect={() => setValue('mock')} title="Thanh toán mô phỏng" detail="Kiểm thử luồng payment và idempotency, không thu tiền thật" icon={CreditCard} />
        )}
        <Choice selected={value === 'cod'} onSelect={() => setValue('cod')} title="Thanh toán khi nhận hàng" detail="COD mô phỏng cho đơn local" icon={PackageCheck} />
      </div>
      <div className="mt-5 flex items-start gap-2 rounded-lg border border-emerald/30 bg-emerald/5 p-4 text-sm leading-6 text-emerald"><ShieldCheck className="mt-0.5 h-5 w-5 flex-none" /> Thông tin thẻ thô không được gửi hoặc lưu trong giao diện này.</div>
      <div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={next}>Xem lại đơn</Button></div>
    </div>
  )
}

function ReviewStep({ address, shipping, payment, submit, pending, error }: { address: CheckoutAddress; shipping: string; payment: string; submit: () => void; pending: boolean; error: string | null }) { return <div><h1 className="text-xl font-black">Xác nhận đặt hàng</h1><div className="mt-6 divide-y rounded-lg border"><ReviewRow label="Người nhận" value={`${address.fullName} · ${address.phone}`} /><ReviewRow label="Địa chỉ" value={`${address.street}, ${address.ward}, ${address.district}, ${address.province}`} /><ReviewRow label="Vận chuyển" value={shipping === 'express' ? 'Giao hàng nhanh' : 'Giao hàng tiêu chuẩn'} /><ReviewRow label="Thanh toán" value={paymentLabels[payment] ?? payment} /></div>{error && <p role="alert" className="mt-4 rounded-md bg-danger-soft p-3 text-sm text-danger">{error}</p>}<div className="mt-7 flex justify-end"><Button type="button" size="lg" onClick={submit} loading={pending}>Đặt hàng</Button></div></div> }
function Choice({ selected, onSelect, title, detail, icon: Icon }: { selected: boolean; onSelect: () => void; title: string; detail: string; icon: typeof Truck }) { return <button type="button" onClick={onSelect} aria-pressed={selected} className={`focus-ring flex w-full items-center gap-4 rounded-lg border-2 p-4 text-left ${selected ? 'border-primary-500 bg-primary-50' : 'border-line hover:border-slate-300'}`}><span className={`flex h-11 w-11 flex-none items-center justify-center rounded-md ${selected ? 'bg-primary-600 text-white' : 'bg-slate-100 text-muted'}`}><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><strong className="block text-sm">{title}</strong><span className="mt-1 block text-xs text-muted">{detail}</span></span><span className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${selected ? 'border-primary-600 bg-primary-600 text-white' : 'border-slate-300'}`}>{selected && <Check className="h-3 w-3" />}</span></button> }
function ReviewRow({ label, value }: { label: string; value: string }) { return <div className="grid gap-1 p-4 sm:grid-cols-[130px_1fr]"><span className="text-sm text-muted">{label}</span><span className="text-sm font-semibold">{value}</span></div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="space-y-2 text-sm font-semibold text-slate-700"><span>{label}</span>{children}</label> }

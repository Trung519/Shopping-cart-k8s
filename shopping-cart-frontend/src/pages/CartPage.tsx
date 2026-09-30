import { Minus, PackageOpen, Plus, ShieldCheck, ShoppingBag, Trash2, Truck } from 'lucide-react'
import { Link } from 'react-router-dom'
import ProductImage from '@/components/product/ProductImage'
import { Button } from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCart, useRemoveCartItem, useUpdateCartItem } from '@/hooks/useCart'
import { formatCurrency } from '@/utils/format'
import type { CartItem } from '@/types'

export default function CartPage() {
  const cartQuery = useCart()
  if (cartQuery.isLoading) return <div className="flex min-h-[60vh] items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (cartQuery.isError) return <div className="market-container py-16 text-center text-primary-700">Không thể tải giỏ hàng.</div>
  const cart = cartQuery.data
  if (!cart || cart.items.length === 0) return <EmptyCart />

  const groups = groupByShop(cart.items)
  return (
    <div className="market-container py-7 sm:py-10">
      <div className="mb-6 flex items-end justify-between"><div><p className="eyebrow">Đơn mua</p><h1 className="page-heading mt-1">Giỏ hàng của bạn</h1></div><p className="text-sm text-slate-500">{cart.items.reduce((sum, item) => sum + item.quantity, 0)} sản phẩm</p></div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">{Object.entries(groups).map(([shopName, items]) => <section key={shopName} className="surface-card overflow-hidden"><div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-50 text-primary-600"><ShoppingBag className="h-4 w-4" /></span> {shopName}</div><div className="divide-y divide-slate-200">{items.map((item) => <CartRow key={item.id} item={item} currency={cart.currency} />)}</div><div className="flex items-center gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500"><Truck className="h-4 w-4 text-emerald" /> Phí và thời gian vận chuyển được xác nhận khi checkout.</div></section>)}</div>
        <aside className="surface-card sticky top-28 p-5 sm:p-6"><h2 className="text-lg font-extrabold">Tóm tắt đơn hàng</h2><div className="mt-5 space-y-3 text-sm"><SummaryRow label="Tạm tính" value={formatCurrency(cart.totalAmount, cart.currency)} /><SummaryRow label="Phí vận chuyển" value="Tính ở bước sau" muted /><SummaryRow label="Giảm giá" value="Chưa áp dụng" muted /></div><div className="my-5 border-t border-slate-200" /><div className="flex items-end justify-between"><span className="font-bold">Tổng thanh toán</span><span className="text-2xl font-extrabold tracking-[-0.02em] text-primary-600">{formatCurrency(cart.totalAmount, cart.currency)}</span></div><p className="mt-2 text-right text-xs text-slate-400">Đã bao gồm thuế nếu áp dụng</p><Link to="/checkout" className="focus-ring mt-5 flex min-h-12 w-full items-center justify-center rounded-xl bg-primary-600 text-sm font-bold text-white transition hover:bg-primary-700">Tiến hành thanh toán</Link><div className="mt-4 flex items-start gap-2 text-xs leading-5 text-slate-500"><ShieldCheck className="mt-0.5 h-4 w-4 flex-none text-emerald" /> Giá và tồn kho sẽ được kiểm tra lại trước khi tạo đơn.</div></aside>
      </div>
    </div>
  )
}

function CartRow({ item, currency }: { item: CartItem; currency: string }) {
  const updateItem = useUpdateCartItem()
  const removeItem = useRemoveCartItem()
  const update = (quantity: number) => quantity >= 1 && updateItem.mutate({ itemId: item.id, data: { quantity } })
  return <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-4 p-4 sm:grid-cols-[96px_minmax(0,1fr)_auto] sm:items-center"><Link to={`/products/${item.productId}`} className="aspect-square overflow-hidden rounded-md bg-gray-100"><ProductImage src={item.imageUrl} alt={item.name} className="h-full w-full object-cover" /></Link><div className="min-w-0"><Link to={`/products/${item.productId}`} className="line-clamp-2 font-semibold text-ink hover:text-primary-600">{item.name}</Link>{item.sku && <p className="mt-1 text-xs text-gray-400">SKU: {item.sku}</p>}<p className="mt-2 font-bold text-primary-600">{formatCurrency(item.unitPrice, currency)}</p><div className="mt-3 flex items-center gap-2 sm:hidden"><Quantity value={item.quantity} pending={updateItem.isPending} update={update} /><RemoveButton pending={removeItem.isPending} remove={() => removeItem.mutate(item.id)} /></div></div><div className="col-span-2 hidden items-center gap-5 sm:col-span-1 sm:flex"><Quantity value={item.quantity} pending={updateItem.isPending} update={update} /><p className="w-28 text-right font-bold">{formatCurrency(item.subTotal, currency)}</p><RemoveButton pending={removeItem.isPending} remove={() => removeItem.mutate(item.id)} /></div></div>
}

function Quantity({ value, pending, update }: { value: number; pending: boolean; update: (value: number) => void }) { return <div className="flex overflow-hidden rounded-md border"><button type="button" title="Giảm" aria-label="Giảm số lượng" onClick={() => update(value - 1)} disabled={value <= 1 || pending} className="focus-ring flex h-9 w-9 items-center justify-center hover:bg-gray-100 disabled:opacity-40"><Minus className="h-4 w-4" /></button><span className="flex h-9 w-10 items-center justify-center border-x text-sm font-bold">{value}</span><button type="button" title="Tăng" aria-label="Tăng số lượng" onClick={() => update(value + 1)} disabled={pending} className="focus-ring flex h-9 w-9 items-center justify-center hover:bg-gray-100 disabled:opacity-40"><Plus className="h-4 w-4" /></button></div> }
function RemoveButton({ pending, remove }: { pending: boolean; remove: () => void }) { return <button type="button" title="Xóa" aria-label="Xóa sản phẩm" onClick={remove} disabled={pending} className="focus-ring flex h-9 w-9 items-center justify-center rounded-md text-gray-400 hover:bg-primary-50 hover:text-primary-600"><Trash2 className="h-4 w-4" /></button> }
function SummaryRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) { return <div className="flex justify-between gap-4"><span className="text-gray-500">{label}</span><span className={muted ? 'text-gray-500' : 'font-semibold'}>{value}</span></div> }
function groupByShop(items: CartItem[]) { return items.reduce<Record<string, CartItem[]>>((groups, item) => { const key = item.shopName || 'Sản phẩm chưa gắn cửa hàng'; groups[key] = [...(groups[key] ?? []), item]; return groups }, {}) }
function EmptyCart() { return <div className="market-container flex min-h-[60vh] flex-col items-center justify-center py-16 text-center"><span className="flex h-24 w-24 items-center justify-center rounded-full bg-primary-50 text-primary-500"><PackageOpen className="h-11 w-11" /></span><h1 className="mt-5 text-2xl font-black">Giỏ hàng đang trống</h1><p className="mt-2 max-w-sm text-sm leading-6 text-gray-500">Khám phá sản phẩm phù hợp và thêm vào giỏ để bắt đầu đơn hàng.</p><Link to="/products" className="mt-6"><Button><ShoppingBag className="mr-2 h-4 w-4" /> Khám phá sản phẩm</Button></Link></div> }

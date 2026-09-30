import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { addresses, notices, orders, reviews, vouchers } from './fixtures'
import type { Address, CartLine, DemoOrder, DemoState, Quote, Voucher } from './types'

const KEY = 'shopcart-buyer-demo-v1'
const initial = (): DemoState => ({ cart: [], wishlist: [], addresses, orders, reviews, notices, viewed: [], vouchers, profileName: 'Khách trải nghiệm' })
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
export const money = (amount: number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount)

export function quote(lines: Array<{ price: number; originalPrice?: number; quantity: number; sellerId: string }>, shippingMethod: 'standard' | 'express', voucher?: Voucher): Quote {
  const subtotal = lines.reduce((sum, line) => sum + line.price * line.quantity, 0)
  const productDiscount = lines.reduce((sum, line) => sum + Math.max(0, (line.originalPrice ?? line.price) - line.price) * line.quantity, 0)
  const shipping = [...new Set(lines.map(line => line.sellerId))].length * (shippingMethod === 'express' ? 50000 : 30000)
  let shippingDiscount = 0; let voucherMessage: string | undefined
  if (voucher) {
    if (subtotal < voucher.minOrder) voucherMessage = `Cần đơn từ ${money(voucher.minOrder)} để dùng ${voucher.code}`
    else if (voucher.kind === 'percent') shippingDiscount = 0
    else if (voucher.kind === 'fixed') shippingDiscount = 0
    else shippingDiscount = Math.min(voucher.value, shipping)
  }
  const voucherDiscount = voucher && subtotal >= voucher.minOrder && voucher.kind === 'percent' ? Math.min(Math.round(subtotal * voucher.value / 100), voucher.cap ?? Infinity) : voucher && subtotal >= voucher.minOrder && voucher.kind === 'fixed' ? voucher.value : 0
  return { subtotal, productDiscount: productDiscount + voucherDiscount, shipping, shippingDiscount, total: Math.max(0, subtotal - productDiscount - voucherDiscount + shipping - shippingDiscount), voucherMessage }
}

interface Store extends DemoState {
  storageWarning: boolean; addCart: (line: CartLine) => void; setCart: (cart: CartLine[]) => void; toggleWishlist: (id: string) => void; view: (id: string) => void
  saveAddress: (address: Address) => void; removeAddress: (id: string) => void; setProfileName: (name: string) => void; setNotices: (value: DemoState['notices']) => void
  placeOrder: (order: DemoOrder, boughtLines: Array<{ productId?: string; variantId?: string }>, source: 'cart' | 'buy-now') => void; reset: () => void
}
const StoreContext = createContext<Store | null>(null)

export function BuyerDemoProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DemoState>(() => {
    try { const raw = localStorage.getItem(KEY); if (!raw) return clone(initial()); const parsed = JSON.parse(raw); return parsed?.version === 1 ? parsed.state : clone(initial()) } catch { return clone(initial()) }
  })
  const [storageWarning, setStorageWarning] = useState(false)
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify({ version: 1, state })); setStorageWarning(false) } catch { setStorageWarning(true) } }, [state])
  const set = useCallback((patch: Partial<DemoState>) => setState(current => ({ ...current, ...patch })), [])
  const value = useMemo<Store>(() => ({ ...state, storageWarning,
    addCart: line => setState(current => { const found = current.cart.find(item => item.productId === line.productId && item.variantId === line.variantId); return { ...current, cart: found ? current.cart.map(item => item === found ? { ...item, quantity: item.quantity + line.quantity, selected: true } : item) : [...current.cart, line] } }),
    setCart: cart => set({ cart }), toggleWishlist: id => setState(current => ({ ...current, wishlist: current.wishlist.includes(id) ? current.wishlist.filter(x => x !== id) : [...current.wishlist, id] })),
    view: id => setState(current => ({ ...current, viewed: [id, ...current.viewed.filter(x => x !== id)].slice(0, 8) })),
    saveAddress: address => setState(current => ({ ...current, addresses: [...current.addresses.filter(a => a.id !== address.id), address].map(a => address.isDefault ? { ...a, isDefault: a.id === address.id } : a) })),
    removeAddress: id => setState(current => ({ ...current, addresses: current.addresses.filter(a => a.id !== id) })), setProfileName: profileName => set({ profileName }), setNotices: notices => set({ notices }),
    placeOrder: (order, boughtLines, source) => setState(current => ({ ...current, orders: [order, ...current.orders], cart: source === 'cart' ? current.cart.filter(line => !boughtLines.some(b => b.productId === line.productId && b.variantId === line.variantId)) : current.cart })),
    reset: () => { try { localStorage.removeItem(KEY) } catch { /* memory reset still works */ } setState(clone(initial())) },
  }), [state, storageWarning, set])
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}
export const useBuyerDemo = () => { const store = useContext(StoreContext); if (!store) throw new Error('Buyer demo provider missing'); return store }

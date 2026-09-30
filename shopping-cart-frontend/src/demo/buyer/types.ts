export type DemoCategory = 'phone' | 'computer' | 'audio' | 'fashion' | 'home' | 'book' | 'beauty' | 'sport'
export type OrderStatus = 'pending' | 'shipping' | 'delivered' | 'cancelled'

export interface Seller { id: string; name: string; logo: string; banner?: string; description: string; category: string }
export interface Variant { id: string; sku: string; label: string; options: Record<string, string>; price: number; originalPrice?: number; stock: number; image?: string }
export interface DemoProduct {
  id: string; slug: string; name: string; category: DemoCategory; brand: string; sellerId: string; description: string
  gallery: string[]; specifications: Array<[string, string]>; variants: Variant[]; badge?: 'Mới' | 'Giảm giá'; rating?: number; reviewCount?: number; soldCount?: number
}
export interface Voucher { id: string; code: string; kind: 'percent' | 'fixed' | 'shipping'; value: number; minOrder: number; cap?: number; status: 'available' | 'used' | 'expired' }
export interface CartLine { productId: string; variantId: string; quantity: number; selected: boolean }
export interface Address { id: string; fullName: string; phone: string; city: string; ward: string; detail: string; isDefault: boolean }
export interface DemoOrderItem { productId: string; variantId: string; name: string; variant: string; sellerId: string; quantity: number; unitPrice: number; image?: string }
export interface DemoOrder { id: string; items: DemoOrderItem[]; address: Address; status: OrderStatus; createdAt: string; subtotal: number; productDiscount: number; shipping: number; shippingDiscount: number; total: number; payment: string; shippingMethod: string; timeline: Array<{ label: string; at: string }> }
export interface Review { id: string; productId: string; orderItemId?: string; author: string; rating: number; content: string; date: string; images?: string[] }
export interface Notice { id: string; title: string; body: string; href?: string; read: boolean }
export interface Quote { subtotal: number; productDiscount: number; shipping: number; shippingDiscount: number; total: number; voucherMessage?: string }
export interface DemoState { cart: CartLine[]; wishlist: string[]; addresses: Address[]; orders: DemoOrder[]; reviews: Review[]; notices: Notice[]; viewed: string[]; vouchers: Voucher[]; profileName: string }

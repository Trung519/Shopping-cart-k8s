// Types for the fake marketplace API served by the BFF under /api/v2/mock.
// Everything here is demo data; the UI labels it as such.

export type MockPaymentMethod = 'momo' | 'vnpay' | 'zalopay' | 'cod'
export type MockPaymentStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED'

export interface MockConfig {
  enabled: boolean
  paymentDelaySeconds: number
  shipmentStepSeconds: number
  paymentMethods: MockPaymentMethod[]
}

export interface MockPayment {
  id: string
  orderId: string
  method: MockPaymentMethod
  amount: number
  status: MockPaymentStatus
  remainingSeconds: number
  expiresInSeconds: number
  createdAt: string
  paidAt?: string
  qr?: { payload: string; matrix: string[]; notice: string }
}

export type ShipmentStatus =
  | 'WAITING_PAYMENT'
  | 'PAYMENT_FAILED'
  | 'PLACED'
  | 'CONFIRMED'
  | 'PACKING'
  | 'HANDED_OVER'
  | 'IN_TRANSIT'
  | 'DELIVERED'

export interface Shipment {
  orderId: string
  status: ShipmentStatus
  carrier: string
  trackingCode: string
  currentStep: number
  stepSeconds: number
  steps: { key: string; label: string; at?: string; done: boolean }[]
}

export interface MockAddress {
  id: string
  fullName: string
  phone: string
  province: string
  district: string
  ward: string
  street: string
  isDefault: boolean
}
export type MockAddressInput = Omit<MockAddress, 'id'>

export interface Voucher {
  code: string
  title: string
  description: string
  kind: 'amount' | 'percent' | 'freeship'
  minSpend: number
  eligible: boolean
  reason?: string
}
export interface AppliedVoucher {
  code: string
  title: string
  discount: number
  shippingDiscount: number
}

export interface Review {
  id: string
  author: string
  rating: number
  comment: string
  createdAt: string
  verified: boolean
  mine: boolean
}
export interface ReviewList {
  summary: { average: number; count: number; distribution: Record<string, number> }
  items: Review[]
}

export interface ProductExtras {
  colors: { id: string; label: string; hex: string; priceDelta: number; stock: number }[]
  sizes: string[]
  gallery: { id: number; label: string }[]
}

export type ReturnReason = 'DEFECTIVE' | 'NOT_AS_DESCRIBED' | 'WRONG_ITEM' | 'CHANGED_MIND'
export type ReturnStatus = 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'REFUNDED'
export interface ReturnRequest {
  id: string
  orderRef: string
  buyer: string
  shop: string
  reason: ReturnReason
  note: string
  amount: number
  status: ReturnStatus
  createdAt: string
  updatedAt: string
}

export interface MockNotification {
  id: string
  type: 'order' | 'promo' | 'security'
  title: string
  text: string
  at: string
  unread: boolean
}

export type SellerOrderStatus = 'NEW' | 'CONFIRMED' | 'PACKED' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED'
export interface SellerOrder {
  id: string
  buyer: string
  city: string
  items: { name: string; qty: number; price: number }[]
  total: number
  status: SellerOrderStatus
  createdAt: string
}

export interface InventoryItem {
  sku: string
  name: string
  stock: number
  reserved: number
  available: number
  lowThreshold: number
  low: boolean
}

export interface Promotion {
  id: string
  name: string
  kind: 'percent' | 'amount' | 'freeship'
  value: number
  minSpend: number
  status: 'ACTIVE' | 'PAUSED'
  used: number
}

export interface ChatThread {
  id: string
  buyer: string
  product: string
  unread: boolean
  messages: { from: 'buyer' | 'seller'; text: string; at: string }[]
}

export interface Payout {
  id: string
  amount: number
  status: 'PROCESSING' | 'COMPLETED'
  createdAt: string
}
export interface SellerFinance {
  availableBalance: number
  pendingBalance: number
  commissionRate: number
  transactions: { id: string; type: string; ref: string; amount: number; at: string }[]
  payouts: Payout[]
}

export interface SellerSettings {
  shopName: string
  description: string
  phone: string
  returnDays: number
  vacationMode: boolean
  notifyOrders: boolean
  notifyMessages: boolean
}

export interface SellerDashboard {
  kpis: { revenue7d: number; orders7d: number; views7d: number; conversion: number; rating: number }
  series: { date: string; revenue: number; orders: number }[]
  todo: { newOrders: number; lowStock: number; openReturns: number }
  topProducts: { name: string; sold: number; revenue: number }[]
}

export interface Settlement {
  id: string
  shop: string
  period: string
  gross: number
  commission: number
  net: number
  status: 'PENDING' | 'PAID'
  paidAt?: string
}
export interface AdminFinance {
  totals: { gross: number; commission: number; pendingPayout: number }
  settlements: Settlement[]
}

export interface AdminAnalytics {
  range: number
  kpis: { gmv: number; orders: number; aov: number; conversion: number; newSellers: number }
  series: { date: string; gmv: number; orders: number }[]
  funnel: { step: string; value: number }[]
  categories: { name: string; share: number; gmv: number }[]
}

export interface AuditEntry {
  id: string
  actor: string
  action: string
  target: string
  at: string
}

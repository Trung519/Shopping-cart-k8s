import api from './api'
import type {
  AdminAnalytics, AdminFinance, AppliedVoucher, AuditEntry, ChatThread, InventoryItem, MockAddress, MockAddressInput,
  MockConfig, MockNotification, MockPayment, MockPaymentMethod, Payout, ProductExtras, Promotion, ReturnReason,
  ReturnRequest, ReturnStatus, Review, ReviewList, SellerDashboard, SellerFinance, SellerOrder, SellerOrderStatus,
  SellerSettings, Settlement, Shipment, Voucher,
} from '@/types/mock'

export const MOCK_BASE = '/api/v2/mock'

interface Envelope<T> { success: boolean; data: T; mock: true }

const get = async <T>(path: string, params?: Record<string, string | number>) =>
  (await api.get<Envelope<T>>(`${MOCK_BASE}${path}`, { params })).data.data
const post = async <T>(path: string, body?: unknown) => (await api.post<Envelope<T>>(`${MOCK_BASE}${path}`, body)).data.data
const put = async <T>(path: string, body?: unknown) => (await api.put<Envelope<T>>(`${MOCK_BASE}${path}`, body)).data.data
const patch = async <T>(path: string, body?: unknown) => (await api.patch<Envelope<T>>(`${MOCK_BASE}${path}`, body)).data.data
const del = async <T>(path: string) => (await api.delete<Envelope<T>>(`${MOCK_BASE}${path}`)).data.data

export const mockService = {
  // Resolves to null when the BFF does not serve the mock API (feature switched off).
  getConfig: async (): Promise<MockConfig | null> => {
    try {
      return await get<MockConfig>('/config')
    } catch {
      return null
    }
  },

  createPayment: (input: { orderId: string; method: MockPaymentMethod; amount: number }) => post<MockPayment>('/payments', input),
  getPayment: (id: string) => get<MockPayment>(`/payments/${id}`),
  cancelPayment: (id: string) => post<MockPayment>(`/payments/${id}/cancel`),
  getShipment: (orderId: string) => get<Shipment>(`/shipments/${encodeURIComponent(orderId)}`),

  listAddresses: () => get<MockAddress[]>('/addresses'),
  createAddress: (input: MockAddressInput) => post<MockAddress>('/addresses', input),
  updateAddress: (id: string, input: MockAddressInput) => put<MockAddress>(`/addresses/${id}`, input),
  deleteAddress: (id: string) => del<MockAddress[]>(`/addresses/${id}`),
  setDefaultAddress: (id: string) => post<MockAddress[]>(`/addresses/${id}/default`),

  listVouchers: (subtotal: number) => get<Voucher[]>('/vouchers', { subtotal }),
  applyVoucher: (code: string, subtotal: number) => post<AppliedVoucher>('/vouchers/apply', { code, subtotal }),

  listReviews: (productId: string) => get<ReviewList>(`/products/${encodeURIComponent(productId)}/reviews`),
  createReview: (productId: string, input: { rating: number; comment: string }) => post<Review>(`/products/${encodeURIComponent(productId)}/reviews`, input),
  getExtras: (productId: string) => get<ProductExtras>(`/products/${encodeURIComponent(productId)}/extras`),

  listReturns: () => get<ReturnRequest[]>('/returns'),
  createReturn: (input: { orderId: string; reason: ReturnReason; note: string; amount: number }) => post<ReturnRequest>('/returns', input),

  listNotifications: () => get<{ items: MockNotification[]; unread: number }>('/notifications'),
  readNotifications: () => post<{ unread: number }>('/notifications/read'),

  sellerDashboard: () => get<SellerDashboard>('/seller/dashboard'),
  sellerOrders: (status?: string) => get<{ items: SellerOrder[]; counts: Record<SellerOrderStatus, number> }>('/seller/orders', status ? { status } : undefined),
  sellerOrderAction: (id: string, action: 'confirm' | 'pack' | 'ship' | 'cancel') => patch<SellerOrder>(`/seller/orders/${id}`, { action }),
  sellerInventory: () => get<InventoryItem[]>('/seller/inventory'),
  sellerSetStock: (sku: string, stock: number) => patch<InventoryItem[]>(`/seller/inventory/${encodeURIComponent(sku)}`, { stock }),
  sellerPromotions: () => get<Promotion[]>('/seller/promotions'),
  sellerCreatePromotion: (input: { name: string; kind: Promotion['kind']; value: number; minSpend: number }) => post<Promotion>('/seller/promotions', input),
  sellerTogglePromotion: (id: string) => post<Promotion>(`/seller/promotions/${id}/toggle`),
  sellerMessages: () => get<ChatThread[]>('/seller/messages'),
  sellerReply: (id: string, text: string) => post<{ from: 'seller'; text: string; at: string }>(`/seller/messages/${id}`, { text }),
  sellerFinance: () => get<SellerFinance>('/seller/finance'),
  sellerPayout: (amount: number) => post<Payout>('/seller/payouts', { amount }),
  sellerSettings: () => get<SellerSettings>('/seller/settings'),
  sellerSaveSettings: (input: SellerSettings) => put<SellerSettings>('/seller/settings', input),

  adminReturns: (status?: string) => get<{ items: ReturnRequest[]; counts: Record<ReturnStatus, number> }>('/admin/returns', status ? { status } : undefined),
  adminReturnAction: (id: string, action: 'approve' | 'reject' | 'refund') => patch<ReturnRequest>(`/admin/returns/${id}`, { action }),
  adminFinance: () => get<AdminFinance>('/admin/finance'),
  adminApproveSettlement: (id: string) => post<Settlement>(`/admin/finance/settlements/${id}/approve`),
  adminAnalytics: (range: '7d' | '30d' | '90d') => get<AdminAnalytics>('/admin/analytics', { range }),
  adminAudit: (q?: string) => get<AuditEntry[]>('/admin/audit', q ? { q } : undefined),
}

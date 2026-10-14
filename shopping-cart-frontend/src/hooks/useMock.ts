import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useAppAuth } from '@/contexts/AuthContext'
import { mockService } from '@/services/mockService'
import type { ReturnReason, SellerSettings } from '@/types/mock'

const root = 'mock'

/** Whether the BFF serves the mock API. The config call is public and cached for the session. */
export function useMockConfig() {
  return useQuery({ queryKey: [root, 'config'], queryFn: mockService.getConfig, staleTime: Infinity, retry: false })
}

export function useMockEnabled() {
  const query = useMockConfig()
  return { enabled: Boolean(query.data?.enabled), loading: query.isLoading, config: query.data ?? null }
}

interface MockQueryOptions { enabled?: boolean; refetchInterval?: number | false }

function useMockQuery<T>(key: unknown[], fn: () => Promise<T>, options: MockQueryOptions = {}) {
  const auth = useAppAuth()
  const { enabled } = useMockEnabled()
  return useQuery({
    queryKey: [root, ...key],
    queryFn: fn,
    enabled: enabled && auth.isAuthenticated && (options.enabled ?? true),
    refetchInterval: options.refetchInterval,
    retry: false,
  })
}

function useMockMutation<TVars, TData>(fn: (vars: TVars) => Promise<TData>, invalidate: QueryKey[] = []) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      invalidate.forEach((key) => queryClient.invalidateQueries({ queryKey: [root, ...key] }))
    },
  })
}

// ---- buyer ------------------------------------------------------------------

export function useCreateMockPayment() {
  return useMutation({ mutationFn: mockService.createPayment })
}

/** Polls once a second while the payment is PENDING, then stops. */
export function useMockPayment(id: string | null) {
  const auth = useAppAuth()
  const { enabled } = useMockEnabled()
  return useQuery({
    queryKey: [root, 'payment', id],
    queryFn: () => mockService.getPayment(id as string),
    enabled: enabled && auth.isAuthenticated && Boolean(id),
    refetchInterval: (query) => (query.state.data?.status === 'PENDING' ? 1000 : false),
    retry: false,
  })
}

export function useCancelMockPayment() {
  return useMockMutation(mockService.cancelPayment, [['payment']])
}

export function useShipment(orderId: string) {
  const auth = useAppAuth()
  const { enabled } = useMockEnabled()
  return useQuery({
    queryKey: [root, 'shipment', orderId],
    queryFn: () => mockService.getShipment(orderId),
    enabled: enabled && auth.isAuthenticated && Boolean(orderId),
    refetchInterval: (query) => (query.state.data && ['DELIVERED', 'PAYMENT_FAILED'].includes(query.state.data.status) ? false : 2000),
    retry: false,
  })
}

export const useAddresses = () => useMockQuery(['addresses'], mockService.listAddresses)
export const useCreateAddress = () => useMockMutation(mockService.createAddress, [['addresses']])
export const useUpdateAddress = () => useMockMutation(({ id, input }: { id: string; input: Parameters<typeof mockService.updateAddress>[1] }) => mockService.updateAddress(id, input), [['addresses']])
export const useDeleteAddress = () => useMockMutation(mockService.deleteAddress, [['addresses']])
export const useSetDefaultAddress = () => useMockMutation(mockService.setDefaultAddress, [['addresses']])

export const useVouchers = (subtotal: number) => useMockQuery(['vouchers', subtotal], () => mockService.listVouchers(subtotal))
export const useApplyVoucher = () => useMutation({ mutationFn: ({ code, subtotal }: { code: string; subtotal: number }) => mockService.applyVoucher(code, subtotal) })

export const useReviews = (productId: string) => useMockQuery(['reviews', productId], () => mockService.listReviews(productId), { enabled: Boolean(productId) })
export const useCreateReview = (productId: string) => useMockMutation((input: { rating: number; comment: string }) => mockService.createReview(productId, input), [['reviews', productId]])
export const useProductExtras = (productId: string) => useMockQuery(['extras', productId], () => mockService.getExtras(productId), { enabled: Boolean(productId) })

export const useMyReturns = () => useMockQuery(['returns'], mockService.listReturns)
export const useCreateReturn = () =>
  useMockMutation((input: { orderId: string; reason: ReturnReason; note: string; amount: number }) => mockService.createReturn(input), [['returns'], ['admin-returns'], ['notifications']])

export const useMockNotifications = () => useMockQuery(['notifications'], mockService.listNotifications)
export const useReadNotifications = () => useMockMutation(() => mockService.readNotifications(), [['notifications']])

// ---- seller ------------------------------------------------------------------

export const useSellerDashboard = () => useMockQuery(['seller-dashboard'], mockService.sellerDashboard)
export const useSellerOrders = (status?: string) => useMockQuery(['seller-orders', status ?? 'all'], () => mockService.sellerOrders(status))
export const useSellerOrderAction = () =>
  useMockMutation(({ id, action }: { id: string; action: Parameters<typeof mockService.sellerOrderAction>[1] }) => mockService.sellerOrderAction(id, action), [['seller-orders'], ['seller-dashboard']])
export const useSellerInventory = () => useMockQuery(['seller-inventory'], mockService.sellerInventory)
export const useSellerSetStock = () => useMockMutation(({ sku, stock }: { sku: string; stock: number }) => mockService.sellerSetStock(sku, stock), [['seller-inventory'], ['seller-dashboard']])
export const useSellerPromotions = () => useMockQuery(['seller-promotions'], mockService.sellerPromotions)
export const useSellerCreatePromotion = () => useMockMutation(mockService.sellerCreatePromotion, [['seller-promotions']])
export const useSellerTogglePromotion = () => useMockMutation(mockService.sellerTogglePromotion, [['seller-promotions']])
export const useSellerMessages = () => useMockQuery(['seller-messages'], mockService.sellerMessages, { refetchInterval: 4000 })
export const useSellerReply = () => useMockMutation(({ id, text }: { id: string; text: string }) => mockService.sellerReply(id, text), [['seller-messages']])
export const useSellerFinance = () => useMockQuery(['seller-finance'], mockService.sellerFinance, { refetchInterval: 4000 })
export const useSellerPayout = () => useMockMutation(mockService.sellerPayout, [['seller-finance']])
export const useSellerSettings = () => useMockQuery(['seller-settings'], mockService.sellerSettings)
export const useSellerSaveSettings = () => useMockMutation((input: SellerSettings) => mockService.sellerSaveSettings(input), [['seller-settings']])

// ---- admin ------------------------------------------------------------------

export const useAdminReturns = (status?: string) => useMockQuery(['admin-returns', status ?? 'all'], () => mockService.adminReturns(status))
export const useAdminReturnAction = () =>
  useMockMutation(({ id, action }: { id: string; action: Parameters<typeof mockService.adminReturnAction>[1] }) => mockService.adminReturnAction(id, action), [['admin-returns'], ['admin-audit']])
export const useAdminFinance = () => useMockQuery(['admin-finance'], mockService.adminFinance)
export const useAdminApproveSettlement = () => useMockMutation(mockService.adminApproveSettlement, [['admin-finance'], ['admin-audit']])
export const useAdminAnalytics = (range: '7d' | '30d' | '90d') => useMockQuery(['admin-analytics', range], () => mockService.adminAnalytics(range))
export const useAdminAudit = (q?: string) => useMockQuery(['admin-audit', q ?? ''], () => mockService.adminAudit(q))

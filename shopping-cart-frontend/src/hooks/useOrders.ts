import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAppAuth } from '@/contexts/AuthContext'
import { orderService, type GetOrdersParams } from '@/services/orderService'
import type { UpdateOrderStatusInput } from '@/services/orderService'

export function useOrders(params: GetOrdersParams = {}) {
  const auth = useAppAuth()

  return useQuery({
    queryKey: ['orders', auth.user?.id, params],
    queryFn: () =>
      orderService.getOrders({
        ...params,
        customerId: auth.user?.id,
      }),
    enabled: auth.isAuthenticated && !!auth.user?.id,
  })
}

export function useOrder(id: string) {
  const auth = useAppAuth()

  return useQuery({
    queryKey: ['order', id],
    queryFn: () => orderService.getOrderById(id),
    enabled: auth.isAuthenticated && !!id,
  })
}

export function useCancelOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => orderService.cancelOrder(id),
    onSuccess: (order) => {
      queryClient.setQueryData(['order', order.id], order)
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

export function useAdminOrders(status?: string) {
  const auth = useAppAuth()
  return useQuery({
    queryKey: ['admin-orders', status],
    queryFn: () => orderService.getAdminOrders(status),
    enabled: auth.isAuthenticated && auth.isAdmin,
  })
}

export function useUpdateOrderStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: UpdateOrderStatusInput }) =>
      orderService.updateOrderStatus(id, input),
    onSuccess: (order) => {
      queryClient.setQueryData(['order', order.id], order)
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['admin-orders'] })
    },
  })
}

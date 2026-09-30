import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { cartService } from '@/services/cartService'
import { useAppAuth } from '@/contexts/AuthContext'
import { useCartStore } from '@/stores/cartStore'
import type { AddToCartRequest, CheckoutAddress, UpdateCartItemRequest } from '@/types'

export function useCart() {
  const auth = useAppAuth()
  const setCart = useCartStore((state) => state.setCart)

  return useQuery({
    queryKey: ['cart'],
    queryFn: async () => {
      const cart = await cartService.getCart()
      setCart(cart)
      return cart
    },
    enabled: auth.isAuthenticated,
  })
}

export function useAddToCart() {
  const queryClient = useQueryClient()
  const setCart = useCartStore((state) => state.setCart)

  return useMutation({
    mutationFn: (item: AddToCartRequest) => cartService.addItem(item),
    onSuccess: (cart) => {
      setCart(cart)
      queryClient.setQueryData(['cart'], cart)
    },
  })
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient()
  const setCart = useCartStore((state) => state.setCart)

  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: UpdateCartItemRequest }) =>
      cartService.updateItem(itemId, data),
    onSuccess: (cart) => {
      setCart(cart)
      queryClient.setQueryData(['cart'], cart)
    },
  })
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient()
  const setCart = useCartStore((state) => state.setCart)

  return useMutation({
    mutationFn: (itemId: string) => cartService.removeItem(itemId),
    onSuccess: (cart) => {
      setCart(cart)
      queryClient.setQueryData(['cart'], cart)
    },
  })
}

export function useClearCart() {
  const queryClient = useQueryClient()
  const clearCart = useCartStore((state) => state.clearCart)

  return useMutation({
    mutationFn: () => cartService.clearCart(),
    onSuccess: () => {
      clearCart()
      queryClient.setQueryData(['cart'], null)
    },
  })
}

export function useCheckout() {
  const queryClient = useQueryClient()
  const clearCart = useCartStore((state) => state.clearCart)

  return useMutation({
    mutationFn: (address: CheckoutAddress) => cartService.checkout(address),
    onSuccess: () => {
      clearCart()
      queryClient.invalidateQueries({ queryKey: ['cart'] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

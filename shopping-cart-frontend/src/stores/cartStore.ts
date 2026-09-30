import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Cart } from '@/types'

interface CartState {
  cart: Cart | null
  itemCount: number
  isLoading: boolean
  error: string | null

  // Actions
  setCart: (cart: Cart | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  updateItemCount: () => void
  clearCart: () => void
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      cart: null,
      itemCount: 0,
      isLoading: false,
      error: null,

      setCart: (cart) => {
        set({ cart })
        get().updateItemCount()
      },

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      updateItemCount: () => {
        const cart = get().cart
        const count = cart?.items.reduce((sum, item) => sum + item.quantity, 0) || 0
        set({ itemCount: count })
      },

      clearCart: () => set({ cart: null, itemCount: 0 }),
    }),
    {
      name: 'cart-storage',
      partialize: (state) => ({ itemCount: state.itemCount }),
    }
  )
)

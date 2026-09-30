import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore } from './cartStore'
import type { Cart } from '@/types'

describe('cartStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useCartStore.setState({ cart: null, itemCount: 0, isLoading: false, error: null })
  })

  it('initializes with empty state', () => {
    const state = useCartStore.getState()
    expect(state.cart).toBeNull()
    expect(state.itemCount).toBe(0)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('sets cart and updates item count', () => {
    const mockCart: Cart = {
      id: '1',
      customerId: 'customer-1',
      items: [
        { id: '1', productId: 'p1', name: 'Product 1', quantity: 2, unitPrice: 10, subTotal: 20 },
        { id: '2', productId: 'p2', name: 'Product 2', quantity: 3, unitPrice: 15, subTotal: 45 },
      ],
      totalAmount: 65,
      currency: 'USD',
      createdAt: '2024-01-01',
      updatedAt: '2024-01-01',
      expiresAt: '2024-01-08',
    }

    useCartStore.getState().setCart(mockCart)

    const state = useCartStore.getState()
    expect(state.cart).toEqual(mockCart)
    expect(state.itemCount).toBe(5) // 2 + 3
  })

  it('clears cart', () => {
    const mockCart: Cart = {
      id: '1',
      customerId: 'customer-1',
      items: [
        { id: '1', productId: 'p1', name: 'Product 1', quantity: 2, unitPrice: 10, subTotal: 20 },
      ],
      totalAmount: 20,
      currency: 'USD',
      createdAt: '2024-01-01',
      updatedAt: '2024-01-01',
      expiresAt: '2024-01-08',
    }

    useCartStore.getState().setCart(mockCart)
    expect(useCartStore.getState().cart).not.toBeNull()

    useCartStore.getState().clearCart()
    expect(useCartStore.getState().cart).toBeNull()
    expect(useCartStore.getState().itemCount).toBe(0)
  })

  it('sets loading state', () => {
    useCartStore.getState().setLoading(true)
    expect(useCartStore.getState().isLoading).toBe(true)

    useCartStore.getState().setLoading(false)
    expect(useCartStore.getState().isLoading).toBe(false)
  })

  it('sets error state', () => {
    useCartStore.getState().setError('Something went wrong')
    expect(useCartStore.getState().error).toBe('Something went wrong')

    useCartStore.getState().setError(null)
    expect(useCartStore.getState().error).toBeNull()
  })
})

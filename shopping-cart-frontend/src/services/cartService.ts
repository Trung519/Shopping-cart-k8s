import api from './api'
import { ENDPOINTS } from '@/config/api'
import type { Cart, AddToCartRequest, CheckoutAddress, UpdateCartItemRequest } from '@/types'

type CartApiResponse = Cart | { success: boolean; data?: Cart }

function unwrapCartResponse(payload: CartApiResponse): Cart {
  if ('success' in payload) {
    if (!payload.data) {
      throw new Error('Cart response did not include cart data')
    }

    return payload.data
  }

  return payload
}

export const cartService = {
  async getCart(): Promise<Cart> {
    const response = await api.get<CartApiResponse>(ENDPOINTS.CART)
    return unwrapCartResponse(response.data)
  },

  async addItem(item: AddToCartRequest): Promise<Cart> {
    const response = await api.post<CartApiResponse>(ENDPOINTS.CART_ITEMS, item)
    return unwrapCartResponse(response.data)
  },

  async updateItem(itemId: string, data: UpdateCartItemRequest): Promise<Cart> {
    const response = await api.put<CartApiResponse>(ENDPOINTS.CART_ITEM_BY_ID(itemId), data)
    return unwrapCartResponse(response.data)
  },

  async removeItem(itemId: string): Promise<Cart> {
    const response = await api.delete<CartApiResponse>(ENDPOINTS.CART_ITEM_BY_ID(itemId))
    return unwrapCartResponse(response.data)
  },

  async clearCart(): Promise<void> {
    await api.delete(ENDPOINTS.CART)
  },

  async checkout(address: CheckoutAddress): Promise<{ orderId?: string }> {
    const response = await api.post<
      | { orderId?: string }
      | { success: boolean; data?: { orderId?: string; message?: string } }
    >(ENDPOINTS.CART_CHECKOUT, {
      shippingAddress: {
        street: `${address.street}, ${address.ward}`,
        city: address.province ?? address.city,
        state: address.district,
        postalCode: address.postalCode || '700000',
        country: address.country || 'VN',
      },
    })

    if ('success' in response.data) {
      return { orderId: response.data.data?.orderId }
    }

    return response.data
  },
}

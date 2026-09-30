import api from './api'
import { ENDPOINTS } from '@/config/api'
import type { Order, PaginatedResponse } from '@/types'

export interface GetOrdersParams {
  page?: number
  pageSize?: number
  status?: string
  customerId?: string
}

export interface UpdateOrderStatusInput {
  status: Order['status']
  paymentId?: string
  paymentMethod?: string
  trackingNumber?: string
  carrier?: string
  estimatedDelivery?: string
}

interface OrderApiItem {
  id: string
  productId: string
  productName?: string
  name?: string
  quantity: number
  unitPrice: number | string
  subtotal?: number | string
  subTotal?: number | string
}

interface OrderApiResponse {
  id: string
  customerId: string
  status: Order['status']
  items: OrderApiItem[]
  totalAmount: number | string
  currency: string
  shippingAddress?: Order['shippingAddress']
  createdAt: string
  updatedAt: string
}

function normalizeOrderItem(item: OrderApiItem | Order['items'][number]): Order['items'][number] {
  return {
    id: item.id,
    productId: item.productId,
    name: 'productName' in item ? item.productName ?? item.name ?? 'Unnamed item' : item.name ?? 'Unnamed item',
    quantity: item.quantity,
    unitPrice: Number(item.unitPrice),
    subTotal: Number('subtotal' in item ? item.subtotal ?? item.subTotal ?? 0 : item.subTotal),
  }
}

function normalizeOrder(payload: Order | OrderApiResponse): Order {
  return {
    id: payload.id,
    customerId: payload.customerId,
    status: payload.status,
    items: payload.items.map(normalizeOrderItem),
    totalAmount: Number(payload.totalAmount),
    currency: payload.currency,
    shippingAddress: payload.shippingAddress,
    createdAt: payload.createdAt,
    updatedAt: payload.updatedAt,
  }
}

export const orderService = {
  async getOrders(params: GetOrdersParams = {}): Promise<PaginatedResponse<Order>> {
    const { page = 1, pageSize = 10, status, customerId } = params
    const queryParams = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    })

    if (status) queryParams.append('status', status)
    if (customerId) queryParams.append('customerId', customerId)

    const response = await api.get<PaginatedResponse<Order> | OrderApiResponse[]>(
      `${ENDPOINTS.ORDERS}?${queryParams}`
    )
    const payload = response.data

    // Backward compatibility: order service may return either a plain list or paginated payload.
    if (Array.isArray(payload)) {
      return {
        data: payload.map(normalizeOrder),
        page,
        pageSize,
        totalItems: payload.length,
        totalPages: 1,
      }
    }

    return payload
  },

  async getOrderById(id: string): Promise<Order> {
    const response = await api.get<OrderApiResponse | Order>(ENDPOINTS.ORDER_BY_ID(id))
    return normalizeOrder(response.data)
  },

  async getAdminOrders(status?: string): Promise<Order[]> {
    const query = status ? `?status=${encodeURIComponent(status)}` : ''
    const response = await api.get<OrderApiResponse[]>(`${ENDPOINTS.ORDERS}/admin${query}`)
    return response.data.map(normalizeOrder)
  },

  async updateOrderStatus(id: string, input: UpdateOrderStatusInput): Promise<Order> {
    const response = await api.patch<OrderApiResponse>(`${ENDPOINTS.ORDER_BY_ID(id)}/status`, input)
    return normalizeOrder(response.data)
  },

  async cancelOrder(id: string): Promise<Order> {
    const response = await api.post<OrderApiResponse | Order>(`${ENDPOINTS.ORDER_BY_ID(id)}/cancel`, {
      reason: 'Cancelled by user',
    })
    return normalizeOrder(response.data)
  },
}

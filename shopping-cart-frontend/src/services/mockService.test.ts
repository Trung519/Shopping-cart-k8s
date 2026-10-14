import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))

import api from './api'
import { mockService, MOCK_BASE } from './mockService'

const http = vi.mocked(api, true)

describe('mockService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('unwraps the { success, data, mock } envelope', async () => {
    http.get.mockResolvedValue({ data: { success: true, mock: true, data: { enabled: true, paymentDelaySeconds: 5 } } })
    await expect(mockService.getConfig()).resolves.toEqual({ enabled: true, paymentDelaySeconds: 5 })
    expect(http.get).toHaveBeenCalledWith(`${MOCK_BASE}/config`, { params: undefined })
  })

  it('treats a failing config call as "mock not available"', async () => {
    http.get.mockRejectedValue(new Error('API không tồn tại'))
    await expect(mockService.getConfig()).resolves.toBeNull()
  })

  it('posts payments to the mock route and returns the payment', async () => {
    http.post.mockResolvedValue({ data: { success: true, mock: true, data: { id: 'mpay_1', status: 'PENDING' } } })
    const payment = await mockService.createPayment({ orderId: 'o1', method: 'momo', amount: 1000 })
    expect(payment.id).toBe('mpay_1')
    expect(http.post).toHaveBeenCalledWith(`${MOCK_BASE}/payments`, { orderId: 'o1', method: 'momo', amount: 1000 })
  })

  it('encodes path segments that come from ids', async () => {
    http.get.mockResolvedValue({ data: { success: true, mock: true, data: {} } })
    await mockService.getShipment('a/b c')
    expect(http.get).toHaveBeenCalledWith(`${MOCK_BASE}/shipments/a%2Fb%20c`, { params: undefined })
  })

  it('passes optional filters as query params only when given', async () => {
    http.get.mockResolvedValue({ data: { success: true, mock: true, data: { items: [], counts: {} } } })
    await mockService.sellerOrders()
    await mockService.sellerOrders('NEW')
    expect(http.get).toHaveBeenNthCalledWith(1, `${MOCK_BASE}/seller/orders`, { params: undefined })
    expect(http.get).toHaveBeenNthCalledWith(2, `${MOCK_BASE}/seller/orders`, { params: { status: 'NEW' } })
  })

  it('propagates API errors so the UI can show the server message', async () => {
    http.post.mockRejectedValue(new Error('Mã đã hết hạn'))
    await expect(mockService.applyVoucher('HETHAN', 1)).rejects.toThrow('Mã đã hết hạn')
  })
})

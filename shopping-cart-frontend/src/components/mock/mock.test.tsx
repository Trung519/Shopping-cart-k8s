import type { ReactNode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MockPayment, Shipment } from '@/types/mock'

const service = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getPayment: vi.fn(),
  cancelPayment: vi.fn(),
  getShipment: vi.fn(),
  applyVoucher: vi.fn(),
  listVouchers: vi.fn(),
}))

vi.mock('@/services/mockService', () => ({ MOCK_BASE: '/api/v2/mock', mockService: service }))
vi.mock('@/contexts/AuthContext', () => ({ useAppAuth: () => ({ isAuthenticated: true, user: { id: 'u1' } }) }))

import PaymentQrModal, { QrCode } from './PaymentQrModal'
import ShipmentTimeline from './ShipmentTimeline'
import VoucherBox from './VoucherBox'
import { MockPage, StatusBadge } from './MockPrimitives'
import { useVoucherStore } from '@/stores/voucherStore'

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>)
}

const payment = (over: Partial<MockPayment> = {}): MockPayment => ({
  id: 'mpay_1', orderId: 'o1', method: 'momo', amount: 1290000, status: 'PENDING', remainingSeconds: 5, expiresInSeconds: 5, createdAt: '2026-10-14T09:00:00Z',
  qr: { payload: 'MOCK|MOMO|mpay_1|1290000', matrix: ['101', '010', '101'], notice: 'Mã QR giả lập, không quét được' }, ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  service.getConfig.mockResolvedValue({ enabled: true, paymentDelaySeconds: 5, shipmentStepSeconds: 10, paymentMethods: ['momo'] })
  useVoucherStore.setState({ applied: null })
})

describe('QrCode', () => {
  it('draws one square per "1" cell and is labelled for screen readers', () => {
    const { container } = render(<QrCode matrix={['101', '010', '101']} label="QR giả lập" />)
    expect(screen.getByRole('img', { name: 'QR giả lập' })).toBeInTheDocument()
    expect(container.querySelectorAll('rect')).toHaveLength(5)
  })
})

describe('PaymentQrModal', () => {
  it('shows the fake QR, the notice and the countdown while PENDING', async () => {
    service.getPayment.mockResolvedValue(payment())
    wrap(<PaymentQrModal paymentId="mpay_1" initial={payment()} onSuccess={vi.fn()} onClose={vi.fn()} onRetry={vi.fn()} />)
    expect(await screen.findByText(/Mã QR giả lập, không quét được/)).toBeInTheDocument()
    expect(screen.getByText(/còn 5s/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('moves to success and calls onSuccess once the BFF reports SUCCESS', async () => {
    const onSuccess = vi.fn()
    service.getPayment.mockResolvedValue(payment({ status: 'SUCCESS', remainingSeconds: 0, paidAt: '2026-10-14T09:00:05Z' }))
    wrap(<PaymentQrModal paymentId="mpay_1" initial={payment()} onSuccess={onSuccess} onClose={vi.fn()} onRetry={vi.fn()} />)
    expect(await screen.findByText('Thanh toán thành công')).toBeInTheDocument()
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1), { timeout: 3000 })
  })

  it('offers retry and a link to the order when the payment fails', async () => {
    const onRetry = vi.fn()
    const onSuccess = vi.fn()
    service.getPayment.mockResolvedValue(payment({ status: 'FAILED', remainingSeconds: 0 }))
    wrap(<PaymentQrModal paymentId="mpay_1" initial={payment()} onSuccess={onSuccess} onClose={vi.fn()} onRetry={onRetry} />)
    expect(await screen.findByText('Thanh toán thất bại')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(onRetry).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Xem đơn hàng' }))
    expect(onSuccess).toHaveBeenCalled()
  })

  it('cancels a pending payment when the user backs out', async () => {
    const onClose = vi.fn()
    service.getPayment.mockResolvedValue(payment())
    service.cancelPayment.mockResolvedValue(payment({ status: 'CANCELLED' }))
    wrap(<PaymentQrModal paymentId="mpay_1" initial={payment()} onSuccess={vi.fn()} onClose={onClose} onRetry={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Huỷ thanh toán' }))
    await waitFor(() => expect(service.cancelPayment).toHaveBeenCalled())
    expect(service.cancelPayment.mock.calls[0][0]).toBe('mpay_1')
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})

describe('ShipmentTimeline', () => {
  const shipment = (over: Partial<Shipment>): Shipment => ({
    orderId: 'o1', status: 'PACKING', carrier: 'GHN Express', trackingCode: 'MOCK123456789', currentStep: 2, stepSeconds: 10,
    steps: ['Đã đặt hàng', 'Đã xác nhận', 'Đang đóng gói', 'Đã bàn giao', 'Đang vận chuyển', 'Đã giao thành công'].map((label, i) => ({ key: String(i), label, done: i <= 2, at: i <= 2 ? '2026-10-14T09:00:00Z' : undefined })), ...over,
  })

  it('lists every step with the carrier and tracking code', async () => {
    service.getShipment.mockResolvedValue(shipment({}))
    wrap(<ShipmentTimeline orderId="o1" />)
    expect(await screen.findByText('Đang đóng gói')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(6)
    expect(screen.getByText(/GHN Express/)).toBeInTheDocument()
    expect(screen.getByText('MOCK123456789')).toBeInTheDocument()
  })

  it('explains why nothing moves while the payment is unpaid', async () => {
    service.getShipment.mockResolvedValue(shipment({ status: 'WAITING_PAYMENT', currentStep: 0 }))
    wrap(<ShipmentTimeline orderId="o1" />)
    expect(await screen.findByText(/Đang chờ thanh toán/)).toBeInTheDocument()
  })

  it('renders nothing when the mock API is not available', async () => {
    service.getShipment.mockRejectedValue(new Error('API không tồn tại'))
    const { container } = wrap(<ShipmentTimeline orderId="o1" />)
    await waitFor(() => expect(service.getConfig).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})

describe('VoucherBox', () => {
  it('is hidden entirely when the mock API is off', async () => {
    service.getConfig.mockResolvedValue(null)
    const { container } = wrap(<VoucherBox subtotal={500000} />)
    await waitFor(() => expect(service.getConfig).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('applies a code and shows it as applied', async () => {
    service.listVouchers.mockResolvedValue([{ code: 'SALE50', title: 'Giảm 50.000₫', description: '', kind: 'amount', minSpend: 300000, eligible: true }])
    service.applyVoucher.mockResolvedValue({ code: 'SALE50', title: 'Giảm 50.000₫', discount: 50000, shippingDiscount: 0 })
    wrap(<VoucherBox subtotal={500000} />)
    fireEvent.change(await screen.findByLabelText('Mã giảm giá'), { target: { value: 'sale50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }))
    expect(await screen.findByText('SALE50', { selector: 'strong' })).toBeInTheDocument()
    expect(service.applyVoucher).toHaveBeenCalledWith('SALE50', 500000)
    expect(useVoucherStore.getState().applied?.discount).toBe(50000)
  })

  it('shows the server message for a rejected code and keeps nothing applied', async () => {
    service.listVouchers.mockResolvedValue([])
    service.applyVoucher.mockRejectedValue(new Error('Mã đã hết hạn'))
    wrap(<VoucherBox subtotal={500000} />)
    fireEvent.change(await screen.findByLabelText('Mã giảm giá'), { target: { value: 'HETHAN' } })
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Mã đã hết hạn')
    expect(useVoucherStore.getState().applied).toBeNull()
  })

  it('drops a stored voucher that no longer qualifies for the cart', async () => {
    useVoucherStore.setState({ applied: { code: 'SALE50', title: 'Giảm 50.000₫', discount: 50000, shippingDiscount: 0 } })
    service.listVouchers.mockResolvedValue([])
    service.applyVoucher.mockRejectedValue(new Error('Đơn hàng chưa đạt giá trị tối thiểu'))
    wrap(<VoucherBox subtotal={100000} />)
    await waitFor(() => expect(useVoucherStore.getState().applied).toBeNull())
  })
})

describe('MockPage', () => {
  it('renders the page when mock is enabled', async () => {
    wrap(<MockPage title="Sổ địa chỉ"><p>nội dung</p></MockPage>)
    expect(await screen.findByText('nội dung')).toBeInTheDocument()
    expect(screen.getByText('Demo')).toBeInTheDocument()
  })

  it('explains how to enable the feature when mock is off', async () => {
    service.getConfig.mockResolvedValue(null)
    wrap(<MockPage title="Sổ địa chỉ"><p>nội dung</p></MockPage>)
    expect(await screen.findByText('Tính năng demo chưa được bật')).toBeInTheDocument()
    expect(screen.queryByText('nội dung')).not.toBeInTheDocument()
  })
})

describe('StatusBadge', () => {
  it('uses Vietnamese labels and falls back to the raw status', () => {
    render(<><StatusBadge status="REFUNDED" /><StatusBadge status="SOMETHING_NEW" /></>)
    expect(screen.getByText('Đã hoàn tiền')).toBeInTheDocument()
    expect(screen.getByText('SOMETHING_NEW')).toBeInTheDocument()
  })
})

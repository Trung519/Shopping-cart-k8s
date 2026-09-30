import { useState } from 'react'
import { CheckCircle2, CircleDollarSign, PackageCheck, RefreshCw, Truck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useAdminOrders, useUpdateOrderStatus } from '@/hooks/useOrders'
import type { Order, OrderStatus } from '@/types'
import { formatCurrency, formatDate } from '@/utils/format'

const filters: Array<{ label: string; value?: OrderStatus }> = [
  { label: 'Tất cả' },
  { label: 'Chờ thanh toán', value: 'PENDING' },
  { label: 'Đã thanh toán', value: 'PAID' },
  { label: 'Đang xử lý', value: 'PROCESSING' },
  { label: 'Đang giao', value: 'SHIPPED' },
  { label: 'Hoàn tất', value: 'COMPLETED' },
]

const statusLabels: Record<string, string> = {
  PENDING: 'Chờ thanh toán',
  PAID: 'Đã thanh toán',
  PROCESSING: 'Đang xử lý',
  SHIPPED: 'Đang giao',
  COMPLETED: 'Hoàn tất',
  CANCELLED: 'Đã hủy',
}

function nextAction(order: Order) {
  switch (order.status) {
    case 'PENDING':
      return {
        label: 'Xác nhận thanh toán mock',
        icon: CircleDollarSign,
        input: { status: 'PAID', paymentId: `mock-${order.id}`, paymentMethod: 'mock' } as const,
      }
    case 'PAID':
      return { label: 'Bắt đầu xử lý', icon: PackageCheck, input: { status: 'PROCESSING' } as const }
    case 'PROCESSING':
      return {
        label: 'Bàn giao vận chuyển',
        icon: Truck,
        input: {
          status: 'SHIPPED',
          trackingNumber: `LOCAL-${order.id.slice(0, 8).toUpperCase()}`,
          carrier: 'ShopCart Local',
        } as const,
      }
    case 'SHIPPED':
      return { label: 'Hoàn tất đơn', icon: CheckCircle2, input: { status: 'COMPLETED' } as const }
    default:
      return null
  }
}

export default function AdminOrdersPage() {
  const [status, setStatus] = useState<OrderStatus | undefined>()
  const orders = useAdminOrders(status)
  const updateStatus = useUpdateOrderStatus()
  const [error, setError] = useState('')

  const advance = async (order: Order) => {
    const action = nextAction(order)
    if (!action) return
    setError('')
    try {
      await updateStatus.mutateAsync({ id: order.id, input: action.input })
    } catch {
      setError('Không thể cập nhật trạng thái. Kiểm tra order-service và thử lại.')
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-bold uppercase text-primary-600">Order operations</p>
          <h1 className="mt-2 text-2xl font-black">Vận hành đơn hàng</h1>
          <p className="mt-1 text-sm text-gray-500">Theo dõi thanh toán mock, xử lý và giao hàng.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => orders.refetch()} disabled={orders.isFetching}>
          <RefreshCw className="mr-2 h-4 w-4" /> Làm mới
        </Button>
      </div>

      <div className="flex gap-2 overflow-x-auto border-b py-4">
        {filters.map((filter) => (
          <button
            key={filter.label}
            type="button"
            onClick={() => setStatus(filter.value)}
            className={`h-9 shrink-0 rounded-md px-3 text-sm font-semibold ${status === filter.value ? 'bg-ink text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {error && <p className="border-b bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>}
      {orders.isLoading ? (
        <div className="flex min-h-64 items-center justify-center"><LoadingSpinner size="lg" /></div>
      ) : orders.isError ? (
        <div className="border-b py-12 text-center text-sm text-red-600">Không tải được danh sách đơn hàng.</div>
      ) : !orders.data?.length ? (
        <div className="border-b py-12 text-center text-sm text-gray-500">Không có đơn ở trạng thái này.</div>
      ) : (
        <div className="overflow-x-auto border-b">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr><th className="px-4 py-3">Đơn hàng</th><th className="px-4 py-3">Khách hàng</th><th className="px-4 py-3">Sản phẩm</th><th className="px-4 py-3">Tổng tiền</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3 text-right">Thao tác</th></tr>
            </thead>
            <tbody className="divide-y">
              {orders.data.map((order) => {
                const action = nextAction(order)
                const Icon = action?.icon
                return (
                  <tr key={order.id} className="bg-white align-middle hover:bg-gray-50">
                    <td className="px-4 py-4"><p className="font-bold">#{order.id.slice(0, 8)}</p><p className="mt-1 text-xs text-gray-500">{formatDate(order.createdAt)}</p></td>
                    <td className="px-4 py-4 font-mono text-xs">{order.customerId.slice(0, 12)}...</td>
                    <td className="px-4 py-4">{order.items.length} dòng / {order.items.reduce((sum, item) => sum + item.quantity, 0)} sản phẩm</td>
                    <td className="px-4 py-4 font-bold">{formatCurrency(order.totalAmount, order.currency)}</td>
                    <td className="px-4 py-4"><span className="rounded bg-gray-100 px-2 py-1 text-xs font-semibold">{statusLabels[order.status] ?? order.status}</span></td>
                    <td className="px-4 py-4 text-right">
                      {action && Icon ? <Button size="sm" onClick={() => advance(order)} loading={updateStatus.isPending}><Icon className="mr-2 h-4 w-4" />{action.label}</Button> : <span className="text-xs text-gray-400">Không còn thao tác</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

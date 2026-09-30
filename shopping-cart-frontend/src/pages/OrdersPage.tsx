import { Link } from 'react-router-dom'
import { ChevronRight, Package, ShoppingBag } from 'lucide-react'
import { useOrders } from '@/hooks/useOrders'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatCurrency, formatDate } from '@/utils/format'
import type { Order, OrderStatus } from '@/types'

const statusVariants: Record<OrderStatus, 'default' | 'success' | 'warning' | 'destructive'> = {
  PENDING: 'warning',
  PAID: 'default',
  CONFIRMED: 'default',
  PROCESSING: 'default',
  SHIPPED: 'default',
  COMPLETED: 'success',
  DELIVERED: 'success',
  CANCELLED: 'destructive',
}

const statusLabels: Record<OrderStatus, string> = {
  PENDING: 'Chờ xác nhận',
  PAID: 'Đã thanh toán',
  CONFIRMED: 'Đã xác nhận',
  PROCESSING: 'Đang chuẩn bị',
  SHIPPED: 'Đang giao',
  COMPLETED: 'Hoàn tất',
  DELIVERED: 'Đã giao',
  CANCELLED: 'Đã hủy',
}

export default function OrdersPage() {
  const { data, isLoading, error } = useOrders()

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center">
        <p className="text-red-600">Không thể tải danh sách đơn hàng.</p>
      </div>
    )
  }

  if (!data || data.data.length === 0) {
    return (
      <div className="market-container flex flex-col items-center justify-center py-16">
        <Package className="h-16 w-16 text-gray-300" />
        <h2 className="mt-4 text-xl font-semibold">Bạn chưa có đơn hàng</h2>
        <p className="mt-2 text-gray-500">Đơn đã đặt sẽ xuất hiện tại đây.</p>
        <Link to="/products" className="mt-6">
          <span className="text-primary-600 hover:underline">Khám phá sản phẩm</span>
        </Link>
      </div>
    )
  }

  return (
    <div className="market-container space-y-6 py-8">
      <div>
        <p className="text-sm font-semibold uppercase text-primary-600">Buyer Center</p>
        <h1 className="mt-1 text-2xl font-bold text-ink">Đơn mua của tôi</h1>
      </div>

      <div className="space-y-4">
        {data.data.map((order) => (
          <OrderCard key={order.id} order={order} />
        ))}
      </div>
    </div>
  )
}

function OrderCard({ order }: { order: Order }) {
  return (
    <Link to={`/orders/${order.id}`}>
      <Card className="transition-shadow hover:border-primary-200 hover:shadow-sm">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <ShoppingBag className="h-5 w-5 text-primary-600" />
                <h3 className="font-semibold">Đơn #{order.id.slice(0, 8)}</h3>
                <Badge variant={statusVariants[order.status]}>{statusLabels[order.status]}</Badge>
              </div>
              <p className="mt-1 text-sm text-gray-500">Đặt ngày {formatDate(order.createdAt)}</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold">
                {formatCurrency(order.totalAmount, order.currency)}
              </p>
              <p className="text-sm text-gray-500">{order.items.length} sản phẩm</p>
            </div>
            <ChevronRight className="hidden h-5 w-5 text-gray-400 sm:block" />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

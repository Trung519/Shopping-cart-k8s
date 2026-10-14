import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ShipmentTimeline from '@/components/mock/ShipmentTimeline'
import ReturnRequestModal from '@/components/mock/ReturnRequestModal'
import { DemoBadge, StatusBadge } from '@/components/mock/MockPrimitives'
import { useMyReturns, useShipment } from '@/hooks/useMock'
import type { ShipmentStatus } from '@/types/mock'
import { ArrowLeft, Package } from 'lucide-react'
import { useOrder, useCancelOrder } from '@/hooks/useOrders'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatCurrency, formatDateTime } from '@/utils/format'
import type { OrderStatus } from '@/types'

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
  PENDING: 'Chờ xác nhận', PAID: 'Đã thanh toán', CONFIRMED: 'Đã xác nhận',
  PROCESSING: 'Đang chuẩn bị', SHIPPED: 'Đang giao', COMPLETED: 'Hoàn tất',
  DELIVERED: 'Đã giao', CANCELLED: 'Đã hủy',
}

function demoOrderStatus(status?: ShipmentStatus): OrderStatus | undefined {
  switch (status) {
    case 'CONFIRMED': return 'CONFIRMED'
    case 'PACKING': return 'PROCESSING'
    case 'HANDED_OVER':
    case 'IN_TRANSIT': return 'SHIPPED'
    case 'DELIVERED': return 'DELIVERED'
    default: return undefined
  }
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: order, isLoading, error } = useOrder(id!)
  const cancelOrder = useCancelOrder()
  const shipment = useShipment(id!)
  const myReturns = useMyReturns()
  const [returning, setReturning] = useState(false)

  const handleCancel = async () => {
    if (!order || !confirm('Bạn có chắc muốn hủy đơn hàng này?')) return
    try {
      await cancelOrder.mutateAsync(order.id)
    } catch (err) {
      console.error('Failed to cancel order:', err)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !order) {
    return (
      <div className="text-center">
        <p className="text-red-600">Không thể tải thông tin đơn hàng.</p>
        <Button variant="link" onClick={() => navigate('/orders')}>
          Quay lại danh sách đơn
        </Button>
      </div>
    )
  }

  const canCancel = ['PENDING', 'CONFIRMED'].includes(order.status)
  // The mock shipment clock overlays what the order page shows; the real order record is untouched.
  const demoStatus = order.status === 'CANCELLED' ? undefined : demoOrderStatus(shipment.data?.status)
  const displayStatus = demoStatus && demoStatus !== order.status && ['PENDING', 'PAID', 'CONFIRMED', 'PROCESSING', 'SHIPPED'].includes(order.status) ? demoStatus : order.status
  const isDemoStatus = displayStatus !== order.status
  const existingReturn = myReturns.data?.find((item) => item.orderRef === order.id)
  const canReturn = ['DELIVERED', 'COMPLETED'].includes(displayStatus) && myReturns.isSuccess && !existingReturn

  return (
    <div className="market-container space-y-6 py-8">
      <Button variant="ghost" onClick={() => navigate('/orders')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Quay lại đơn mua
      </Button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Đơn #{order.id.slice(0, 8)}</h1>
          <p className="text-muted">Đặt lúc {formatDateTime(order.createdAt)}</p>
        </div>
        <div className="flex items-center gap-2 self-start">
          {isDemoStatus && <DemoBadge />}
          <Badge variant={statusVariants[displayStatus]} className="text-sm">
            {statusLabels[displayStatus]}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <ShipmentTimeline orderId={order.id} />
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Sản phẩm trong đơn
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="divide-y">
                {order.items.map((item) => (
                  <div key={item.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
                    <div className="h-16 w-16 flex-shrink-0 rounded-md bg-slate-100" />
                    <div className="flex-1">
                      <h3 className="font-medium">{item.name}</h3>
                      <p className="text-sm text-muted">
                        {formatCurrency(item.unitPrice, order.currency)} x {item.quantity}
                      </p>
                    </div>
                    <div className="font-medium">
                      {formatCurrency(item.subTotal, order.currency)}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Tóm tắt đơn hàng</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between">
                <span className="text-slate-600">Tiền hàng</span>
                <span>{formatCurrency(order.totalAmount, order.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Phí vận chuyển</span>
                <span>Miễn phí</span>
              </div>
              <hr />
              <div className="flex justify-between text-lg font-bold">
                <span>Tổng cộng</span>
                <span>{formatCurrency(order.totalAmount, order.currency)}</span>
              </div>
            </CardContent>
          </Card>

          {order.shippingAddress && (
            <Card>
              <CardHeader>
                <CardTitle>Địa chỉ nhận hàng</CardTitle>
              </CardHeader>
              <CardContent>
                <address className="not-italic text-slate-600">
                  {order.shippingAddress.street}
                  <br />
                  {order.shippingAddress.city}, {order.shippingAddress.state}{' '}
                  {order.shippingAddress.postalCode}
                  <br />
                  {order.shippingAddress.country}
                </address>
              </CardContent>
            </Card>
          )}

          {canReturn && <Button type="button" variant="outline" className="w-full" onClick={() => setReturning(true)}>Yêu cầu đổi trả</Button>}
          {existingReturn && <div className="flex items-center justify-between rounded-card border border-line bg-white p-4 text-sm"><span>Yêu cầu đổi trả</span><StatusBadge status={existingReturn.status} /></div>}
          {returning && <ReturnRequestModal orderId={order.id} amount={order.totalAmount} onClose={() => setReturning(false)} />}

          {canCancel && (
            <Button
              variant="destructive"
              className="w-full"
              onClick={handleCancel}
              loading={cancelOrder.isPending}
            >
              Hủy đơn hàng
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

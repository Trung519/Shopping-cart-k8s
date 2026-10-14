import { BadgePercent, Bell, CheckCheck, PackageCheck, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, shortDate } from '@/components/mock/MockPrimitives'
import { useMockNotifications, useReadNotifications } from '@/hooks/useMock'
import { cn } from '@/utils/cn'

const icons = { order: PackageCheck, promo: BadgePercent, security: ShieldCheck }

export default function NotificationsPage() {
  const list = useMockNotifications()
  const markRead = useReadNotifications()
  const unread = list.data?.unread ?? 0

  return (
    <MockPage
      title="Thông báo"
      description="Cập nhật đơn hàng, ưu đãi và bảo mật. Thông báo mới sẽ hiện ngay khi đang mở trang."
      actions={<Button type="button" variant="outline" disabled={unread === 0} loading={markRead.isPending} onClick={() => markRead.mutate(undefined)}><CheckCheck className="mr-2 h-4 w-4" /> Đánh dấu đã đọc{unread > 0 ? ` (${unread})` : ''}</Button>}
    >
      {list.isLoading ? <SkeletonRows /> : list.isError ? <ErrorLine error={list.error} /> : list.data?.items.length === 0 ? <EmptyLine>Bạn chưa có thông báo nào.</EmptyLine> : (
        <ul className="divide-y divide-line rounded-card border border-line bg-white">
          {list.data?.items.map((item) => {
            const Icon = icons[item.type] ?? Bell
            return (
              <li key={item.id} className={cn('flex gap-4 px-4 py-4', item.unread && 'bg-primary-50')}>
                <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary-100 text-primary-700"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="text-sm font-semibold">{item.title}{item.unread && <span className="ml-2 inline-block h-2 w-2 rounded-full bg-price align-middle" aria-label="Chưa đọc" />}</h2>
                    <time dateTime={item.at} className="whitespace-nowrap text-xs text-muted">{shortDate(item.at)}</time>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-muted">{item.text}</p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </MockPage>
  )
}

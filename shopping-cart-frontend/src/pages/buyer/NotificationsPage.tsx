import { BadgePercent, Bell, CheckCircle2, PackageCheck } from 'lucide-react'

const notifications = [
  { icon: PackageCheck, title: 'Theo dõi đơn hàng', text: 'Trạng thái đóng gói và vận chuyển sẽ xuất hiện tại đây.', time: 'Hôm nay' },
  { icon: BadgePercent, title: 'Kho voucher', text: 'Voucher đủ điều kiện sẽ được gợi ý tại bước thanh toán.', time: 'Hôm qua' },
  { icon: CheckCircle2, title: 'Bảo vệ tài khoản', text: 'Mọi thay đổi quyền quản trị đều được ghi vào audit log.', time: '2 ngày trước' },
]

export default function NotificationsPage() { return <div><div className="border-b pb-5"><h1 className="text-2xl font-black">Thông báo</h1><p className="mt-1 text-sm text-gray-500">Cập nhật mua hàng và bảo mật tài khoản.</p></div><div className="mt-5 divide-y border-y bg-white">{notifications.map(({ icon: Icon, title, text, time }) => <article key={title} className="flex gap-4 px-4 py-5"><span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary-50 text-primary-600"><Icon className="h-5 w-5" /></span><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><h2 className="text-sm font-bold">{title}</h2><time className="whitespace-nowrap text-xs text-gray-400">{time}</time></div><p className="mt-1 text-sm leading-6 text-gray-500">{text}</p></div></article>)}</div><div className="mt-6 flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500"><Bell className="mt-0.5 h-5 w-5 flex-none" /> Bạn sẽ nhận thông báo khi đơn hàng hoặc tài khoản có cập nhật mới.</div></div> }

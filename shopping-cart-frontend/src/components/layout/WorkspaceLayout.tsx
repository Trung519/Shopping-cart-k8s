import { BarChart3, Bell, ChevronRight, CircleDollarSign, ClipboardList, Heart, LayoutDashboard, LifeBuoy, MessageCircle, Package, RotateCcw, Settings, ShieldCheck, Store, Tags, Users, Warehouse } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

type WorkspaceKind = 'buyer' | 'seller' | 'admin'

const navigation = {
  buyer: [
    { to: '/buyer', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/orders', label: 'Đơn mua', icon: ClipboardList },
    { to: '/buyer/wishlist', label: 'Yêu thích', icon: Heart },
    { to: '/buyer/notifications', label: 'Thông báo', icon: Bell },
    { to: '/support', label: 'Hỗ trợ', icon: LifeBuoy },
  ],
  seller: [
    { to: '/seller', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/seller/products', label: 'Sản phẩm', icon: Package },
    { to: '/seller/inventory', label: 'Kho hàng', icon: Warehouse },
    { to: '/seller/orders', label: 'Đơn bán', icon: ClipboardList },
    { to: '/seller/promotions', label: 'Khuyến mãi', icon: Tags },
    { to: '/seller/messages', label: 'Tin nhắn', icon: MessageCircle },
    { to: '/seller/finance', label: 'Tài chính', icon: CircleDollarSign },
    { to: '/seller/settings', label: 'Thiết lập shop', icon: Settings },
  ],
  admin: [
    { to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/admin/users', label: 'Người dùng', icon: Users },
    { to: '/admin/sellers', label: 'Duyệt người bán', icon: Store },
    { to: '/admin/catalog', label: 'Danh mục sản phẩm', icon: Package },
    { to: '/admin/orders', label: 'Đơn hàng', icon: ClipboardList },
    { to: '/admin/returns', label: 'Đổi trả & tranh chấp', icon: RotateCcw },
    { to: '/admin/finance', label: 'Thanh toán', icon: CircleDollarSign },
    { to: '/admin/analytics', label: 'Phân tích', icon: BarChart3 },
    { to: '/admin/audit', label: 'Nhật ký kiểm toán', icon: ShieldCheck },
  ],
}

const labels = { buyer: 'Trung tâm người mua', seller: 'Kênh người bán', admin: 'Quản trị hệ thống' }

export default function WorkspaceLayout({ kind }: { kind: WorkspaceKind }) {
  return (
    <div className="market-container py-7 sm:py-10">
      <div className="mb-5 flex items-center gap-2 text-sm text-slate-500"><span>ShopCart</span><ChevronRight className="h-4 w-4" /><span className="font-medium text-ink">{labels[kind]}</span></div>
      <div className="grid min-h-[620px] gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="overflow-x-auto rounded-card border border-slate-200 bg-white p-3 shadow-soft lg:sticky lg:top-28 lg:h-fit"><div className="mb-4 hidden rounded-xl bg-primary-50 px-3 py-3 lg:block"><p className="text-xs font-bold uppercase tracking-[0.12em] text-primary-600">Workspace</p><p className="mt-1 text-sm font-extrabold text-ink">{labels[kind]}</p></div><nav className="flex gap-1.5 lg:flex-col" aria-label={labels[kind]}>{navigation[kind].map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `focus-ring flex min-h-11 flex-none items-center gap-3 rounded-xl px-3 text-sm font-semibold transition ${isActive ? 'bg-primary-600 text-white shadow-soft' : 'text-slate-600 hover:bg-slate-100 hover:text-ink'}`}><Icon className="h-4 w-4 flex-none" /><span className="whitespace-nowrap">{label}</span></NavLink>)}</nav></aside>
        <main className="min-w-0 rounded-card border border-slate-200 bg-white p-4 shadow-soft sm:p-6 xl:p-8"><Outlet /></main>
      </div>
    </div>
  )
}

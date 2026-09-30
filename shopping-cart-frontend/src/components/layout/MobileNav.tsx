import { Grid2X2, Home, ShoppingCart, UserRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useCartStore } from '@/stores/cartStore'

const links = [
  { to: '/', label: 'Trang chủ', icon: Home, end: true },
  { to: '/products', label: 'Danh mục', icon: Grid2X2 },
  { to: '/cart', label: 'Giỏ hàng', icon: ShoppingCart },
  { to: '/buyer', label: 'Tài khoản', icon: UserRound },
]

export default function MobileNav() {
  const itemCount = useCartStore((state) => state.itemCount)
  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 grid h-[68px] grid-cols-4 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur md:hidden" aria-label="Điều hướng di động">
      {links.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `focus-ring relative flex min-h-[64px] flex-col items-center justify-center gap-1 text-[11px] font-semibold ${isActive ? 'text-primary-600' : 'text-slate-500'}`}>
          <Icon className="h-5 w-5" />
          {label}
          {to === '/cart' && itemCount > 0 && <span className="absolute left-1/2 top-1 ml-2 rounded-full bg-mint px-1.5 text-[9px] font-bold text-primary-950">{itemCount}</span>}
        </NavLink>
      ))}
    </nav>
  )
}

import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, Heart, LogOut, Menu, Search, ShoppingCart } from 'lucide-react'
import { useAppAuth } from '@/contexts/AuthContext'
import { useMockNotifications } from '@/hooks/useMock'
import { useCartStore } from '@/stores/cartStore'
import { useWishlistStore } from '@/stores/wishlistStore'

const categoryLinks = [
  { label: 'Máy tính', value: 'may-tinh-laptop' },
  { label: 'Điện thoại', value: 'dien-thoai-phu-kien' },
  { label: 'Thời trang nam', value: 'thoi-trang-nam' },
  { label: 'Thời trang nữ', value: 'thoi-trang-nu' },
  { label: 'Sách', value: 'sach-van-phong-pham' },
]

export default function Header() {
  const auth = useAppAuth()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const itemCount = useCartStore((state) => state.itemCount)
  const clearCart = useCartStore((state) => state.clearCart)
  const wishlistCount = useWishlistStore((state) => state.productIds.length)
  const unread = useMockNotifications().data?.unread ?? 0

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    const query = search.trim()
    navigate(query ? `/products?search=${encodeURIComponent(query)}` : '/products')
  }

  const logout = () => {
    setMenuOpen(false)
    auth.logout()
    clearCart()
    navigate('/')
  }

  const displayName = auth.user?.name || auth.user?.username || ''

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-white">
      <div className="market-container flex flex-wrap items-center gap-x-4 gap-y-3 py-3 lg:gap-x-6">
        <Link to="/" className="focus-ring flex flex-none items-center gap-2.5 rounded-md text-ink">
          <span className="flex h-10 w-10 items-center justify-center rounded-card bg-primary-600 text-[19px] font-bold text-white" aria-hidden="true">c</span>
          <span className="text-[22px] font-bold tracking-[-0.03em]">chợ</span>
        </Link>

        <Link to="/products" className="focus-ring hidden min-h-11 flex-none items-center gap-2 rounded-md border border-line px-3.5 text-sm font-semibold hover:bg-ground lg:flex">
          <Menu className="h-[18px] w-[18px]" aria-hidden="true" /> Danh mục
        </Link>

        <form onSubmit={submitSearch} role="search" className="order-last flex min-w-0 basis-full sm:order-none sm:basis-0 sm:flex-1">
          <label htmlFor="site-search" className="sr-only">Tìm kiếm sản phẩm</label>
          <input
            id="site-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm sản phẩm, thương hiệu, shop"
            className="h-11 min-w-0 flex-1 rounded-l-md border border-r-0 border-slate-300 bg-white px-3.5 text-sm text-ink outline-none placeholder:text-muted focus-visible:border-primary-600 focus-visible:ring-2 focus-visible:ring-primary-600"
          />
          <button type="submit" className="focus-ring flex h-11 w-[52px] items-center justify-center rounded-r-md bg-ink text-white hover:bg-slate-800" aria-label="Tìm kiếm" title="Tìm kiếm">
            <Search className="h-5 w-5" />
          </button>
        </form>

        <nav className="ml-auto flex items-center gap-1 sm:ml-0" aria-label="Tài khoản và mua hàng">
          <Link to="/buyer/wishlist" className="focus-ring relative hidden h-11 w-11 items-center justify-center rounded-md text-slate-700 hover:bg-ground md:flex" aria-label="Sản phẩm yêu thích" title="Yêu thích">
            <Heart className="h-[22px] w-[22px]" />
            {wishlistCount > 0 && <Counter value={wishlistCount} />}
          </Link>
          {auth.isAuthenticated && (
            <Link to="/buyer/notifications" className="focus-ring relative flex h-11 w-11 items-center justify-center rounded-md text-slate-700 hover:bg-ground" aria-label={`Thông báo${unread > 0 ? `, ${unread} chưa đọc` : ''}`} title="Thông báo">
              <Bell className="h-[22px] w-[22px]" />
              {unread > 0 && <Counter value={unread} />}
            </Link>
          )}
          <Link to={auth.isAuthenticated ? '/cart' : '/login'} className="focus-ring relative flex h-11 w-11 items-center justify-center rounded-md text-slate-700 hover:bg-ground" aria-label={`Giỏ hàng${itemCount > 0 ? `, ${itemCount} sản phẩm` : ''}`} title="Giỏ hàng">
            <ShoppingCart className="h-[22px] w-[22px]" />
            {itemCount > 0 && <Counter value={itemCount} />}
          </Link>

          {auth.isAuthenticated ? (
            <div className="relative hidden md:block">
              <button type="button" aria-haspopup="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)} className="focus-ring flex min-h-11 items-center gap-2 rounded-md px-2.5 text-sm font-semibold hover:bg-ground">
                <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-primary-100 text-[13px] text-primary-700" aria-hidden="true">{displayName.slice(0, 2).toUpperCase()}</span>
                <span className="max-w-28 truncate">{displayName}</span>
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              {menuOpen && (
                <div role="menu" className="absolute right-0 top-full z-20 mt-1 w-56 rounded-card border border-line bg-white p-1.5 shadow-lift" onClick={() => setMenuOpen(false)}>
                  <Link role="menuitem" to="/buyer" className="block rounded-md px-3 py-2.5 text-sm hover:bg-ground">Tài khoản của tôi</Link>
                  <Link role="menuitem" to="/orders" className="block rounded-md px-3 py-2.5 text-sm hover:bg-ground">Đơn mua</Link>
                  <Link role="menuitem" to="/buyer/notifications" className="block rounded-md px-3 py-2.5 text-sm hover:bg-ground">Thông báo</Link>
                  <Link role="menuitem" to="/seller" className="block rounded-md px-3 py-2.5 text-sm hover:bg-ground">Kênh người bán</Link>
                  {auth.isAdmin && <Link role="menuitem" to="/admin" className="block rounded-md px-3 py-2.5 text-sm hover:bg-ground">Quản trị hệ thống</Link>}
                  <button type="button" role="menuitem" onClick={logout} className="flex w-full items-center gap-2 rounded-md border-t border-line px-3 py-2.5 text-left text-sm text-danger hover:bg-ground">
                    <LogOut className="h-4 w-4" /> Đăng xuất
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/login" className="focus-ring flex min-h-11 items-center rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-slate-800">Đăng nhập</Link>
          )}
        </nav>
      </div>

      <nav className="market-container flex gap-2 overflow-x-auto pb-3" aria-label="Danh mục sản phẩm">
        {categoryLinks.map((category) => (
          <Link key={category.value} to={`/products?category=${encodeURIComponent(category.value)}`} className="focus-ring flex h-8 flex-none items-center whitespace-nowrap rounded-full bg-ground px-3 text-[13px] font-medium text-slate-700 hover:bg-primary-100 hover:text-primary-800">
            {category.label}
          </Link>
        ))}
        <Link to="/products?sort=price_asc" className="focus-ring ml-auto flex h-8 flex-none items-center whitespace-nowrap rounded-full bg-primary-100 px-3 text-[13px] font-semibold text-primary-800 hover:bg-primary-200">Deal hôm nay</Link>
      </nav>
    </header>
  )
}

function Counter({ value }: { value: number }) {
  return (
    <span className="absolute right-0.5 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-price px-1 text-[11px] font-bold text-white">
      {Math.min(value, 99)}
    </span>
  )
}

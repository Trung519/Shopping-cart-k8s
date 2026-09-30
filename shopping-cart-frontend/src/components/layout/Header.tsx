import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, Heart, LogOut, MapPin, Menu, Search, ShoppingBag, ShoppingCart, Store, UserRound } from 'lucide-react'
import { useAppAuth } from '@/contexts/AuthContext'
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
  const itemCount = useCartStore((state) => state.itemCount)
  const clearCart = useCartStore((state) => state.clearCart)
  const wishlistCount = useWishlistStore((state) => state.productIds.length)

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    const query = search.trim()
    navigate(query ? `/products?search=${encodeURIComponent(query)}` : '/products')
  }

  const logout = () => {
    auth.logout()
    clearCart()
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur">
      <div className="hidden bg-ink text-xs text-slate-100 lg:block">
        <div className="market-container flex h-8 items-center justify-between">
          <div className="flex items-center gap-5">
            <Link to="/seller" className="flex items-center gap-1.5 transition hover:text-mint">
              <Store className="h-3.5 w-3.5" /> Kênh người bán
            </Link>
            <span className="flex items-center gap-1.5 text-slate-300"><MapPin className="h-3.5 w-3.5 text-mint" /> Giao hàng toàn quốc · freeship từ 299.000đ</span>
          </div>
          <div className="flex items-center gap-5 text-slate-300">
            <Link to="/buyer/notifications" className="transition hover:text-white">Thông báo</Link>
            <Link to="/support" className="transition hover:text-white">Hỗ trợ</Link>
          </div>
        </div>
      </div>

      <div className="market-container flex min-h-[76px] items-center gap-3 py-3 lg:gap-8">
        <Link to="/" className="focus-ring flex flex-none items-center gap-2 rounded-xl text-primary-600">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white shadow-soft">
            <ShoppingBag className="h-5 w-5" />
          </span>
          <span className="hidden text-xl font-extrabold tracking-[-0.04em] sm:inline">shopcart</span>
          <svg
            className="h-5 w-7 flex-none rounded-[2px] shadow-sm"
            viewBox="0 0 30 20"
            role="img"
            aria-label="Cờ Việt Nam"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="30" height="20" fill="#DA251D" />
            <path d="m15 3.2 1.62 4.98h5.24l-4.24 3.08 1.62 4.98L15 13.16l-4.24 3.08 1.62-4.98-4.24-3.08h5.24Z" fill="#FFFF00" />
          </svg>
        </Link>

        <form onSubmit={submitSearch} className="relative min-w-0 flex-1">
          <label htmlFor="site-search" className="sr-only">Tìm kiếm sản phẩm</label>
          <input
            id="site-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm sản phẩm, thương hiệu và cửa hàng"
            className="focus-ring h-11 w-full rounded-xl border border-slate-300 bg-white pl-4 pr-12 text-sm text-ink shadow-sm outline-none transition placeholder:text-slate-400 hover:border-slate-400 focus:border-primary-500"
          />
          <button
            type="submit"
            className="focus-ring absolute right-1 top-1 flex h-9 w-10 items-center justify-center rounded-lg bg-primary-600 text-white transition hover:bg-primary-700"
            aria-label="Tìm kiếm"
            title="Tìm kiếm"
          >
            <Search className="h-5 w-5" />
          </button>
        </form>

        <nav className="hidden items-center gap-2 md:flex" aria-label="Tài khoản và mua hàng">
          <Link
            to="/buyer/wishlist"
            className="focus-ring relative flex h-11 w-11 items-center justify-center rounded-xl text-slate-600 transition hover:bg-primary-50 hover:text-primary-600"
            aria-label="Sản phẩm yêu thích"
            title="Yêu thích"
          >
            <Heart className="h-5 w-5" />
            {wishlistCount > 0 && <Counter value={wishlistCount} />}
          </Link>
          {auth.isAuthenticated && (
            <Link
              to="/buyer/notifications"
              className="focus-ring flex h-11 w-11 items-center justify-center rounded-xl text-slate-600 transition hover:bg-primary-50 hover:text-primary-600"
              aria-label="Thông báo"
              title="Thông báo"
            >
              <Bell className="h-5 w-5" />
            </Link>
          )}
          <Link
            to={auth.isAuthenticated ? '/cart' : '/login'}
            className="focus-ring relative flex h-11 w-11 items-center justify-center rounded-xl text-slate-600 transition hover:bg-primary-50 hover:text-primary-600"
            aria-label="Giỏ hàng"
            title="Giỏ hàng"
          >
            <ShoppingCart className="h-6 w-6" />
            {itemCount > 0 && <Counter value={itemCount} />}
          </Link>

          {auth.isAuthenticated ? (
            <div className="group relative">
              <Link to="/buyer" className="focus-ring flex h-11 items-center gap-2 rounded-xl px-2.5 transition hover:bg-slate-100">
                <UserRound className="h-5 w-5 text-slate-600" />
                <span className="max-w-28 truncate text-sm font-semibold">{auth.user?.name || auth.user?.username}</span>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </Link>
              <div className="invisible absolute right-0 top-full z-20 w-52 pt-2 opacity-0 transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
                <div className="rounded-card border border-slate-200 bg-white p-2 shadow-lift">
                  <Link to="/buyer" className="block rounded-lg px-3 py-2 text-sm hover:bg-slate-100">Tài khoản của tôi</Link>
                  <Link to="/orders" className="block rounded-lg px-3 py-2 text-sm hover:bg-slate-100">Đơn mua</Link>
                  {auth.isAdmin && <Link to="/admin" className="block rounded-lg px-3 py-2 text-sm hover:bg-slate-100">Quản trị hệ thống</Link>}
                  <button type="button" onClick={logout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-primary-700 hover:bg-primary-50">
                    <LogOut className="h-4 w-4" /> Đăng xuất
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <Link to="/login" className="focus-ring rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Đăng nhập
            </Link>
          )}
        </nav>
      </div>

      <nav className="market-container hidden h-12 items-center gap-7 overflow-x-auto text-sm lg:flex" aria-label="Danh mục sản phẩm">
        <Link to="/products" className="flex items-center gap-2 font-semibold text-ink transition hover:text-primary-600"><Menu className="h-4 w-4" /> Tất cả danh mục</Link>
        {categoryLinks.map((category) => (
          <Link key={category.value} to={`/products?category=${encodeURIComponent(category.value)}`} className="whitespace-nowrap text-slate-600 transition hover:text-primary-600">
            {category.label}
          </Link>
        ))}
        <Link to="/products?sort=price_asc" className="ml-auto whitespace-nowrap rounded-full bg-primary-50 px-3 py-1.5 font-semibold text-primary-700 transition hover:bg-primary-100">Deal hôm nay</Link>
      </nav>
    </header>
  )
}

function Counter({ value }: { value: number }) {
  return (
    <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-mint px-1 text-[10px] font-bold text-primary-950">
      {Math.min(value, 99)}
    </span>
  )
}

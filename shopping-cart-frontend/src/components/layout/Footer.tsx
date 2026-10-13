import { Link } from 'react-router-dom'

const columns = [
  { title: 'Mua hàng', links: [{ label: 'Đơn mua', to: '/orders' }, { label: 'Yêu thích', to: '/buyer/wishlist' }, { label: 'Giỏ hàng', to: '/cart' }] },
  { title: 'Bán hàng', links: [{ label: 'Kênh người bán', to: '/seller' }, { label: 'Mở gian hàng', to: '/seller' }] },
  { title: 'Hỗ trợ', links: [{ label: 'Trung tâm trợ giúp', to: '/support' }, { label: 'Thông báo', to: '/buyer/notifications' }] },
]

export default function Footer() {
  return (
    <footer className="mt-16 bg-ink pb-20 text-slate-300 md:pb-0">
      <div className="market-container grid gap-8 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="text-lg font-bold text-white">chợ</p>
          <p className="mt-3 max-w-xs text-sm leading-6">Marketplace nhiều gian hàng dành cho người mua và nhà bán hàng Việt Nam.</p>
        </div>
        {columns.map((column) => (
          <div key={column.title}>
            <p className="text-sm font-semibold text-white">{column.title}</p>
            <ul className="mt-3 space-y-2 text-sm">
              {column.links.map((link) => <li key={link.label}><Link to={link.to} className="hover:text-white">{link.label}</Link></li>)}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-700"><div className="market-container py-4 text-xs text-slate-400">© {new Date().getFullYear()} chợ. Giá đã gồm thuế, tồn kho được kiểm tra lại khi đặt hàng.</div></div>
    </footer>
  )
}

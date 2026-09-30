import { CreditCard, Headphones, RotateCcw, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

const promises = [
  { icon: ShieldCheck, title: 'Mua sắm an tâm', text: 'Người bán được kiểm duyệt' },
  { icon: RotateCcw, title: 'Đổi trả minh bạch', text: 'Theo dõi yêu cầu ngay trên app' },
  { icon: CreditCard, title: 'Thanh toán an toàn', text: 'Không lưu thông tin thẻ thô' },
  { icon: Headphones, title: 'Hỗ trợ 7 ngày', text: 'Luôn có lịch sử xử lý' },
]

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white pb-20 md:pb-0">
      <section className="border-b border-slate-200 bg-slate-50/70">
        <div className="market-container grid gap-3 py-5 sm:grid-cols-2 lg:grid-cols-4">
          {promises.map(({ icon: Icon, title, text }) => (
            <div key={title} className="flex items-center gap-3 rounded-card border border-slate-200 bg-white px-4 py-4">
              <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-mint/15 text-emerald"><Icon className="h-5 w-5" /></span>
              <div><p className="text-sm font-bold text-ink">{title}</p><p className="mt-0.5 text-xs text-slate-500">{text}</p></div>
            </div>
          ))}
        </div>
      </section>
      <div className="market-container grid gap-8 py-12 sm:grid-cols-2 lg:grid-cols-4">
        <div><p className="text-xl font-extrabold tracking-[-0.04em] text-primary-600">shopcart</p><p className="mt-3 max-w-xs text-sm leading-6 text-slate-500">Marketplace đa ngành hàng dành cho người mua và nhà bán hàng Việt Nam.</p></div>
        <FooterColumn title="Chăm sóc khách hàng" links={['Trung tâm trợ giúp', 'Hướng dẫn mua hàng', 'Chính sách đổi trả']} />
        <FooterColumn title="Về ShopCart" links={['Giới thiệu', 'Điều khoản', 'Bảo mật']} />
        <div><p className="text-sm font-bold text-ink">Dành cho người bán</p><Link to="/seller" className="mt-3 inline-flex rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">Mở gian hàng</Link></div>
      </div>
      <div className="border-t border-slate-200 bg-slate-50"><div className="market-container py-4 text-xs text-slate-500">© {new Date().getFullYear()} ShopCart. Marketplace dành cho người mua và nhà bán hàng Việt Nam.</div></div>
    </footer>
  )
}

function FooterColumn({ title, links }: { title: string; links: string[] }) {
  return <div><p className="text-sm font-bold text-ink">{title}</p><div className="mt-3 space-y-2">{links.map((link) => <span key={link} className="block text-sm text-slate-500">{link}</span>)}</div></div>
}

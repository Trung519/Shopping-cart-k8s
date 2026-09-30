import { ArrowRight, BookOpen, Box, Laptop, Shirt, Smartphone, Sparkles, Store } from 'lucide-react'
import { Link } from 'react-router-dom'
import MarketplaceProductCard from '@/components/product/MarketplaceProductCard'
import { useProducts } from '@/hooks/useProducts'

const categories = [
  { label: 'Máy tính', value: 'may-tinh-laptop', image: '/assets/products/computers.jpg', icon: Laptop },
  { label: 'Điện thoại', value: 'dien-thoai-phu-kien', image: '/assets/products/smartphones.jpg', icon: Smartphone },
  { label: 'Thời trang nam', value: 'thoi-trang-nam', image: '/assets/products/fashion.jpg', icon: Shirt },
  { label: 'Thời trang nữ', value: 'thoi-trang-nu', image: '/assets/products/fashion.jpg', icon: Sparkles },
  { label: 'Sách & tri thức', value: 'sach-van-phong-pham', image: '/assets/products/books.jpg', icon: BookOpen },
]

export default function HomePage() {
  const products = useProducts({ page: 1, pageSize: 10 })

  return (
    <div>
      <section className="market-container pt-5 sm:pt-7">
        <div className="relative min-h-[360px] overflow-hidden rounded-panel bg-primary-700 shadow-lift sm:min-h-[390px]">
        <img
          src="/assets/marketplace-hero.png"
          alt="Bộ sưu tập sản phẩm công nghệ, thời trang và sách trên ShopCart"
          className="absolute inset-0 h-full w-full object-cover object-[68%_center] opacity-80 sm:object-center"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-primary-950/95 via-primary-800/80 to-primary-700/10" />
        <div className="relative flex min-h-[360px] items-center px-6 py-10 sm:min-h-[390px] sm:px-10 lg:px-14">
          <div className="max-w-2xl text-white">
            <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-mint/20 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-mint">
              <Sparkles className="h-4 w-4" /> ShopCart marketplace
            </p>
            <h1 className="max-w-xl text-4xl font-extrabold leading-[1.06] tracking-[-0.045em] sm:text-5xl lg:text-6xl">Khám phá những điều phù hợp với bạn.</h1>
            <p className="mt-5 max-w-md text-base leading-7 text-slate-100 sm:text-lg">Một nơi để tìm sản phẩm, lưu lựa chọn yêu thích và theo dõi đơn mua một cách rõ ràng.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/products" className="focus-ring inline-flex h-12 items-center gap-2 rounded-xl bg-white px-6 text-sm font-bold text-primary-800 transition hover:bg-mint">
                Mua sắm ngay <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/seller" className="focus-ring inline-flex h-12 items-center rounded-xl border border-white/30 bg-white/10 px-6 text-sm font-bold text-white transition hover:bg-white/20">Mở gian hàng</Link>
            </div>
          </div>
        </div>
        </div>
      </section>

      <section className="py-8">
        <div className="market-container">
          <div className="mb-5 flex items-end justify-between"><div><p className="eyebrow">Khám phá nhanh</p><h2 className="section-title mt-1">Danh mục nổi bật</h2></div><Link to="/products" className="hidden items-center gap-1 text-sm font-semibold text-primary-600 hover:text-primary-700 sm:flex">Xem tất cả <ArrowRight className="h-4 w-4" /></Link></div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-4">
            {categories.map(({ label, value, image, icon: Icon }) => (
              <Link key={value} to={`/products?category=${encodeURIComponent(value)}`} className="focus-ring group relative min-h-36 overflow-hidden rounded-card bg-slate-100 shadow-soft">
                <img src={image} alt="" className="absolute inset-0 h-full w-full object-cover transition duration-300 group-hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/15 to-transparent" />
                <div className="relative flex h-full min-h-36 flex-col justify-between p-4 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 backdrop-blur"><Icon className="h-5 w-5" /></span><p className="font-bold">{label}</p></div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="py-8">
        <div className="market-container">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div><p className="eyebrow">Mới cập nhật</p><h2 className="section-title mt-1">Sản phẩm đáng xem</h2></div>
            <Link to="/products" className="inline-flex items-center gap-1 text-sm font-semibold text-primary-600">Xem danh mục <ArrowRight className="h-4 w-4" /></Link>
          </div>
          {products.isLoading ? <ProductSkeletonGrid /> : products.isError ? <InlineError /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-5">
              {products.data?.data.slice(0, 5).map((product) => <MarketplaceProductCard key={product.id} product={product} compact />)}
            </div>
          )}
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white py-10">
        <div className="market-container">
          <div className="mb-5 flex items-end justify-between"><div><p className="eyebrow">Gợi ý khám phá</p><h2 className="section-title mt-1">Dành cho bạn</h2></div><Link to="/products" className="flex items-center gap-1 text-sm font-semibold text-primary-600">Xem thêm <ArrowRight className="h-4 w-4" /></Link></div>
          {products.isLoading ? <ProductSkeletonGrid /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-5">
              {products.data?.data.slice(5, 10).map((product) => <MarketplaceProductCard key={product.id} product={product} compact />)}
            </div>
          )}
        </div>
      </section>
      <section className="market-container grid gap-3 py-8 md:grid-cols-3">
        <InfoCard icon={Box} title="Danh mục rõ ràng" text="Tìm nhanh sản phẩm theo nhu cầu và mức giá." />
        <InfoCard icon={Store} title="Không gian cho người bán" text="Quản lý sản phẩm và đơn hàng trong cùng một workspace." />
        <InfoCard icon={Sparkles} title="Lưu lựa chọn của bạn" text="Theo dõi sản phẩm yêu thích và hoạt động mua sắm." />
      </section>
    </div>
  )
}

function InfoCard({ icon: Icon, title, text }: { icon: typeof Box; title: string; text: string }) {
  return <div className="surface-card flex items-start gap-3 p-5"><span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-primary-50 text-primary-600"><Icon className="h-5 w-5" /></span><div><h3 className="font-bold text-ink">{title}</h3><p className="mt-1 text-sm leading-6 text-slate-500">{text}</p></div></div>
}

function ProductSkeletonGrid() {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-5">{Array.from({ length: 5 }).map((_, index) => <div key={index} className="overflow-hidden rounded-card border border-slate-200 bg-white"><div className="aspect-[4/5] animate-pulse bg-slate-200" /><div className="space-y-3 p-4"><div className="h-4 animate-pulse rounded bg-slate-200" /><div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" /></div></div>)}</div>
}

function InlineError() {
  return <div className="rounded-card border border-primary-200 bg-primary-50 p-5 text-sm text-primary-800">Không thể tải sản phẩm lúc này. Vui lòng thử lại sau.</div>
}

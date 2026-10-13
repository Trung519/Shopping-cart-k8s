import { ArrowRight, BookOpen, Laptop, Shirt, Smartphone, Sparkles, Truck } from 'lucide-react'
import { Link } from 'react-router-dom'
import MarketplaceProductCard from '@/components/product/MarketplaceProductCard'
import { useProducts } from '@/hooks/useProducts'

const categories = [
  { label: 'Máy tính', value: 'may-tinh-laptop', image: '/assets/products/computers.jpg', icon: Laptop },
  { label: 'Điện thoại', value: 'dien-thoai-phu-kien', image: '/assets/products/smartphones.jpg', icon: Smartphone },
  { label: 'Thời trang nam', value: 'thoi-trang-nam', image: '/assets/products/fashion.jpg', icon: Shirt },
  { label: 'Thời trang nữ', value: 'thoi-trang-nu', image: '/assets/products/fashion.jpg', icon: Sparkles },
  { label: 'Sách & văn phòng phẩm', value: 'sach-van-phong-pham', image: '/assets/products/books.jpg', icon: BookOpen },
]

export default function HomePage() {
  const products = useProducts({ page: 1, pageSize: 10 })

  return (
    <div className="pb-8">
      <section className="market-container flex flex-wrap gap-4 pt-6">
        <div className="flex min-h-[320px] flex-[999_1_560px] flex-wrap items-center justify-between gap-6 overflow-hidden rounded-panel bg-primary-600 p-6 text-white sm:p-10">
          <div className="flex max-w-[480px] flex-1 basis-[320px] flex-col gap-4">
            <p className="text-sm font-semibold text-primary-200">Mua sắm từ nhiều gian hàng, một giỏ hàng</p>
            <h1 className="text-4xl font-bold leading-[1.08] tracking-[-0.03em] sm:text-[44px]">Tìm đúng món bạn cần, giá rõ ràng.</h1>
            <p className="text-base leading-relaxed text-primary-100">Giá đã gồm thuế, tồn kho được kiểm tra lại khi đặt hàng.</p>
            <div className="flex flex-wrap gap-3">
              <Link to="/products" className="focus-ring inline-flex min-h-12 items-center gap-2 rounded-md bg-white px-5 text-sm font-semibold text-primary-700 hover:bg-primary-50">Mua sắm ngay <ArrowRight className="h-4 w-4" /></Link>
              <Link to="/seller" className="focus-ring inline-flex min-h-12 items-center rounded-md border border-primary-300 px-5 text-sm font-semibold text-white hover:bg-primary-700">Mở gian hàng</Link>
            </div>
          </div>
          <img src="/assets/marketplace-hero.png" alt="" className="hidden h-60 w-[300px] flex-none rounded-card object-cover lg:block" />
        </div>
        <div className="flex flex-[1_1_300px] flex-col gap-4">
          <Link to="/products?sort=price_asc" className="focus-ring flex flex-1 flex-col justify-between gap-2 rounded-panel border border-line bg-white p-6 text-ink hover:border-primary-300">
            <span className="text-[13px] font-semibold text-price">Deal hôm nay</span>
            <span className="text-xl font-bold leading-snug">Sản phẩm giá tốt, sắp xếp từ thấp đến cao</span>
            <span className="text-sm font-semibold text-primary-600">Xem deal →</span>
          </Link>
          <div className="flex flex-1 flex-col justify-between gap-2 rounded-panel bg-ink p-6 text-white">
            <span className="flex items-center gap-2 text-[13px] font-semibold text-slate-300"><Truck className="h-4 w-4" aria-hidden="true" /> Miễn phí vận chuyển</span>
            <span className="text-xl font-bold leading-snug">Đơn từ 299.000₫ trên toàn quốc</span>
          </div>
        </div>
      </section>

      <section className="py-8">
        <div className="market-container">
          <div className="mb-4 flex items-baseline justify-between"><h2 className="section-title">Danh mục</h2><Link to="/products" className="text-sm font-semibold text-primary-600 hover:text-primary-800">Tất cả danh mục</Link></div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {categories.map(({ label, value, image, icon: Icon }) => (
              <Link key={value} to={`/products?category=${encodeURIComponent(value)}`} className="focus-ring flex flex-col gap-3 rounded-card border border-line bg-white p-3 hover:border-primary-300">
                <span className="relative block aspect-[4/3] overflow-hidden rounded-md bg-[#EEF0EC]"><img src={image} alt="" className="h-full w-full object-cover" /></span>
                <span className="flex items-center gap-2 text-sm font-semibold"><Icon className="h-4 w-4 text-primary-600" aria-hidden="true" />{label}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="pb-8">
        <div className="market-container">
          <div className="mb-4 flex items-baseline justify-between"><h2 className="section-title">Mới cập nhật</h2><Link to="/products" className="text-sm font-semibold text-primary-600 hover:text-primary-800">Xem tất cả</Link></div>
          {products.isLoading ? <ProductSkeletonGrid /> : products.isError ? <InlineError /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-4">
              {products.data?.data.slice(0, 5).map((product) => <MarketplaceProductCard key={product.id} product={product} compact />)}
            </div>
          )}
        </div>
      </section>

      <section>
        <div className="market-container">
          <div className="mb-4 flex items-baseline justify-between"><h2 className="section-title">Gợi ý cho bạn</h2><Link to="/products" className="text-sm font-semibold text-primary-600 hover:text-primary-800">Xem thêm</Link></div>
          {products.isLoading ? <ProductSkeletonGrid /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-4">
              {products.data?.data.slice(5, 10).map((product) => <MarketplaceProductCard key={product.id} product={product} compact />)}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ProductSkeletonGrid() {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-4">{Array.from({ length: 5 }).map((_, index) => <div key={index} className="overflow-hidden rounded-card border border-line bg-white"><div className="aspect-square animate-pulse bg-slate-200" /><div className="space-y-3 p-4"><div className="h-4 animate-pulse rounded bg-slate-200" /><div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" /></div></div>)}</div>
}

function InlineError() {
  return <div role="alert" className="rounded-card border border-danger/30 bg-danger-soft p-5 text-sm text-danger">Không thể tải sản phẩm lúc này. Vui lòng thử lại sau.</div>
}

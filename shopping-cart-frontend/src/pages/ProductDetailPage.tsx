import { useState } from 'react'
import { CheckCircle2, Heart, Minus, Pencil, Plus, ShieldCheck, ShoppingCart, Store, Trash2, Truck } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ProductImage from '@/components/product/ProductImage'
import MarketplaceProductCard from '@/components/product/MarketplaceProductCard'
import { Button } from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useAppAuth } from '@/contexts/AuthContext'
import { useAddToCart } from '@/hooks/useCart'
import { useDeleteProduct, useProduct, useProducts } from '@/hooks/useProducts'
import { useWishlistStore } from '@/stores/wishlistStore'
import { formatCurrency } from '@/utils/format'

export default function ProductDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const auth = useAppAuth()
  const productQuery = useProduct(id)
  const addToCart = useAddToCart()
  const deleteProduct = useDeleteProduct()
  const [quantity, setQuantity] = useState(1)
  const isSaved = useWishlistStore((state) => state.contains(id))
  const toggleSaved = useWishlistStore((state) => state.toggle)
  const related = useProducts({ pageSize: 5, category: productQuery.data?.category })

  if (productQuery.isLoading) return <div className="flex min-h-[60vh] items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (productQuery.isError || !productQuery.data) return <div className="market-container py-16 text-center"><h1 className="text-xl font-bold">Không tìm thấy sản phẩm</h1><Link to="/products" className="mt-4 inline-block text-primary-600">Quay lại danh mục</Link></div>
  const product = productQuery.data

  const addProduct = async (buyNow = false) => {
    if (!auth.isAuthenticated) {
      navigate('/login', { state: { returnTo: `/products/${id}` } })
      return
    }
    await addToCart.mutateAsync({ productId: product.id, quantity })
    if (buyNow) navigate('/cart')
  }

  const removeProduct = async () => {
    if (!window.confirm(`Xóa sản phẩm “${product.name}”?`)) return
    await deleteProduct.mutateAsync(product.id)
    navigate('/products')
  }

  const hasSeller = Boolean(product.sellerId || product.shopName)

  return (
    <div>
      <div className="market-container py-7 sm:py-10">
        <nav className="flex flex-wrap items-center gap-2 text-sm text-slate-500"><Link to="/" className="hover:text-primary-600">Trang chủ</Link><span>/</span><Link to={`/products?category=${encodeURIComponent(product.category)}`} className="hover:text-primary-600">{categoryLabel(product.category)}</Link><span>/</span><span className="max-w-64 truncate font-medium text-ink">{product.name}</span></nav>

        <section className="surface-card mt-6 grid gap-7 p-4 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.9fr)] lg:p-8">
          <div>
            <div className="aspect-square overflow-hidden rounded-card bg-slate-100"><ProductImage src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" /></div>
            {product.imageUrl && <div className="mt-3 flex gap-2"><span className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl border-2 border-primary-500 bg-slate-100"><ProductImage src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" /></span></div>}
          </div>

          <div className="lg:sticky lg:top-28 lg:self-start lg:pl-3">
            <div className="flex items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">SKU: {product.sku}</span>{product.stock <= 0 && <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">Hết hàng</span>}</div><h1 className="mt-3 text-2xl font-extrabold leading-8 tracking-[-0.03em] text-ink sm:text-3xl">{product.name}</h1></div><button type="button" title={isSaved ? 'Bỏ yêu thích' : 'Yêu thích'} aria-label={isSaved ? 'Bỏ yêu thích' : 'Yêu thích'} onClick={() => toggleSaved(product.id)} className="focus-ring flex h-11 w-11 flex-none items-center justify-center rounded-xl border border-slate-200 transition hover:border-primary-300 hover:bg-primary-50 hover:text-primary-600"><Heart className={`h-5 w-5 ${isSaved ? 'fill-primary-500 text-primary-500' : ''}`} /></button></div>

            {(product.ratingAverage !== undefined || product.soldCount !== undefined) && <div className="mt-4 flex flex-wrap items-center gap-5 border-b border-slate-200 pb-4 text-sm text-slate-600">{product.ratingAverage !== undefined && <span><strong className="text-primary-600">{product.ratingAverage.toFixed(1)}</strong> đánh giá</span>}{product.soldCount !== undefined && <span className="border-l border-slate-200 pl-5"><strong>{product.soldCount}</strong> đã bán</span>}</div>}
            <div className="my-5 rounded-card bg-primary-50 px-5 py-5"><p className="text-3xl font-extrabold tracking-[-0.03em] text-primary-600">{formatCurrency(product.price, product.currency)}</p><p className="mt-2 text-sm text-slate-500">Giá và tồn kho được xác nhận lại khi tạo đơn.</p></div>

            <div className="space-y-5 text-sm">
              <div className="grid grid-cols-[110px_1fr] gap-3"><span className="text-slate-500">Vận chuyển</span><div><p className="flex items-center gap-2 font-semibold"><Truck className="h-4 w-4 text-emerald" /> Tính phí và thời gian giao khi checkout</p></div></div>
              <div className="grid grid-cols-[110px_1fr] items-center gap-3"><span className="text-slate-500">Số lượng</span><div className="flex items-center gap-3"><div className="flex overflow-hidden rounded-xl border border-slate-300"><button type="button" title="Giảm" aria-label="Giảm số lượng" onClick={() => setQuantity((value) => Math.max(1, value - 1))} disabled={quantity <= 1} className="focus-ring flex h-10 w-10 items-center justify-center hover:bg-slate-100 disabled:opacity-40"><Minus className="h-4 w-4" /></button><span className="flex h-10 w-12 items-center justify-center border-x border-slate-300 font-bold">{quantity}</span><button type="button" title="Tăng" aria-label="Tăng số lượng" onClick={() => setQuantity((value) => Math.min(product.stock, value + 1))} disabled={quantity >= product.stock} className="focus-ring flex h-10 w-10 items-center justify-center hover:bg-slate-100 disabled:opacity-40"><Plus className="h-4 w-4" /></button></div><span className="text-slate-500">{product.stock > 0 ? `${product.stock} sản phẩm có sẵn` : 'Sản phẩm hiện đã hết hàng'}</span></div></div>
            </div>

            <div className="mt-7 grid gap-3 sm:grid-cols-2"><Button type="button" size="lg" variant="outline" className="border-primary-500 bg-primary-50 text-primary-700 hover:bg-primary-100" onClick={() => addProduct()} loading={addToCart.isPending} disabled={product.stock <= 0}><ShoppingCart className="mr-2 h-5 w-5" /> Thêm vào giỏ</Button><Button type="button" size="lg" onClick={() => addProduct(true)} loading={addToCart.isPending} disabled={product.stock <= 0}>Mua ngay</Button></div>
            {addToCart.isSuccess && <p className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald"><CheckCircle2 className="h-4 w-4" /> Đã thêm sản phẩm vào giỏ.</p>}
            {addToCart.isError && <p className="mt-3 text-sm font-medium text-primary-700">Không thể thêm sản phẩm. Giá hoặc tồn kho có thể vừa thay đổi.</p>}

            <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-200 pt-5 text-xs text-slate-600"><span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald" /> Thông tin đơn được xác nhận trước khi đặt</span></div>
            {auth.isAdmin && <div className="mt-6 grid grid-cols-2 gap-3"><Button type="button" variant="secondary" onClick={() => navigate(`/admin/products/${product.id}/edit`)}><Pencil className="mr-2 h-4 w-4" /> Sửa</Button><Button type="button" variant="destructive" onClick={removeProduct} loading={deleteProduct.isPending}><Trash2 className="mr-2 h-4 w-4" /> Xóa</Button></div>}
          </div>
        </section>

        {hasSeller && <section className="surface-card mt-8 flex items-center gap-4 p-5"><span className="flex h-14 w-14 items-center justify-center rounded-xl bg-ink text-white"><Store className="h-6 w-6" /></span><div><p className="font-bold">{product.shopName || 'Cửa hàng đối tác'}</p><p className="mt-1 text-sm text-slate-500">Thông tin cửa hàng được cập nhật từ hồ sơ người bán.</p></div></section>}

        <section className="py-9"><h2 className="section-title">Mô tả sản phẩm</h2><div className="mt-4 max-w-4xl whitespace-pre-line text-sm leading-7 text-slate-600">{product.description || 'Thông tin chi tiết đang được người bán cập nhật.'}</div></section>

        <section className="border-t py-8"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">Có thể bạn cũng thích</h2><Link to={`/products?category=${encodeURIComponent(product.category)}`} className="text-sm font-semibold text-primary-600">Xem thêm</Link></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-5">{related.data?.data.filter((item) => item.id !== product.id).slice(0, 5).map((item) => <MarketplaceProductCard key={item.id} product={item} compact />)}</div></section>
      </div>
    </div>
  )
}

function categoryLabel(value: string) {
  const labels: Record<string, string> = {
    'may-tinh-laptop': 'Máy tính & laptop', 'dien-thoai-phu-kien': 'Điện thoại & phụ kiện',
    'thoi-trang-nam': 'Thời trang nam', 'thoi-trang-nu': 'Thời trang nữ',
    'sach-van-phong-pham': 'Sách & văn phòng phẩm', 'nha-cua-doi-song': 'Nhà cửa & đời sống',
  }
  return labels[value] || value
}

import { Heart, ShoppingCart, Star } from 'lucide-react'
import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAddToCart } from '@/hooks/useCart'
import { useAppAuth } from '@/contexts/AuthContext'
import { useWishlistStore } from '@/stores/wishlistStore'
import { formatCurrency } from '@/utils/format'
import ProductImage from './ProductImage'
import type { Product } from '@/types'

interface MarketplaceProductCardProps {
  product: Product
  compact?: boolean
}

export default function MarketplaceProductCard({ product, compact = false }: MarketplaceProductCardProps) {
  const navigate = useNavigate()
  const auth = useAppAuth()
  const addToCart = useAddToCart()
  const isSaved = useWishlistStore((state) => state.contains(product.id))
  const toggleSaved = useWishlistStore((state) => state.toggle)
  const hasSeller = Boolean(product.sellerId || product.shopName)
  const isOutOfStock = product.stock <= 0

  const addProduct = (event: MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    if (!auth.isAuthenticated) {
      navigate('/login', { state: { returnTo: `/products/${product.id}` } })
      return
    }
    addToCart.mutate({ productId: product.id, quantity: 1 })
  }

  return (
    <article className="group relative overflow-hidden rounded-card border border-slate-200 bg-white transition duration-200 hover:-translate-y-1 hover:border-primary-200 hover:shadow-lift">
      <Link to={`/products/${product.id}`} className="focus-ring block rounded-card">
        <div className="relative aspect-[4/5] overflow-hidden bg-slate-100">
          <ProductImage
            src={product.imageUrl}
            alt={product.name}
            className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
          />
          {isOutOfStock && <span className="absolute inset-0 flex items-center justify-center bg-ink/55 text-sm font-bold text-white">Hết hàng</span>}
        </div>

        <div className={compact ? 'p-3' : 'p-4'}>
          {hasSeller && <p className="mb-1 truncate text-xs font-semibold text-emerald">{product.shopName || 'Cửa hàng đối tác'}</p>}
          <h3 className="min-h-10 line-clamp-2 text-sm font-semibold leading-5 text-ink sm:text-[15px]">
            {product.name}
          </h3>
          {(product.ratingAverage !== undefined || product.soldCount !== undefined) && <div className="mt-2 flex min-h-4 items-center gap-2 text-xs text-slate-500">
            {product.ratingAverage !== undefined && <span className="flex items-center gap-1 text-sunflower">
              <Star className="h-3.5 w-3.5 fill-current" />
              {product.ratingAverage.toFixed(1)}
            </span>}
            {product.soldCount !== undefined && <span>Đã bán {product.soldCount}</span>}
          </div>}
          <div className="mt-3 flex min-h-10 items-end justify-between gap-2">
            <div>
              <p className="text-lg font-extrabold tracking-[-0.02em] text-primary-600">
                {formatCurrency(product.price, product.currency)}
              </p>
              {product.stock <= 10 && product.stock > 0 && (
                <p className="text-xs font-medium text-primary-700">Chỉ còn {product.stock}</p>
              )}
            </div>
          </div>
        </div>
      </Link>
      <button
        type="button"
        aria-label={isSaved ? 'Bỏ khỏi yêu thích' : 'Thêm vào yêu thích'}
        title={isSaved ? 'Bỏ khỏi yêu thích' : 'Thêm vào yêu thích'}
        className="focus-ring absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/95 text-slate-600 shadow-sm transition hover:text-primary-600"
        onClick={() => toggleSaved(product.id)}
      >
        <Heart className={`h-5 w-5 ${isSaved ? 'fill-primary-500 text-primary-500' : ''}`} />
      </button>
      <button
        type="button"
        aria-label={`Thêm ${product.name} vào giỏ`}
        title="Thêm nhanh vào giỏ"
        className="focus-ring absolute bottom-3 right-3 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-50 text-primary-700 opacity-100 transition hover:bg-primary-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:opacity-0 sm:group-hover:opacity-100"
        onClick={addProduct}
        disabled={isOutOfStock || addToCart.isPending}
      >
        <ShoppingCart className="h-5 w-5" />
      </button>
    </article>
  )
}

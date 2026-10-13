import { Heart, Star } from 'lucide-react'
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
    <article className="group relative flex flex-col overflow-hidden rounded-card border border-line bg-white transition-colors hover:border-primary-300">
      <Link to={`/products/${product.id}`} className="focus-ring block flex-1 rounded-card">
        <div className="relative aspect-square overflow-hidden bg-[#EEF0EC]">
          <ProductImage src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" />
          {isOutOfStock && <span className="absolute inset-0 flex items-center justify-center bg-ink/60 text-sm font-bold text-white">Hết hàng</span>}
        </div>

        <div className={compact ? 'p-3' : 'p-4'}>
          <h3 className="min-h-10 line-clamp-2 text-sm font-medium leading-5 text-ink">{product.name}</h3>
          <p className="price mt-2 text-[17px]">{formatCurrency(product.price, product.currency)}</p>
          {(product.ratingAverage !== undefined || product.soldCount !== undefined || hasSeller) && (
            <div className="mt-1.5 flex min-h-4 flex-wrap items-center gap-x-2 text-xs text-muted">
              {product.ratingAverage !== undefined && (
                <span className="flex items-center gap-1 font-semibold text-ink">
                  <Star className="h-3.5 w-3.5 fill-warning text-warning" aria-hidden="true" />
                  {product.ratingAverage.toFixed(1)}
                </span>
              )}
              {product.soldCount !== undefined && <span>Đã bán {product.soldCount}</span>}
              {hasSeller && <span className="truncate">{product.shopName || 'Cửa hàng đối tác'}</span>}
            </div>
          )}
          {product.stock <= 10 && product.stock > 0 && <p className="mt-1 text-xs font-medium text-warning">Chỉ còn {product.stock}</p>}
        </div>
      </Link>

      <button
        type="button"
        aria-label={isSaved ? 'Bỏ khỏi yêu thích' : 'Thêm vào yêu thích'}
        title={isSaved ? 'Bỏ khỏi yêu thích' : 'Thêm vào yêu thích'}
        aria-pressed={isSaved}
        className="focus-ring absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-full bg-white/95 text-slate-600 transition hover:text-price"
        onClick={() => toggleSaved(product.id)}
      >
        <Heart className={`h-5 w-5 ${isSaved ? 'fill-price text-price' : ''}`} />
      </button>

      {/* Always visible: the old version hid this behind hover, which keyboard users could not see. */}
      <div className={compact ? 'px-3 pb-3' : 'px-4 pb-4'}>
        <button
          type="button"
          aria-label={`Thêm ${product.name} vào giỏ`}
          className="focus-ring min-h-10 w-full rounded-md border border-primary-600 bg-white text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-600 hover:text-white disabled:cursor-not-allowed disabled:border-line disabled:bg-[#EEF0EC] disabled:text-muted"
          onClick={addProduct}
          disabled={isOutOfStock || addToCart.isPending}
        >
          {isOutOfStock ? 'Hết hàng' : 'Thêm vào giỏ'}
        </button>
      </div>
    </article>
  )
}

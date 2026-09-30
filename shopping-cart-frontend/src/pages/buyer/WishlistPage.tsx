import { Heart } from 'lucide-react'
import MarketplaceProductCard from '@/components/product/MarketplaceProductCard'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useProducts } from '@/hooks/useProducts'
import { useWishlistStore } from '@/stores/wishlistStore'

export default function WishlistPage() {
  const ids = useWishlistStore((state) => state.productIds)
  const products = useProducts({ pageSize: 100 })
  const saved = products.data?.data.filter((product) => ids.includes(product.id)) ?? []
  return <div><div className="border-b pb-5"><h1 className="text-2xl font-black">Sản phẩm yêu thích</h1><p className="mt-1 text-sm text-gray-500">Những sản phẩm bạn muốn xem lại sau.</p></div>{products.isLoading ? <div className="flex py-16 justify-center"><LoadingSpinner /></div> : saved.length === 0 ? <div className="flex min-h-72 flex-col items-center justify-center text-center"><Heart className="h-12 w-12 text-gray-300" /><h2 className="mt-4 font-bold">Chưa có sản phẩm yêu thích</h2><p className="mt-1 text-sm text-gray-500">Nhấn biểu tượng trái tim trên sản phẩm để lưu lại.</p></div> : <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 xl:gap-5">{saved.map((product) => <MarketplaceProductCard key={product.id} product={product} />)}</div>}</div>
}

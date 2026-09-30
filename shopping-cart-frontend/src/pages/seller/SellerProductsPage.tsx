import { PackagePlus, Pencil } from 'lucide-react'
import { Link } from 'react-router-dom'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useAppAuth } from '@/contexts/AuthContext'
import { useProducts } from '@/hooks/useProducts'
import { formatCurrency } from '@/utils/format'

export default function SellerProductsPage() {
  const { user } = useAppAuth()
  const products = useProducts({ sellerId: user?.id, pageSize: 100 })

  if (products.isLoading) return <div className="flex min-h-72 items-center justify-center"><LoadingSpinner size="lg" /></div>

  return <div><div className="flex items-center justify-between border-b pb-5"><div><h1 className="text-2xl font-black">Sản phẩm của shop</h1><p className="mt-1 text-sm text-gray-500">Quản lý sản phẩm thuộc đúng tài khoản seller hiện tại.</p></div><Link to="/seller/products/new" className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-bold text-white"><PackagePlus className="h-4 w-4" /> Thêm sản phẩm</Link></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="border-b text-gray-500"><tr><th className="px-3 py-3">SKU</th><th className="px-3 py-3">Tên</th><th className="px-3 py-3">Giá</th><th className="px-3 py-3">Tồn kho</th><th className="px-3 py-3">Trạng thái</th><th className="px-3 py-3"><span className="sr-only">Thao tác</span></th></tr></thead><tbody className="divide-y">{products.data?.data.map((product) => <tr key={product.id}><td className="px-3 py-4 font-mono text-xs">{product.sku}</td><td className="px-3 py-4 font-semibold">{product.name}</td><td className="px-3 py-4">{formatCurrency(product.price, product.currency)}</td><td className="px-3 py-4">{product.stock}</td><td className="px-3 py-4">{product.isActive ? 'Đang bán' : 'Tạm ẩn'}</td><td className="px-3 py-4 text-right"><Link to={`/seller/products/${product.id}/edit`} className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-gray-100" title="Sửa sản phẩm"><Pencil className="h-4 w-4" /></Link></td></tr>)}</tbody></table>{products.data?.data.length === 0 && <div className="py-16 text-center text-sm text-gray-500">Shop chưa có sản phẩm nào.</div>}</div></div>
}

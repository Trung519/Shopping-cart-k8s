import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Save } from 'lucide-react'
import { useCategories, useCreateProduct, useProduct, useUpdateProduct } from '@/hooks/useProducts'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { ProductFormInput } from '@/types'

const DEFAULT_FORM: ProductFormInput = {
  sku: '',
  name: '',
  description: '',
  price: 0,
  currency: 'VND',
  quantity: 0,
  category: '',
  imageUrl: '',
}

export default function ProductAdminPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const sellerMode = location.pathname.startsWith('/seller/')
  const isEditMode = Boolean(id)
  const { data: product, isLoading } = useProduct(id ?? '')
  const createProduct = useCreateProduct()
  const updateProduct = useUpdateProduct()
  const categories = useCategories()
  const [form, setForm] = useState<ProductFormInput>(DEFAULT_FORM)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!product || !isEditMode) {
      return
    }

    setForm({
      sku: product.sku,
      name: product.name,
      description: product.description,
      price: product.price,
      currency: product.currency,
      quantity: product.stock,
      category: product.category,
      imageUrl: product.imageUrl ?? '',
    })
  }, [isEditMode, product])

  const setField = <K extends keyof ProductFormInput>(field: K, value: ProductFormInput[K]) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)

    try {
      if (isEditMode && id) {
        const updated = await updateProduct.mutateAsync({ id, input: form })
        navigate(sellerMode ? '/seller/products' : `/products/${updated.id}`)
        return
      }

      const created = await createProduct.mutateAsync(form)
      navigate(sellerMode ? '/seller/products' : `/products/${created.id}`)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Không thể lưu sản phẩm')
    }
  }

  if (isEditMode && isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate(id ? `/products/${id}` : '/products')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Quay lại
        </Button>
        <Link to="/products" className="text-sm text-primary-600 hover:underline">
          Xem catalog
        </Link>
      </div>

      <Card className="mx-auto max-w-3xl">
        <CardHeader>
          <CardTitle>{isEditMode ? 'Chỉnh sửa sản phẩm' : 'Tạo sản phẩm'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>SKU</span>
                <Input
                  value={form.sku}
                  onChange={(event) => setField('sku', event.target.value)}
                  disabled={isEditMode}
                  required
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>Tên sản phẩm</span>
                <Input
                  value={form.name}
                  onChange={(event) => setField('name', event.target.value)}
                  required
                />
              </label>
            </div>

            <label className="block space-y-2 text-sm font-medium text-gray-700">
              <span>Mô tả</span>
              <textarea
                className="min-h-28 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
                value={form.description}
                onChange={(event) => setField('description', event.target.value)}
              />
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>Giá</span>
                <Input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={form.price}
                  onChange={(event) => setField('price', Number(event.target.value))}
                  required
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>Tiền tệ</span>
                <Input
                  value={form.currency}
                  onChange={(event) => setField('currency', event.target.value.toUpperCase())}
                  maxLength={3}
                  required
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>Danh mục</span>
                <select
                  className="focus-ring h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm"
                  value={form.category}
                  onChange={(event) => setField('category', event.target.value)}
                  required
                >
                  <option value="">Chọn danh mục</option>
                  {categories.data?.map((category) => <option key={category.id} value={category.slug}>{category.name}</option>)}
                </select>
              </label>
              <label className="space-y-2 text-sm font-medium text-gray-700">
                <span>Tồn kho</span>
                <Input
                  type="number"
                  min="0"
                  step="1"
                  value={form.quantity}
                  onChange={(event) => setField('quantity', Number(event.target.value))}
                  required
                />
              </label>
            </div>

            <label className="space-y-2 text-sm font-medium text-gray-700">
              <span>URL hình ảnh</span>
              <Input
                value={form.imageUrl}
                onChange={(event) => setField('imageUrl', event.target.value)}
                placeholder="https://example.com/image.jpg"
              />
            </label>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex justify-end">
              <Button
                type="submit"
                size="lg"
                loading={createProduct.isPending || updateProduct.isPending}
              >
                <Save className="mr-2 h-4 w-4" />
                {isEditMode ? 'Lưu thay đổi' : 'Tạo sản phẩm'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

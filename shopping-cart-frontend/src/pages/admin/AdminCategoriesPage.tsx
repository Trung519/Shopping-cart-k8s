import { useState, type FormEvent } from 'react'
import { Plus, Power, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useCategories, useManageCategories } from '@/hooks/useProducts'

export default function AdminCategoriesPage() {
  const categories = useCategories(true)
  const mutations = useManageCategories()
  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await mutations.create.mutateAsync({ slug, name, sortOrder: (categories.data?.length ?? 0) * 10 + 10 })
      setSlug('')
      setName('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Không thể tạo danh mục')
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm font-semibold text-primary-600">Catalog</p>
        <h1 className="mt-1 text-2xl font-black text-ink">Quản lý danh mục</h1>
        <p className="mt-1 text-sm text-gray-500">Danh mục ở đây là nguồn lựa chọn duy nhất khi đăng sản phẩm.</p>
      </header>

      <form onSubmit={create} className="grid gap-3 border-y bg-white py-4 sm:grid-cols-[1fr_1.4fr_auto]">
        <label className="space-y-1 text-sm font-semibold"><span>Slug</span><Input value={slug} onChange={(event) => setSlug(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))} placeholder="phu-kien-cong-nghe" required /></label>
        <label className="space-y-1 text-sm font-semibold"><span>Tên hiển thị</span><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Phụ kiện công nghệ" required /></label>
        <Button type="submit" className="self-end" loading={mutations.create.isPending}><Plus className="mr-2 h-4 w-4" />Thêm</Button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto border-y bg-white">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500"><tr><th className="px-4 py-3">Tên</th><th className="px-4 py-3">Slug</th><th className="px-4 py-3">Thứ tự</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3 text-right">Thao tác</th></tr></thead>
          <tbody>{categories.data?.map((category) => (
            <tr key={category.id} className="border-b last:border-0">
              <td className="px-4 py-3 font-semibold text-ink">{category.name}</td>
              <td className="px-4 py-3 font-mono text-xs text-gray-500">{category.slug}</td>
              <td className="px-4 py-3">{category.sortOrder}</td>
              <td className="px-4 py-3"><span className={category.isActive ? 'text-emerald-700' : 'text-gray-400'}>{category.isActive ? 'Đang dùng' : 'Đã ẩn'}</span></td>
              <td className="px-4 py-3"><div className="flex justify-end gap-2">
                <button type="button" title={category.isActive ? 'Ẩn danh mục' : 'Bật danh mục'} onClick={() => mutations.update.mutate({ id: category.id, input: { isActive: !category.isActive } })} className="focus-ring flex h-9 w-9 items-center justify-center rounded-md border hover:bg-gray-50"><Power className="h-4 w-4" /></button>
                <button type="button" title="Xóa danh mục" onClick={() => mutations.remove.mutate(category.id, { onError: (requestError) => setError(requestError instanceof Error ? requestError.message : 'Danh mục đang được sử dụng') })} className="focus-ring flex h-9 w-9 items-center justify-center rounded-md border text-red-600 hover:bg-red-50"><Trash2 className="h-4 w-4" /></button>
              </div></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}

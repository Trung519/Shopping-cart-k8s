import { useEffect, useState, type FormEvent } from 'react'
import { ChevronLeft, ChevronRight, PackageSearch, Plus, Search, SlidersHorizontal, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import MarketplaceProductCard from '@/components/product/MarketplaceProductCard'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAppAuth } from '@/contexts/AuthContext'
import { useCategories, useProducts } from '@/hooks/useProducts'
import type { ProductCategory } from '@/types'

type SortOption = 'newest' | 'price_asc' | 'price_desc' | 'name'

export default function ProductsPage() {
  const auth = useAppAuth()
  const [params, setParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [searchInput, setSearchInput] = useState(params.get('search') ?? '')
  const [minInput, setMinInput] = useState(params.get('minPrice') ?? '')
  const [maxInput, setMaxInput] = useState(params.get('maxPrice') ?? '')
  const page = Number(params.get('page') ?? '1')
  const search = params.get('search') ?? undefined
  const category = params.get('category') ?? undefined
  const sort = (params.get('sort') as SortOption | null) ?? 'newest'
  const minPrice = numberParam(params.get('minPrice'))
  const maxPrice = numberParam(params.get('maxPrice'))
  const products = useProducts({ page, pageSize: 20, search, category, sort, minPrice, maxPrice })
  const categories = useCategories()

  useEffect(() => setSearchInput(search ?? ''), [search])

  const updateParam = (name: string, value?: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name !== 'page') next.delete('page')
    setParams(next)
  }

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    updateParam('search', searchInput.trim() || undefined)
  }

  const applyPrice = (event: FormEvent) => {
    event.preventDefault()
    const next = new URLSearchParams(params)
    if (minInput) next.set('minPrice', minInput); else next.delete('minPrice')
    if (maxInput) next.set('maxPrice', maxInput); else next.delete('maxPrice')
    next.delete('page')
    setParams(next)
    setFiltersOpen(false)
  }

  return (
    <div className="market-container py-7 sm:py-10">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div><p className="eyebrow">Danh mục</p><h1 className="page-heading mt-1">Khám phá sản phẩm</h1><p className="mt-2 text-sm text-slate-500">{products.data?.totalItems ?? 0} sản phẩm phù hợp với bộ lọc hiện tại</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setFiltersOpen(true)} className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 text-sm font-semibold lg:hidden"><SlidersHorizontal className="h-4 w-4" /> Bộ lọc</button>
          <label className="flex items-center gap-2 text-sm text-slate-500"><span className="hidden sm:inline">Sắp xếp</span><select value={sort} onChange={(event) => updateParam('sort', event.target.value)} className="focus-ring min-h-11 rounded-xl border border-slate-300 bg-white px-3 font-medium text-ink"><option value="newest">Mới nhất</option><option value="price_asc">Giá thấp đến cao</option><option value="price_desc">Giá cao đến thấp</option><option value="name">Tên A-Z</option></select></label>
          {auth.isAdmin && <Link to="/admin/products/new" className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-ink px-4 text-sm font-semibold text-white"><Plus className="h-4 w-4" /> Thêm sản phẩm</Link>}
        </div>
      </div>

      <form onSubmit={submitSearch} className="mt-6 flex max-w-2xl gap-2">
        <div className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" /><Input type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Tìm trong danh mục" className="pl-9" /></div>
        <Button type="submit">Tìm kiếm</Button>
      </form>

      <div className="mt-7 grid gap-6 lg:grid-cols-[256px_minmax(0,1fr)]">
        <FilterPanel categories={categories.data ?? []} activeCategory={category} minInput={minInput} maxInput={maxInput} setMinInput={setMinInput} setMaxInput={setMaxInput} applyPrice={applyPrice} updateCategory={(value) => updateParam('category', value)} mobileOpen={filtersOpen} closeMobile={() => setFiltersOpen(false)} />

        <main>
          {products.isLoading ? <CatalogSkeleton /> : products.isError ? <CatalogError /> : products.data?.data.length === 0 ? <EmptyCatalog clear={() => setParams({})} /> : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 xl:gap-4">{products.data?.data.map((product) => <MarketplaceProductCard key={product.id} product={product} />)}</div>
              {products.data && products.data.totalPages > 1 && <Pagination page={page} totalPages={products.data.totalPages} setPage={(nextPage) => updateParam('page', String(nextPage))} />}
            </>
          )}
        </main>
      </div>
    </div>
  )
}

interface FilterPanelProps {
  categories: ProductCategory[]; activeCategory?: string; minInput: string; maxInput: string
  setMinInput: (value: string) => void; setMaxInput: (value: string) => void
  applyPrice: (event: FormEvent) => void; updateCategory: (value?: string) => void
  mobileOpen: boolean; closeMobile: () => void
}

function FilterPanel(props: FilterPanelProps) {
  const content = <div className="space-y-7"><div><h2 className="text-sm font-bold uppercase tracking-[0.1em] text-ink">Danh mục</h2><div className="mt-3 space-y-1"><button type="button" onClick={() => props.updateCategory()} className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${!props.activeCategory ? 'bg-primary-600 font-bold text-white' : 'text-slate-600 hover:bg-slate-100'}`}>Tất cả sản phẩm</button>{props.categories.map((category) => <button key={category.id} type="button" onClick={() => props.updateCategory(category.slug)} className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${props.activeCategory === category.slug ? 'bg-primary-50 font-bold text-primary-700' : 'text-slate-600 hover:bg-slate-100'}`}>{category.name}</button>)}</div></div><form onSubmit={props.applyPrice}><h2 className="text-sm font-bold uppercase tracking-[0.1em] text-ink">Khoảng giá</h2><div className="mt-3 grid grid-cols-2 gap-2"><Input type="number" min="0" placeholder="Từ" value={props.minInput} onChange={(event) => props.setMinInput(event.target.value)} /><Input type="number" min="0" placeholder="Đến" value={props.maxInput} onChange={(event) => props.setMaxInput(event.target.value)} /></div><Button type="submit" variant="outline" className="mt-3 w-full">Áp dụng</Button></form></div>
  return <><aside className="surface-card hidden h-fit p-4 lg:sticky lg:top-28 lg:block">{content}</aside>{props.mobileOpen && <div className="fixed inset-0 z-[70] lg:hidden"><button type="button" aria-label="Đóng bộ lọc" className="absolute inset-0 bg-ink/50" onClick={props.closeMobile} /><aside className="absolute inset-y-0 left-0 w-[min(86vw,340px)] overflow-y-auto bg-white p-5 shadow-lift"><div className="mb-6 flex items-center justify-between"><h2 className="text-lg font-bold">Bộ lọc</h2><button type="button" title="Đóng" aria-label="Đóng" onClick={props.closeMobile} className="focus-ring flex h-11 w-11 items-center justify-center rounded-xl hover:bg-slate-100"><X className="h-5 w-5" /></button></div>{content}</aside></div>}</>
}

function Pagination({ page, totalPages, setPage }: { page: number; totalPages: number; setPage: (page: number) => void }) {
  return <nav className="mt-8 flex items-center justify-center gap-2" aria-label="Phân trang"><button type="button" title="Trang trước" aria-label="Trang trước" onClick={() => setPage(page - 1)} disabled={page <= 1} className="focus-ring flex h-10 w-10 items-center justify-center rounded-md border bg-white disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button><span className="px-3 text-sm font-semibold">Trang {page} / {totalPages}</span><button type="button" title="Trang sau" aria-label="Trang sau" onClick={() => setPage(page + 1)} disabled={page >= totalPages} className="focus-ring flex h-10 w-10 items-center justify-center rounded-md border bg-white disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button></nav>
}

function CatalogSkeleton() { return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 xl:gap-4">{Array.from({ length: 10 }).map((_, index) => <div key={index} className="overflow-hidden rounded-card border bg-white"><div className="aspect-[4/5] animate-pulse bg-slate-200" /><div className="space-y-3 p-4"><div className="h-4 animate-pulse rounded bg-slate-200" /><div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" /></div></div>)}</div> }
function CatalogError() { return <div className="rounded-card border border-primary-200 bg-primary-50 p-6 text-primary-800">Không thể tải danh mục. Vui lòng thử lại sau.</div> }
function EmptyCatalog({ clear }: { clear: () => void }) { return <div className="surface-card flex min-h-80 flex-col items-center justify-center p-8 text-center"><PackageSearch className="h-12 w-12 text-slate-300" /><h2 className="mt-4 text-lg font-bold">Không tìm thấy sản phẩm</h2><p className="mt-1 text-sm text-slate-500">Thử từ khóa hoặc bộ lọc khác.</p><Button type="button" variant="outline" className="mt-4" onClick={clear}>Xóa bộ lọc</Button></div> }
function numberParam(value: string | null) { if (!value) return undefined; const number = Number(value); return Number.isFinite(number) ? number : undefined }

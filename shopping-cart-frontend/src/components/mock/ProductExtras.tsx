import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Star } from 'lucide-react'
import ProductImage from '@/components/product/ProductImage'
import { Button } from '@/components/ui/Button'
import { useAppAuth } from '@/contexts/AuthContext'
import { useCreateReview, useReviews } from '@/hooks/useMock'
import type { ProductExtras } from '@/types/mock'
import { cn } from '@/utils/cn'
import { DemoBadge, ErrorLine, shortDate } from './MockPrimitives'

// The mock API has no real photos, so extra "views" re-crop the product image.
const crops = ['', 'scale-110 object-[15%_50%]', 'scale-150 object-center', 'scale-125 object-[85%_85%]']

export function ProductGallery({ src, alt, extras }: { src?: string; alt: string; extras?: ProductExtras }) {
  const [active, setActive] = useState(0)
  const views = extras?.gallery ?? []
  return (
    <div>
      <div className="aspect-square overflow-hidden rounded-card bg-[#EEF0EC]"><ProductImage src={src} alt={alt} className={cn('h-full w-full object-cover transition duration-200', crops[active] ?? '')} /></div>
      {views.length > 0 && (
        <div className="mt-3">
          <div className="flex gap-2" role="group" aria-label="Ảnh sản phẩm">
            {views.map((view, index) => (
              <button key={view.id} type="button" aria-label={view.label} aria-pressed={active === index} onClick={() => setActive(index)} className={cn('focus-ring h-16 w-16 flex-none overflow-hidden rounded-md border-2 bg-[#EEF0EC]', active === index ? 'border-primary-600' : 'border-line')}>
                <ProductImage src={src} alt="" className={cn('h-full w-full object-cover', crops[index] ?? '')} />
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-muted">{views[active]?.label} · ảnh minh hoạ <DemoBadge /></p>
        </div>
      )}
    </div>
  )
}

export function ProductOptions({ extras, color, setColor, size, setSize }: { extras: ProductExtras; color: string; setColor: (id: string) => void; size: string; setSize: (value: string) => void }) {
  const current = extras.colors.find((item) => item.id === color)
  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 flex items-center gap-2 font-semibold">Màu sắc: <span className="font-normal text-muted">{current?.label ?? 'Chọn màu'}</span> <DemoBadge /></p>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Màu sắc">
          {extras.colors.map((item) => (
            <button key={item.id} type="button" aria-pressed={color === item.id} onClick={() => setColor(item.id)} className={cn('focus-ring flex min-h-11 items-center gap-2 rounded-md border-2 px-3 text-sm font-medium', color === item.id ? 'border-primary-600 bg-primary-50 text-primary-800' : 'border-line bg-white hover:border-slate-300')}>
              <span className="h-4 w-4 rounded-full border border-line" style={{ backgroundColor: item.hex }} aria-hidden="true" />{item.label}
              {item.priceDelta > 0 && <span className="text-xs text-muted">+{new Intl.NumberFormat('vi-VN').format(item.priceDelta)}₫</span>}
            </button>
          ))}
        </div>
        {current && <p className="mt-2 text-xs text-muted">Còn {current.stock} sản phẩm ở màu này</p>}
      </div>
      {extras.sizes.length > 0 && (
        <div>
          <p className="mb-2 font-semibold">Kích cỡ</p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Kích cỡ">
            {extras.sizes.map((item) => <button key={item} type="button" aria-pressed={size === item} onClick={() => setSize(item)} className={cn('focus-ring min-h-11 min-w-11 rounded-md border-2 px-3 text-sm font-medium', size === item ? 'border-primary-600 bg-primary-50 text-primary-800' : 'border-line bg-white hover:border-slate-300')}>{item}</button>)}
          </div>
        </div>
      )}
    </div>
  )
}

function Stars({ value, className }: { value: number; className?: string }) {
  return <span className={cn('inline-flex', className)} role="img" aria-label={`${value} trên 5 sao`}>{[1, 2, 3, 4, 5].map((n) => <Star key={n} className={cn('h-4 w-4', n <= Math.round(value) ? 'fill-warning text-warning' : 'text-slate-300')} aria-hidden="true" />)}</span>
}

export function ReviewsSection({ productId }: { productId: string }) {
  const auth = useAppAuth()
  const reviews = useReviews(productId)
  const create = useCreateReview(productId)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')

  if (!auth.isAuthenticated) {
    return <section className="border-t border-line py-8"><h2 className="section-title">Đánh giá sản phẩm</h2><p className="mt-3 text-sm text-muted"><Link to="/login" className="font-semibold text-primary-600">Đăng nhập</Link> để xem và viết đánh giá.</p></section>
  }
  if (reviews.isError) return null // mock API off or unavailable: the section simply does not exist

  const data = reviews.data
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await create.mutateAsync({ rating, comment })
    setComment('')
  }
  const alreadyReviewed = data?.items.some((item) => item.mine)

  return (
    <section className="border-t border-line py-8" aria-labelledby="reviews-title">
      <div className="flex items-center gap-2"><h2 id="reviews-title" className="section-title">Đánh giá sản phẩm</h2><DemoBadge /></div>
      {!data ? <div className="mt-4 h-24 animate-pulse rounded-card bg-slate-100" aria-hidden="true" /> : (
        <div className="mt-5 grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
          <div>
            <p className="text-4xl font-bold tabular-nums">{data.summary.average.toFixed(1)}<span className="text-lg text-muted"> / 5</span></p>
            <Stars value={data.summary.average} className="mt-1" />
            <p className="mt-1 text-sm text-muted">{data.summary.count} đánh giá</p>
            <ul className="mt-4 space-y-1.5" aria-label="Phân bố số sao">
              {[5, 4, 3, 2, 1].map((star) => {
                const count = data.summary.distribution[String(star)] ?? 0
                return <li key={star} className="flex items-center gap-2 text-xs"><span className="w-6 tabular-nums">{star}★</span><span className="h-2 flex-1 overflow-hidden rounded bg-slate-100"><span className="block h-full bg-warning" style={{ width: `${data.summary.count ? (count / data.summary.count) * 100 : 0}%` }} /></span><span className="w-6 text-right tabular-nums text-muted">{count}</span></li>
              })}
            </ul>
          </div>
          <div>
            {!alreadyReviewed && (
              <form onSubmit={submit} className="mb-6 space-y-3 rounded-card border border-line bg-white p-4">
                <fieldset><legend className="text-sm font-semibold">Đánh giá của bạn</legend>
                  <div className="mt-2 flex gap-1" role="radiogroup" aria-label="Số sao">
                    {[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} sao`} onClick={() => setRating(n)} className="focus-ring flex h-11 w-11 items-center justify-center rounded-md"><Star className={cn('h-6 w-6', n <= rating ? 'fill-warning text-warning' : 'text-slate-300')} aria-hidden="true" /></button>)}
                  </div>
                </fieldset>
                <label className="block text-sm font-semibold"><span className="sr-only">Nhận xét</span><textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} minLength={5} maxLength={500} required placeholder="Chia sẻ trải nghiệm của bạn (5–500 ký tự)" className="focus-ring w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                {create.error && <ErrorLine error={create.error} />}
                <Button type="submit" loading={create.isPending}>Gửi đánh giá</Button>
              </form>
            )}
            <ul className="divide-y divide-line">
              {data.items.map((review) => (
                <li key={review.id} className="py-4 first:pt-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm"><Stars value={review.rating} /><strong>{review.author}</strong>{review.mine && <span className="rounded bg-primary-100 px-1.5 py-0.5 text-xs font-semibold text-primary-800">Của bạn</span>}{review.verified && <span className="text-xs text-primary-700">Đã mua hàng</span>}<time dateTime={review.createdAt} className="ml-auto text-xs text-muted">{shortDate(review.createdAt)}</time></div>
                  <p className="mt-2 text-sm leading-6">{review.comment}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  )
}

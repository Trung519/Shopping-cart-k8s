import { useState } from 'react'
import { BarChart, FunnelBars, ShareBars } from '@/components/mock/Charts'
import { ErrorLine, MockPage, SkeletonRows, StatCard, dayLabel, vnd } from '@/components/mock/MockPrimitives'
import { useAdminAnalytics } from '@/hooks/useMock'
import { cn } from '@/utils/cn'

const ranges = [{ value: '7d', label: '7 ngày' }, { value: '30d', label: '30 ngày' }, { value: '90d', label: '90 ngày' }] as const

export default function AdminAnalyticsPage() {
  const [range, setRange] = useState<'7d' | '30d' | '90d'>('7d')
  const analytics = useAdminAnalytics(range)
  const data = analytics.data
  return (
    <MockPage
      title="Phân tích"
      description="Doanh thu, đơn hàng và phễu chuyển đổi toàn sàn."
      actions={
        <div role="group" aria-label="Khoảng thời gian" className="inline-flex overflow-hidden rounded-md border border-line">
          {ranges.map((r) => <button key={r.value} type="button" aria-pressed={range === r.value} onClick={() => setRange(r.value)} className={cn('focus-ring min-h-11 px-4 text-sm font-semibold', range === r.value ? 'bg-ink text-white' : 'bg-white text-muted hover:text-ink')}>{r.label}</button>)}
        </div>
      }
    >
      {analytics.isLoading ? <SkeletonRows /> : analytics.isError || !data ? <ErrorLine error={analytics.error} /> : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="GMV" value={vnd(data.kpis.gmv)} />
            <StatCard label="Đơn hàng" value={new Intl.NumberFormat('vi-VN').format(data.kpis.orders)} />
            <StatCard label="Giá trị đơn trung bình" value={vnd(data.kpis.aov)} />
            <StatCard label="Tỉ lệ chuyển đổi" value={`${(data.kpis.conversion * 100).toFixed(1)}%`} hint={`${data.kpis.newSellers} seller mới`} />
          </div>
          <section className="surface-card p-5"><h2 className="mb-4 text-lg font-bold">GMV theo ngày</h2><BarChart label={`GMV ${data.range} ngày gần nhất`} data={data.series.map((p) => ({ label: dayLabel(p.date), value: p.gmv }))} /></section>
          <div className="grid gap-6 xl:grid-cols-2">
            <section className="surface-card p-5"><h2 className="mb-4 text-lg font-bold">Phễu chuyển đổi</h2><FunnelBars steps={data.funnel} /></section>
            <section className="surface-card p-5"><h2 className="mb-4 text-lg font-bold">Danh mục bán chạy</h2><ShareBars items={data.categories} /></section>
          </div>
        </div>
      )}
    </MockPage>
  )
}

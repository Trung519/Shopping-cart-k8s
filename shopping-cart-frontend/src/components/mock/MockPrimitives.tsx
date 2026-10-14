/* eslint-disable react-refresh/only-export-components */
import type { ReactNode } from 'react'
import { FlaskConical } from 'lucide-react'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/utils/cn'
import { useMockEnabled } from '@/hooks/useMock'

/** Marks data that comes from the BFF mock API, so nobody mistakes it for real data. */
export function DemoBadge({ className }: { className?: string }) {
  return (
    <span title="Dữ liệu giả lập từ BFF, không đi qua service thật" className={cn('inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-semibold text-warning', className)}>
      <FlaskConical className="h-3 w-3" aria-hidden="true" /> Demo
    </span>
  )
}

/** Page frame for mock-backed workspace pages: title, demo badge, and a guard for when mock is off. */
export function MockPage({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  const { enabled, loading } = useMockEnabled()
  return (
    <div>
      <div className="flex flex-col gap-3 border-b border-line pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold tracking-[-0.02em]">{title}</h1><DemoBadge /></div>
          {description && <p className="mt-1 text-sm text-muted">{description}</p>}
        </div>
        {actions}
      </div>
      <div className="mt-6">
        {loading ? <div className="flex justify-center py-16"><LoadingSpinner /></div> : enabled ? children : <MockDisabled />}
      </div>
    </div>
  )
}

export function MockDisabled() {
  return (
    <div role="status" className="rounded-card border border-dashed border-line bg-ground p-8 text-center">
      <FlaskConical className="mx-auto h-8 w-8 text-muted" aria-hidden="true" />
      <h2 className="mt-3 font-bold">Tính năng demo chưa được bật</h2>
      <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-muted">BFF đang chạy với <code className="rounded bg-white px-1">MOCK_API_ENABLED=false</code> hoặc phiên bản chưa có API giả lập.</p>
    </div>
  )
}

const tones = {
  green: 'bg-primary-100 text-primary-800',
  amber: 'bg-warning-soft text-warning',
  red: 'bg-danger-soft text-danger',
  gray: 'bg-slate-100 text-slate-700',
  blue: 'bg-sky-100 text-sky-800',
} as const

const statusTone: Record<string, keyof typeof tones> = {
  NEW: 'amber', CONFIRMED: 'blue', PACKED: 'blue', SHIPPED: 'blue', DELIVERED: 'green', CANCELLED: 'red',
  REQUESTED: 'amber', APPROVED: 'blue', REJECTED: 'red', REFUNDED: 'green',
  ACTIVE: 'green', PAUSED: 'gray', PENDING: 'amber', PAID: 'green', PROCESSING: 'amber', COMPLETED: 'green',
}
const statusLabel: Record<string, string> = {
  NEW: 'Mới', CONFIRMED: 'Đã xác nhận', PACKED: 'Đã đóng gói', SHIPPED: 'Đang giao', DELIVERED: 'Đã giao', CANCELLED: 'Đã huỷ',
  REQUESTED: 'Chờ duyệt', APPROVED: 'Đã duyệt', REJECTED: 'Từ chối', REFUNDED: 'Đã hoàn tiền',
  ACTIVE: 'Đang chạy', PAUSED: 'Tạm dừng', PENDING: 'Chờ xử lý', PAID: 'Đã thanh toán', PROCESSING: 'Đang xử lý', COMPLETED: 'Hoàn tất',
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={cn('inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold', tones[statusTone[status] ?? 'gray'])}>{statusLabel[status] ?? status}</span>
}

export function StatCard({ label, value, hint, tone = 'default' }: { label: string; value: string; hint?: string; tone?: 'default' | 'warn' }) {
  return (
    <div className={cn('surface-card p-4', tone === 'warn' && 'border-warning')}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 text-2xl font-bold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  )
}

export function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null
  return <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">{error instanceof Error ? error.message : 'Có lỗi xảy ra'}</p>
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return <div className="space-y-3" aria-hidden="true">{Array.from({ length: rows }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-card bg-slate-100" />)}</div>
}

export function EmptyLine({ children }: { children: ReactNode }) {
  return <p className="rounded-card border border-dashed border-line bg-ground px-4 py-10 text-center text-sm text-muted">{children}</p>
}

export const vnd = (value: number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value)
export const shortDate = (value: string) => new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
export const dayLabel = (value: string) => new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' }).format(new Date(value))

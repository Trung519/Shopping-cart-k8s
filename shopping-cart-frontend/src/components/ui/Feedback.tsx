import type { ReactNode } from 'react'
import { AlertCircle, Inbox } from 'lucide-react'
import { cn } from '@/utils/cn'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-lg bg-slate-200', className)} />
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="flex min-h-64 flex-col items-center justify-center rounded-card border border-dashed border-slate-300 bg-slate-50 p-8 text-center"><span className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-primary-500 shadow-soft"><Inbox className="h-7 w-7" /></span><h2 className="mt-4 text-lg font-extrabold text-ink">{title}</h2><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>{action && <div className="mt-5">{action}</div>}</div>
}

export function ErrorState({ title = 'Không thể tải dữ liệu', description = 'Vui lòng thử lại sau.' }: { title?: string; description?: string }) {
  return <div role="alert" className="flex items-start gap-3 rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-800"><AlertCircle className="mt-0.5 h-5 w-5 flex-none" /><div><p className="font-bold">{title}</p><p className="mt-1 leading-6">{description}</p></div></div>
}

export function Toast({ title, description, tone = 'default' }: { title: string; description?: string; tone?: 'default' | 'success' | 'error' }) {
  const tones = { default: 'border-primary-200 bg-white', success: 'border-emerald/30 bg-white', error: 'border-red-200 bg-white' }
  return <div role="status" className={cn('rounded-card border p-4 shadow-lift', tones[tone])}><p className="text-sm font-bold text-ink">{title}</p>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>
}

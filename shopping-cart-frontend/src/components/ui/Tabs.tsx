import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export interface TabItem { id: string; label: string; content: ReactNode }

export function Tabs({ items, activeId, onChange }: { items: TabItem[]; activeId: string; onChange: (id: string) => void }) {
  const active = items.find((item) => item.id === activeId) ?? items[0]
  return <div><div className="flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">{items.map((item) => <button key={item.id} type="button" role="tab" aria-selected={item.id === active?.id} onClick={() => onChange(item.id)} className={cn('focus-ring min-h-11 whitespace-nowrap border-b-2 px-4 text-sm font-semibold transition', item.id === active?.id ? 'border-primary-600 text-primary-700' : 'border-transparent text-slate-500 hover:text-ink')}>{item.label}</button>)}</div><div className="pt-5" role="tabpanel">{active?.content}</div></div>
}

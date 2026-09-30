import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-[80] grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={title}><button type="button" aria-label="Đóng hộp thoại" className="absolute inset-0 bg-ink/50" onClick={onClose} /><section className="relative w-full max-w-lg rounded-panel bg-white p-6 shadow-lift"><div className="flex items-start justify-between gap-4"><h2 className="text-xl font-extrabold text-ink">{title}</h2><button type="button" onClick={onClose} className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label="Đóng"><X className="h-5 w-5" /></button></div><div className="mt-5">{children}</div></section></div>
}

export function Drawer({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label={title}><button type="button" aria-label="Đóng panel" className="absolute inset-0 bg-ink/50" onClick={onClose} /><section className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto bg-white p-6 shadow-lift"><div className="flex items-center justify-between"><h2 className="text-xl font-extrabold text-ink">{title}</h2><button type="button" onClick={onClose} className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label="Đóng"><X className="h-5 w-5" /></button></div><div className="mt-6">{children}</div></section></div>
}

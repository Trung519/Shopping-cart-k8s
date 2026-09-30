import type { ReactNode } from 'react'

export function DataTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return <div className="overflow-x-auto rounded-card border border-slate-200"><table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs font-bold uppercase tracking-[0.08em] text-slate-500"><tr>{headers.map((header) => <th key={header} className="px-4 py-3.5">{header}</th>)}</tr></thead><tbody className="divide-y divide-slate-200 bg-white">{children}</tbody></table></div>
}

export function TablePagination({ currentPage, totalPages, onPrevious, onNext }: { currentPage: number; totalPages: number; onPrevious: () => void; onNext: () => void }) {
  return <nav className="mt-4 flex items-center justify-end gap-3 text-sm" aria-label="Phân trang"><span className="text-slate-500">Trang {currentPage} / {totalPages}</span><button type="button" onClick={onPrevious} disabled={currentPage <= 1} className="focus-ring min-h-10 rounded-xl border border-slate-300 bg-white px-3 font-semibold disabled:opacity-40">Trước</button><button type="button" onClick={onNext} disabled={currentPage >= totalPages} className="focus-ring min-h-10 rounded-xl border border-slate-300 bg-white px-3 font-semibold disabled:opacity-40">Sau</button></nav>
}

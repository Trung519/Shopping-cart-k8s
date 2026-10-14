import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { DataTable } from '@/components/ui/DataTable'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, shortDate } from '@/components/mock/MockPrimitives'
import { useAdminAudit } from '@/hooks/useMock'

export default function AdminAuditPage() {
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), 300) // debounce typing
    return () => window.clearTimeout(timer)
  }, [input])
  const audit = useAdminAudit(query || undefined)

  return (
    <MockPage title="Nhật ký kiểm toán" description="Các thao tác quản trị và vận hành, mới nhất ở trên cùng.">
      <div className="relative mb-4 max-w-md">
        <label htmlFor="audit-q" className="sr-only">Tìm trong nhật ký</label>
        <Search className="pointer-events-none absolute left-3 top-3 h-5 w-5 text-muted" aria-hidden="true" />
        <input id="audit-q" type="search" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Tìm theo người thực hiện, hành động, đối tượng" className="focus-ring h-11 w-full rounded-md border border-slate-300 pl-10 pr-3 text-sm" />
      </div>
      {audit.isLoading ? <SkeletonRows /> : audit.isError ? <ErrorLine error={audit.error} /> : audit.data?.length === 0 ? <EmptyLine>Không có bản ghi phù hợp.</EmptyLine> : (
        <DataTable headers={['Thời gian', 'Người thực hiện', 'Hành động', 'Đối tượng']}>
          {audit.data?.map((entry) => (
            <tr key={entry.id}>
              <td className="whitespace-nowrap px-4 py-3 text-muted">{shortDate(entry.at)}</td>
              <td className="px-4 py-3 font-medium">{entry.actor}</td>
              <td className="px-4 py-3"><code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{entry.action}</code></td>
              <td className="px-4 py-3 text-muted">{entry.target}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </MockPage>
  )
}

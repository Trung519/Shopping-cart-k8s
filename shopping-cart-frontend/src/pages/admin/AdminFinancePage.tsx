import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { ErrorLine, MockPage, SkeletonRows, StatCard, StatusBadge, shortDate, vnd } from '@/components/mock/MockPrimitives'
import { useAdminApproveSettlement, useAdminFinance } from '@/hooks/useMock'

export default function AdminFinancePage() {
  const finance = useAdminFinance()
  const approve = useAdminApproveSettlement()
  return (
    <MockPage title="Thanh toán & đối soát" description="Duyệt kỳ đối soát và chi trả cho người bán.">
      {finance.isLoading ? <SkeletonRows /> : finance.isError || !finance.data ? <ErrorLine error={finance.error} /> : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Tổng doanh thu đối soát" value={vnd(finance.data.totals.gross)} />
            <StatCard label="Hoa hồng sàn" value={vnd(finance.data.totals.commission)} />
            <StatCard label="Chờ chi trả" value={vnd(finance.data.totals.pendingPayout)} tone={finance.data.totals.pendingPayout > 0 ? 'warn' : 'default'} />
          </div>
          {approve.error && <ErrorLine error={approve.error} />}
          <DataTable headers={['Kỳ', 'Gian hàng', 'Doanh thu', 'Hoa hồng', 'Thực nhận', 'Trạng thái', '']}>
            {finance.data.settlements.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-3">{s.period}</td>
                <td className="px-4 py-3 font-medium">{s.shop}</td>
                <td className="px-4 py-3 tabular-nums">{vnd(s.gross)}</td>
                <td className="px-4 py-3 tabular-nums text-muted">{vnd(s.commission)}</td>
                <td className="px-4 py-3 font-semibold tabular-nums">{vnd(s.net)}</td>
                <td className="px-4 py-3"><StatusBadge status={s.status} />{s.paidAt && <span className="ml-2 text-xs text-muted">{shortDate(s.paidAt)}</span>}</td>
                <td className="px-4 py-3 text-right">{s.status === 'PENDING' && <Button type="button" size="sm" loading={approve.isPending && approve.variables === s.id} onClick={() => approve.mutate(s.id)}>Duyệt chi</Button>}</td>
              </tr>
            ))}
          </DataTable>
        </div>
      )}
    </MockPage>
  )
}

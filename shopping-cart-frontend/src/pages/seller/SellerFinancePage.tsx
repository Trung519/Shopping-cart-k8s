import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { ErrorLine, MockPage, SkeletonRows, StatCard, StatusBadge, shortDate, vnd } from '@/components/mock/MockPrimitives'
import { useSellerFinance, useSellerPayout } from '@/hooks/useMock'

const txLabel: Record<string, string> = { SALE: 'Doanh thu đơn', COMMISSION: 'Hoa hồng sàn', REFUND: 'Hoàn tiền' }

export default function SellerFinancePage() {
  const finance = useSellerFinance()
  const payout = useSellerPayout()
  const [amount, setAmount] = useState('1000000')
  const value = Number(amount)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await payout.mutateAsync(value)
  }

  return (
    <MockPage title="Tài chính" description="Số dư, đối soát và rút tiền. Lệnh rút được xử lý giả lập trong vài giây.">
      {finance.isLoading ? <SkeletonRows /> : finance.isError || !finance.data ? <ErrorLine error={finance.error} /> : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Số dư khả dụng" value={vnd(finance.data.availableBalance)} />
            <StatCard label="Đang chờ đối soát" value={vnd(finance.data.pendingBalance)} hint="Về số dư sau khi đơn giao thành công" />
            <StatCard label="Phí hoa hồng" value={`${Math.round(finance.data.commissionRate * 100)}%`} hint="Trên giá trị mỗi đơn" />
          </div>

          <form onSubmit={submit} className="surface-card flex flex-wrap items-end gap-3 p-4">
            <label className="space-y-1.5 text-sm font-semibold"><span>Số tiền muốn rút (₫)</span>
              <input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} className="focus-ring block h-11 w-48 rounded-md border border-slate-300 px-3 tabular-nums" />
            </label>
            <Button type="submit" loading={payout.isPending} disabled={!Number.isInteger(value) || value <= 0}>Rút tiền</Button>
            {payout.isSuccess && !payout.isPending && <p role="status" className="text-sm text-primary-700">Đã tạo lệnh rút, đang xử lý…</p>}
            {payout.error && <div className="basis-full"><ErrorLine error={payout.error} /></div>}
          </form>

          <section><h2 className="mb-3 text-lg font-bold">Lệnh rút tiền</h2>
            <DataTable headers={['Mã lệnh', 'Số tiền', 'Thời gian', 'Trạng thái']}>
              {finance.data.payouts.map((p) => <tr key={p.id}><td className="px-4 py-3 font-mono text-xs">{p.id}</td><td className="px-4 py-3 tabular-nums">{vnd(p.amount)}</td><td className="px-4 py-3 text-muted">{shortDate(p.createdAt)}</td><td className="px-4 py-3"><StatusBadge status={p.status} /></td></tr>)}
            </DataTable>
          </section>

          <section><h2 className="mb-3 text-lg font-bold">Giao dịch gần đây</h2>
            <DataTable headers={['Mã', 'Loại', 'Đơn', 'Thời gian', 'Số tiền']}>
              {finance.data.transactions.map((tx) => <tr key={tx.id}><td className="px-4 py-3 font-mono text-xs">{tx.id}</td><td className="px-4 py-3">{txLabel[tx.type] ?? tx.type}</td><td className="px-4 py-3 text-muted">{tx.ref}</td><td className="px-4 py-3 text-muted">{shortDate(tx.at)}</td><td className={`px-4 py-3 text-right tabular-nums ${tx.amount < 0 ? 'text-danger' : 'text-primary-700'}`}>{vnd(tx.amount)}</td></tr>)}
            </DataTable>
          </section>
        </div>
      )}
    </MockPage>
  )
}

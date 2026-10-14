import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { DataTable } from '@/components/ui/DataTable'
import { ErrorLine, MockPage, SkeletonRows } from '@/components/mock/MockPrimitives'
import { useSellerInventory, useSellerSetStock } from '@/hooks/useMock'
import type { InventoryItem } from '@/types/mock'

export default function SellerInventoryPage() {
  const inventory = useSellerInventory()
  const lowCount = inventory.data?.filter((item) => item.low).length ?? 0
  return (
    <MockPage title="Kho hàng" description="Theo dõi tồn kho, hàng đang giữ chỗ và cảnh báo sắp hết.">
      {lowCount > 0 && <p role="status" className="mb-4 flex items-center gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning"><AlertTriangle className="h-4 w-4" aria-hidden="true" /> {lowCount} SKU sắp hết hàng cần nhập thêm.</p>}
      {inventory.isLoading ? <SkeletonRows /> : inventory.isError ? <ErrorLine error={inventory.error} /> : (
        <DataTable headers={['SKU', 'Sản phẩm', 'Tồn kho', 'Giữ chỗ', 'Có thể bán', 'Cập nhật tồn']}>
          {inventory.data?.map((item) => <StockRow key={item.sku} item={item} />)}
        </DataTable>
      )}
    </MockPage>
  )
}

function StockRow({ item }: { item: InventoryItem }) {
  const save = useSellerSetStock()
  const [value, setValue] = useState(String(item.stock))
  const parsed = Number(value)
  const invalid = value.trim() === '' || !Number.isInteger(parsed) || parsed < 0
  return (
    <tr>
      <td className="px-4 py-3 font-mono text-xs">{item.sku}</td>
      <td className="px-4 py-3 font-medium">{item.name}</td>
      <td className={`px-4 py-3 tabular-nums ${item.low ? 'font-bold text-warning' : ''}`}>{item.stock}{item.low && <span className="ml-2 rounded bg-warning-soft px-1.5 py-0.5 text-xs">Sắp hết</span>}</td>
      <td className="px-4 py-3 tabular-nums text-muted">{item.reserved}</td>
      <td className="px-4 py-3 tabular-nums">{item.available}</td>
      <td className="px-4 py-3">
        <form className="flex items-center gap-2" onSubmit={(event) => { event.preventDefault(); if (!invalid) save.mutate({ sku: item.sku, stock: parsed }) }}>
          <label className="sr-only" htmlFor={`stock-${item.sku}`}>Tồn kho mới của {item.sku}</label>
          <input id={`stock-${item.sku}`} inputMode="numeric" value={value} onChange={(event) => setValue(event.target.value)} aria-invalid={invalid} className="focus-ring h-10 w-20 rounded-md border border-slate-300 px-2 text-right tabular-nums" />
          <Button type="submit" size="sm" variant="outline" disabled={invalid || parsed === item.stock} loading={save.isPending}>Lưu</Button>
        </form>
        {save.error && <p role="alert" className="mt-1 text-xs text-danger">{save.error.message}</p>}
      </td>
    </tr>
  )
}

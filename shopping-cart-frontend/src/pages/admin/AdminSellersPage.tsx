import { Check, Store, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useReviewSellerApplication, useSellerApplications } from '@/hooks/useSellers'
import type { SellerApplicationStatus } from '@/services/sellerService'
import { formatDateTime } from '@/utils/format'

const statusLabel: Record<SellerApplicationStatus, string> = { PENDING: 'Chờ duyệt', APPROVED: 'Đã duyệt', REJECTED: 'Từ chối', SUSPENDED: 'Tạm khóa' }

export default function AdminSellersPage() {
  const { data: applications = [], isLoading } = useSellerApplications()
  const review = useReviewSellerApplication()
  const reject = (id: string) => { const reason = window.prompt('Lý do từ chối hồ sơ'); if (reason?.trim()) review.mutate({ id, status: 'REJECTED', reason }) }
  if (isLoading) return <div className="flex min-h-72 items-center justify-center"><LoadingSpinner size="lg" /></div>
  return <div><div className="border-b pb-5"><h1 className="text-2xl font-black">Duyệt người bán</h1><p className="mt-1 text-sm text-gray-500">Kiểm tra hồ sơ trước khi cấp quyền đăng bán.</p></div>{applications.length === 0 ? <div className="flex min-h-72 flex-col items-center justify-center text-center"><Store className="h-12 w-12 text-gray-300" /><h2 className="mt-4 font-bold">Chưa có hồ sơ seller</h2><p className="mt-1 text-sm text-gray-500">Hồ sơ gửi từ Kênh người bán sẽ xuất hiện tại đây.</p></div> : <div className="mt-5 overflow-x-auto border-y bg-white"><table className="min-w-[760px] w-full text-left text-sm"><thead className="bg-gray-50 text-xs uppercase text-gray-500"><tr><th className="px-4 py-3">Gian hàng</th><th className="px-4 py-3">Mã chủ shop</th><th className="px-4 py-3">Ngày gửi</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3 text-right">Thao tác</th></tr></thead><tbody className="divide-y">{applications.map((application) => <tr key={application.id}><td className="px-4 py-4"><p className="font-bold">{application.name}</p><p className="mt-1 max-w-72 truncate text-xs text-gray-500">{application.description}</p></td><td className="px-4 py-4 font-mono text-xs">{application.ownerUserId.slice(0, 12)}</td><td className="px-4 py-4 text-gray-500">{formatDateTime(application.createdAt)}</td><td className="px-4 py-4"><span className="rounded bg-primary-50 px-2 py-1 text-xs font-semibold text-primary-700">{statusLabel[application.status]}</span></td><td className="px-4 py-4"><div className="flex justify-end gap-2">{application.status === 'PENDING' && <><Button type="button" size="sm" loading={review.isPending} onClick={() => review.mutate({ id: application.id, status: 'APPROVED' })}><Check className="mr-1 h-4 w-4" /> Duyệt</Button><Button type="button" size="sm" variant="outline" onClick={() => reject(application.id)}><X className="mr-1 h-4 w-4" /> Từ chối</Button></>}</div></td></tr>)}</tbody></table></div>}</div>
}

import { useState, type FormEvent, type ReactNode } from 'react'
import { AlertCircle, ArrowRight, CheckCircle2, ClipboardList, Clock3, Package, Store, Wallet } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useOrders } from '@/hooks/useOrders'
import { useProducts } from '@/hooks/useProducts'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useMySellerApplication, useSubmitSellerApplication } from '@/hooks/useSellers'
import { useAppAuth } from '@/contexts/AuthContext'

export default function SellerDashboardPage() {
  const { data: application, isLoading, error } = useMySellerApplication()
  if (isLoading) return <div className="flex min-h-72 items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (error) return <StatusView title="Chưa thể tải hồ sơ" text="Vui lòng thử lại sau ít phút." icon={AlertCircle} tone="danger" />
  if (!application || application.status === 'REJECTED') return <SellerOnboarding rejected={application?.status === 'REJECTED'} />
  if (application.status === 'PENDING') return <StatusView title="Hồ sơ đang được duyệt" text="Platform admin cần duyệt hồ sơ trước khi gian hàng được phép đăng bán." icon={Clock3} tone="pending" />
  if (application.status === 'SUSPENDED') return <StatusView title="Gian hàng đang tạm khóa" text="Liên hệ bộ phận vận hành để xem lý do và gửi yêu cầu mở lại." icon={AlertCircle} tone="danger" />
  return <ApprovedDashboard shopName={application.name} />
}

function SellerOnboarding({ rejected }: { rejected: boolean }) {
  const submit = useSubmitSellerApplication()
  const [form, setForm] = useState({ name: '', description: '' })
  const handleSubmit = async (event: FormEvent) => { event.preventDefault(); await submit.mutateAsync(form) }
  return <div className="max-w-3xl"><div className="border-b pb-5"><p className="text-sm font-bold uppercase text-primary-600">Bắt đầu kinh doanh</p><h1 className="mt-2 text-2xl font-black">Đăng ký gian hàng</h1><p className="mt-1 text-sm leading-6 text-gray-500">Hồ sơ sẽ chuyển sang trạng thái chờ duyệt. Người bán chưa được đăng sản phẩm trước khi admin chấp thuận.</p></div>{rejected && <p className="mt-5 rounded-md bg-primary-50 p-4 text-sm font-medium text-primary-700">Hồ sơ trước đã bị từ chối. Liên hệ vận hành để được mở lại hồ sơ.</p>}<form onSubmit={handleSubmit} className="mt-6 grid gap-4"><Field label="Tên gian hàng"><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ví dụ: Tech House" required /></Field><label className="space-y-2 text-sm font-semibold"><span>Giới thiệu gian hàng</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="focus-ring min-h-28 w-full rounded-md border px-3 py-2 text-sm" required /></label>{submit.error && <p className="text-sm text-primary-600">{submit.error.message}</p>}<div><Button type="submit" size="lg" loading={submit.isPending}>Gửi hồ sơ duyệt <ArrowRight className="ml-2 h-4 w-4" /></Button></div></form></div>
}

function ApprovedDashboard({ shopName }: { shopName: string }) {
  const { user } = useAppAuth()
  const products = useProducts({ pageSize: 100, sellerId: user?.id })
  const orders = useOrders({ pageSize: 100 })
  return <div><div className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-center sm:justify-between"><div><p className="flex items-center gap-2 text-sm font-semibold text-emerald"><CheckCircle2 className="h-4 w-4" /> Đã xác minh</p><h1 className="mt-2 text-2xl font-black">{shopName}</h1><p className="mt-1 text-sm text-gray-500">Tổng quan vận hành gian hàng hôm nay.</p></div><Link to="/seller/products/new" className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-primary-600 px-4 text-sm font-bold text-white">Thêm sản phẩm</Link></div><div className="grid gap-3 py-6 sm:grid-cols-2 xl:grid-cols-4"><Metric icon={Package} label="Sản phẩm" value={String(products.data?.totalItems ?? 0)} /><Metric icon={ClipboardList} label="Đơn mới" value={String(orders.data?.totalItems ?? 0)} /><Metric icon={Wallet} label="Doanh thu" value="0 ₫" /><Metric icon={Store} label="Điểm vận hành" value="98/100" /></div><div className="grid gap-5 xl:grid-cols-2"><section className="border-y bg-white py-5"><h2 className="px-4 text-lg font-bold">Việc cần làm</h2><div className="mt-3 divide-y"><Task label="Xác nhận đơn mới" value={orders.data?.totalItems ?? 0} /><Task label="Sản phẩm sắp hết hàng" value={products.data?.data.filter((item) => item.stock <= 10).length ?? 0} /><Task label="Yêu cầu đổi trả" value={0} /></div></section><section className="border-y bg-white py-5"><h2 className="px-4 text-lg font-bold">Hiệu quả 7 ngày</h2><div className="mt-5 grid grid-cols-3 px-4 text-center"><div><p className="text-xl font-black">0</p><p className="mt-1 text-xs text-gray-500">Lượt xem</p></div><div><p className="text-xl font-black">0%</p><p className="mt-1 text-xs text-gray-500">Chuyển đổi</p></div><div><p className="text-xl font-black">0 ₫</p><p className="mt-1 text-xs text-gray-500">GMV</p></div></div></section></div></div>
}

function StatusView({ title, text, icon: Icon, tone }: { title: string; text: string; icon: typeof Clock3; tone: 'pending' | 'danger' }) { return <div className="flex min-h-96 flex-col items-center justify-center text-center"><span className={`flex h-20 w-20 items-center justify-center rounded-full ${tone === 'pending' ? 'bg-sunflower/15 text-sunflower' : 'bg-primary-50 text-primary-600'}`}><Icon className="h-9 w-9" /></span><h1 className="mt-5 text-2xl font-black">{title}</h1><p className="mt-2 max-w-md text-sm leading-6 text-gray-500">{text}</p></div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="space-y-2 text-sm font-semibold"><span>{label}</span>{children}</label> }
function Metric({ icon: Icon, label, value }: { icon: typeof Package; label: string; value: string }) { return <div className="surface-card p-4"><div className="flex items-center justify-between"><span className="text-sm text-slate-500">{label}</span><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-500"><Icon className="h-4 w-4" /></span></div><p className="mt-3 text-2xl font-extrabold">{value}</p></div> }
function Task({ label, value }: { label: string; value: number }) { return <div className="flex items-center justify-between px-4 py-3 text-sm"><span>{label}</span><span className="rounded bg-primary-50 px-2 py-1 font-bold text-primary-700">{value}</span></div> }

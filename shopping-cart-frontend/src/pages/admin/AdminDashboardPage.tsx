import { AlertTriangle, CircleDollarSign, ClipboardList, Package, Store, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAdminOrders } from '@/hooks/useOrders'
import { useProducts } from '@/hooks/useProducts'
import { useUsers } from '@/hooks/useUsers'
import { useSellerApplications } from '@/hooks/useSellers'

export default function AdminDashboardPage() {
  const users = useUsers()
  const products = useProducts({ pageSize: 100 })
  const orders = useAdminOrders()
  const applications = useSellerApplications('PENDING')
  const pendingSellers = applications.data?.length ?? 0
  const pendingOrders = orders.data?.filter((order) => order.status === 'PENDING').length ?? 0
  return <div><div className="border-b pb-5"><p className="text-sm font-bold uppercase text-primary-600">Platform operations</p><h1 className="mt-2 text-2xl font-black">Tổng quan hệ thống</h1><p className="mt-1 text-sm text-gray-500">Theo dõi marketplace, người dùng và các hàng đợi cần xử lý.</p></div><div className="grid gap-3 py-6 sm:grid-cols-2 xl:grid-cols-4"><Metric icon={Users} label="Người dùng" value={String(users.data?.length ?? 0)} /><Metric icon={Store} label="Seller chờ duyệt" value={String(pendingSellers)} alert={pendingSellers > 0} /><Metric icon={Package} label="Sản phẩm active" value={String(products.data?.totalItems ?? 0)} /><Metric icon={ClipboardList} label="Tổng đơn" value={String(orders.data?.length ?? 0)} /></div><div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]"><section className="border-y bg-white py-5"><div className="flex items-center justify-between px-4"><h2 className="text-lg font-bold">Hàng đợi vận hành</h2><span className="text-xs text-gray-400">Mới nhất</span></div><div className="mt-3 divide-y"><Queue to="/admin/orders" label="Đơn đang chờ thanh toán" value={pendingOrders} /><Queue to="/admin/sellers" label="Hồ sơ seller cần duyệt" value={pendingSellers} /><Queue to="/admin/catalog" label="Sản phẩm cần kiểm duyệt" value={0} /><Queue to="/admin/returns" label="Tranh chấp mở" value={0} /></div></section><section className="border-y bg-white p-5"><div className="flex items-center gap-2"><CircleDollarSign className="h-5 w-5 text-emerald" /><h2 className="text-lg font-bold">Sức khỏe giao dịch</h2></div><div className="mt-5 space-y-4"><Health label="Payment success" value="100%" /><Health label="Checkout errors" value="0" /><Health label="Refund pending" value="0" /></div></section></div></div>
}
function Metric({ icon: Icon, label, value, alert }: { icon: typeof Users; label: string; value: string; alert?: boolean }) { return <div className={`surface-card p-4 ${alert ? 'border-sunflower' : ''}`}><div className="flex items-center justify-between"><span className="text-sm text-slate-500">{label}</span>{alert ? <AlertTriangle className="h-5 w-5 text-sunflower" /> : <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-500"><Icon className="h-4 w-4" /></span>}</div><p className="mt-3 text-2xl font-extrabold">{value}</p></div> }
function Queue({ to, label, value }: { to: string; label: string; value: number }) { return <Link to={to} className="flex items-center justify-between px-4 py-3 text-sm hover:bg-gray-50"><span>{label}</span><span className={`rounded px-2 py-1 font-bold ${value > 0 ? 'bg-sunflower/15 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>{value}</span></Link> }
function Health({ label, value }: { label: string; value: string }) { return <div><div className="flex items-center justify-between text-sm"><span className="text-gray-500">{label}</span><strong>{value}</strong></div><div className="mt-2 h-2 overflow-hidden rounded bg-gray-100"><div className="h-full w-full bg-emerald" /></div></div> }

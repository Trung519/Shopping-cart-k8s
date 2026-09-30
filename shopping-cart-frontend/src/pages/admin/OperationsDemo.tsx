import { useEffect, useState } from 'react'
import '../../operations.css'
import { Link, NavLink, useParams } from 'react-router-dom'
import {
  ArrowUpRight,
  Search,
  ShoppingBag,
  LayoutDashboard,
  Package,
  Users,
  Truck,
  Tags,
  Image,
  RotateCcw,
  Wallet,
  MessageSquare,
  BarChart3,
  Shield,
  Settings,
  Menu,
  X,
  Download,
  Plus,
} from 'lucide-react'

const modules = [
  ['overview', 'Tổng quan', LayoutDashboard],
  ['orders', 'Đơn hàng', ShoppingBag],
  ['products', 'Sản phẩm', Package],
  ['customers', 'Khách hàng', Users],
  ['inventory', 'Tồn kho', Truck],
  ['promotions', 'Khuyến mãi', Tags],
  ['content', 'Nội dung cửa hàng', Image],
  ['returns', 'Đổi trả', RotateCcw],
  ['finance', 'Tài chính', Wallet],
  ['support', 'Chăm sóc khách hàng', MessageSquare],
  ['analytics', 'Phân tích', BarChart3],
  ['audit', 'Nhật ký', Shield],
  ['settings', 'Thiết lập', Settings],
] as const
type Entry = {
  id: string
  title: string
  subtitle: string
  amount: number
  status: string
  note: string
}
const initial: Record<string, Entry[]> = {
  orders: [
    {
      id: 'SC-1048',
      title: 'Nguyễn Minh Anh',
      subtitle: 'Tai nghe Studio • 2 sản phẩm',
      amount: 2490000,
      status: 'Cần xử lý',
      note: 'Khách yêu cầu giao trong giờ hành chính.',
    },
    {
      id: 'SC-1047',
      title: 'Trần Hoàng Nam',
      subtitle: 'Balo Everyday • 1 sản phẩm',
      amount: 890000,
      status: 'Đang giao',
      note: 'Đã bàn giao vận chuyển.',
    },
    {
      id: 'SC-1046',
      title: 'Lê Thu Hà',
      subtitle: 'Đèn bàn Nordic • 1 sản phẩm',
      amount: 650000,
      status: 'Hoàn tất',
      note: 'Khách đã nhận hàng.',
    },
    {
      id: 'SC-1045',
      title: 'Phạm Gia Huy',
      subtitle: 'Bàn phím Air • 1 sản phẩm',
      amount: 1590000,
      status: 'Cần xử lý',
      note: 'Cần kiểm tra tồn kho trước khi xác nhận.',
    },
  ],
  products: [
    {
      id: 'PR-01',
      title: 'Tai nghe Studio',
      subtitle: 'Công nghệ / Âm thanh',
      amount: 1245000,
      status: 'Đang bán',
      note: 'Màu đen, kem. Bảo hành 12 tháng.',
    },
    {
      id: 'PR-02',
      title: 'Balo Everyday',
      subtitle: 'Phong cách sống / Túi',
      amount: 890000,
      status: 'Đang bán',
      note: 'Dung tích 20L. Có ngăn laptop.',
    },
    {
      id: 'PR-03',
      title: 'Đèn bàn Nordic',
      subtitle: 'Nhà cửa / Chiếu sáng',
      amount: 650000,
      status: 'Bản nháp',
      note: 'Cần bổ sung ảnh sản phẩm.',
    },
  ],
}
const seeds: Record<string, string[]> = {
  customers: ['Nguyễn Minh Anh', 'Trần Hoàng Nam', 'Lê Thu Hà'],
  inventory: [
    'Tai nghe Studio • Kho Hà Nội',
    'Balo Everyday • Kho TP.HCM',
    'Đèn bàn Nordic • Kho Hà Nội',
  ],
  promotions: [
    'WELCOME10 • Khách hàng mới',
    'WEEKEND • Ưu đãi cuối tuần',
    'FREESHIP • Đơn từ 500.000đ',
  ],
  content: [
    'Bộ sưu tập Everyday essentials',
    'Banner công nghệ cho mỗi ngày',
    'Bộ sưu tập Góc làm việc',
  ],
  returns: ['SC-1042 • Sản phẩm lỗi', 'SC-1038 • Đổi màu sản phẩm'],
  finance: ['Đối soát kỳ tháng 09', 'Hoàn tiền SC-1042', 'Giao dịch SC-1048'],
  support: [
    'SC-1048 • Thay đổi giờ nhận hàng',
    'SC-1042 • Hướng dẫn đổi trả',
    'PR-02 • Tư vấn kích thước',
  ],
  audit: ['Cập nhật nội dung cửa hàng', 'Xác nhận đơn SC-1048', 'Điều chỉnh tồn kho PR-01'],
  settings: ['Thông tin cửa hàng', 'Thông báo vận hành', 'Chính sách giao hàng'],
}
for (const [key, titles] of Object.entries(seeds))
  initial[key] = titles.map((title, i) => ({
    id: `${key.toUpperCase()}-${i + 1}`,
    title,
    subtitle: 'Bản ghi mẫu • ShopCart demo',
    amount: key === 'inventory' ? [24, 8, 3][i] : 0,
    status: i === 0 ? 'Cần xử lý' : 'Hoàn tất',
    note: 'Dữ liệu mô phỏng để thử giao diện. Chưa kết nối backend.',
  }))
const money = (n: number) =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(n)
const storageKey = 'shopcart-operations-demo-v1'
function readEntries(): Record<string, Entry[]> {
  try {
    const value = localStorage.getItem(storageKey)
    return value ? JSON.parse(value) : initial
  } catch {
    return initial
  }
}

export default function OperationsDemo() {
  const { section = 'overview' } = useParams()
  const [entries, setEntries] = useState(readEntries)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('Tất cả')
  const [selected, setSelected] = useState<Entry | null>(null)
  const [open, setOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const selectedID = selected?.id
  useEffect(() => {
    if (!selectedID) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelected(null)
      if (event.key !== 'Tab') return
      const controls = Array.from(
        document.querySelectorAll<HTMLElement>(
          '.ops-drawer button, .ops-drawer input, .ops-drawer select, .ops-drawer textarea'
        )
      )
      const first = controls[0],
        last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = overflow
      previous?.focus()
    }
  }, [selectedID])
  const title = modules.find(([key]) => key === section)?.[1] ?? 'Tổng quan'
  const rows = (entries[section] ?? []).filter(
    (row) =>
      `${row.title} ${row.id}`.toLowerCase().includes(search.toLowerCase()) &&
      (filter === 'Tất cả' || row.status === filter)
  )
  const save = (next: Record<string, Entry[]>) => {
    setEntries(next)
    try {
      localStorage.setItem(storageKey, JSON.stringify(next))
      setNotice('Đã lưu thay đổi trong bản demo.')
    } catch {
      setNotice('Đã cập nhật phiên này; trình duyệt không cho phép lưu cục bộ.')
    }
  }
  const exportRows = () => {
    const csv = [
      'Mã,Tên,Trạng thái,Giá trị',
      ...rows.map((row) =>
        [row.id, row.title, row.status, row.amount]
          .map(
            (value) =>
              `"${String(value)
                .replace(/^[=+@-]/, "'$&")
                .replace(/"/g, '""')}"`
          )
          .join(',')
      ),
    ].join('\n')
    const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `shopcart-demo-${section}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="ops-app">
      <a className="sr-only focus:not-sr-only" href="#ops-content">
        Đến nội dung
      </a>
      <aside className={`ops-sidebar ${open ? 'is-open' : ''}`}>
        <Link to="/demo/admin" className="ops-brand">
          <ShoppingBag />
          ShopCart<span>OS</span>
        </Link>
        <p className="ops-nav-label">KHÔNG GIAN VẬN HÀNH</p>
        <nav aria-label="Quản trị demo">
          {modules.map(([key, label, Icon]) => (
            <NavLink
              key={key}
              to={`/demo/admin/${key}`}
              onClick={() => {
                setOpen(false)
                setSearch('')
                setFilter('Tất cả')
                setSelected(null)
              }}
              className={section === key ? 'active' : ''}
            >
              <Icon size={18} />
              {label}
              {key === 'orders' && (
                <small>{entries.orders.filter((row) => row.status === 'Cần xử lý').length}</small>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="ops-sidebar-bottom">
          <span className="ops-avatar">SC</span>
          <div>
            ShopCart Studio<small>Không gian trình diễn</small>
          </div>
        </div>
      </aside>
      <div className="ops-workspace">
        <header className="ops-topbar">
          <button className="ops-menu" aria-label="Mở điều hướng" onClick={() => setOpen(!open)}>
            <Menu />
          </button>
          <span>
            Workspace <span className="text-slate-300 mx-2">/</span> <strong>{title}</strong>
          </span>
          <div className="flex items-center gap-4">
            <span className="ops-demo-tag">DEMO · Dữ liệu mẫu</span>
            <Link to="/" className="ops-store-link">
              Xem cửa hàng <ArrowUpRight size={16} />
            </Link>
          </div>
        </header>
        <main id="ops-content" className="ops-main">
          <div className="ops-heading">
            <div>
              <p className="ops-eyebrow">
                SHOPCART / {section === 'overview' ? 'BUSINESS OVERVIEW' : 'OPERATIONS'}
              </p>
              <h1>{section === 'overview' ? 'Một ngày kinh doanh hiệu quả.' : title}</h1>
              <p>
                {section === 'overview'
                  ? 'Mọi hoạt động quan trọng, trong một không gian rõ ràng.'
                  : 'Tìm nhanh thông tin. Xem chi tiết. Xử lý ngay tại đây.'}
              </p>
            </div>
            <button
              className="ops-button secondary"
              onClick={() => {
                save(initial)
                setSelected(null)
              }}
            >
              Đặt lại demo
            </button>
          </div>
          {notice && (
            <div role="status" className="ops-notice">
              {notice}
              <button aria-label="Đóng thông báo" onClick={() => setNotice('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {section === 'overview' || section === 'analytics' ? (
            <>
              <div className="ops-kpis">
                {[
                  [
                    'Giá trị đơn mẫu',
                    money(entries.orders.reduce((sum, row) => sum + row.amount, 0)),
                    'Tổng giá trị trong bộ dữ liệu demo',
                  ],
                  ['Đơn hàng', entries.orders.length, 'Xem toàn bộ đơn hàng'],
                  [
                    'Cần xử lý',
                    entries.orders.filter((row) => row.status === 'Cần xử lý').length,
                    'Ưu tiên xử lý trong hôm nay',
                  ],
                  ['Sản phẩm', entries.products.length, 'Danh mục đang quản lý'],
                ].map(([label, value, detail]) => (
                  <Link
                    to={`/demo/admin/${label === 'Sản phẩm' ? 'products' : 'orders'}`}
                    className="ops-kpi"
                    key={label}
                  >
                    <span>
                      {label}
                      <ArrowUpRight size={16} />
                    </span>
                    <strong>{value}</strong>
                    <small>{detail}</small>
                  </Link>
                ))}
              </div>
              <div className="ops-dashboard-grid">
                <section className="ops-panel">
                  <div className="ops-panel-heading">
                    <div>
                      <h2>Giá trị đơn hàng</h2>
                      <p>So sánh các đơn trong bộ dữ liệu mẫu</p>
                    </div>
                    <span className="ops-badge">VND</span>
                  </div>
                  <div className="ops-chart" aria-label="Biểu đồ giá trị đơn hàng mẫu">
                    {entries.orders.map((row) => (
                      <div key={row.id}>
                        <span>{money(row.amount)}</span>
                        <div style={{ height: `${Math.max(8, (row.amount / 2490000) * 180)}px` }} />
                        <small>{row.id}</small>
                      </div>
                    ))}
                  </div>
                </section>
                <section className="ops-focus">
                  <span className="ops-eyebrow">ƯU TIÊN HÔM NAY</span>
                  <h2>
                    Đừng để khách hàng
                    <br />
                    phải chờ đợi.
                  </h2>
                  <p>Hoàn tất những việc đang mở để giữ trải nghiệm mua sắm liền mạch.</p>
                  {[
                    ['orders', 'Xử lý đơn hàng'],
                    ['returns', 'Giải quyết đổi trả'],
                    ['support', 'Trả lời khách hàng'],
                  ].map(([key, label]) => (
                    <Link key={key} to={`/demo/admin/${key}`}>
                      {label}
                      <ArrowUpRight size={18} />
                    </Link>
                  ))}
                </section>
              </div>
              <section className="ops-panel">
                <div className="ops-panel-heading">
                  <h2>Đơn hàng gần đây</h2>
                  <Link to="/demo/admin/orders">Xem tất cả →</Link>
                </div>
                {entries.orders.map((row) => (
                  <Link className="ops-recent" to="/demo/admin/orders" key={row.id}>
                    <span className="ops-avatar">
                      {row.title.split(' ').slice(-1)[0].slice(0, 1)}
                    </span>
                    <div>
                      <strong>{row.title}</strong>
                      <small>
                        {row.id} · {row.subtitle}
                      </small>
                    </div>
                    <span className="ops-badge">{row.status}</span>
                    <strong>{money(row.amount)}</strong>
                  </Link>
                ))}
              </section>
            </>
          ) : (
            <section className="ops-panel">
              <div className="ops-toolbar">
                <label className="ops-search">
                  <Search size={18} />
                  <input
                    aria-label="Tìm bản ghi"
                    placeholder="Tìm theo tên hoặc mã…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <select
                  aria-label="Lọc trạng thái"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  {['Tất cả', ...new Set((entries[section] ?? []).map((row) => row.status))].map(
                    (value) => (
                      <option key={value}>{value}</option>
                    )
                  )}
                </select>
                <button className="ops-button secondary" onClick={exportRows}>
                  <Download size={16} />
                  Xuất CSV
                </button>
                <button
                  className="ops-button"
                  onClick={() =>
                    setSelected({
                      id: `DEMO-${Date.now()}`,
                      title: '',
                      subtitle: 'Bản ghi mẫu mới',
                      amount: 0,
                      status: 'Bản nháp',
                      note: '',
                    })
                  }
                >
                  <Plus size={16} />
                  Tạo bản nháp
                </button>
              </div>
              <div className="ops-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Bản ghi</th>
                      <th>Mã tham chiếu</th>
                      <th>Trạng thái</th>
                      <th>{section === 'inventory' ? 'Số lượng' : 'Giá trị'}</th>
                      <th>Chi tiết</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.title}</strong>
                          <small>{row.subtitle}</small>
                        </td>
                        <td>{row.id}</td>
                        <td>
                          <span
                            className={`ops-badge ${row.status === 'Cần xử lý' ? 'warning' : ''}`}
                          >
                            {row.status}
                          </span>
                        </td>
                        <td>{section === 'inventory' ? row.amount : money(row.amount)}</td>
                        <td>
                          <button
                            className="ops-button secondary"
                            onClick={() => setSelected({ ...row })}
                          >
                            Mở →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length === 0 && (
                <div className="ops-empty">
                  <Search size={28} />
                  <h2>Không tìm thấy bản ghi</h2>
                  <p>Thử thay đổi từ khóa hoặc bộ lọc trạng thái.</p>
                </div>
              )}
              <div className="ops-table-footer">
                {rows.length} bản ghi · Dữ liệu được lưu trên trình duyệt của bạn
              </div>
            </section>
          )}
          <footer className="ops-footer">
            ShopCart Operations Studio <span>Demo tương tác · Không thực hiện giao dịch thật</span>
          </footer>
        </main>
      </div>
      {selected && (
        <div className="ops-overlay" onClick={() => setSelected(null)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Chi tiết bản ghi demo"
            className="ops-drawer"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setSelected(null)
            }}
          >
            <div className="ops-panel-heading">
              <div>
                <p className="ops-eyebrow">{selected.id}</p>
                <h2>Chi tiết {title.toLowerCase()}</h2>
              </div>
              <button aria-label="Đóng chi tiết" onClick={() => setSelected(null)}>
                <X />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const existing = entries[section] ?? []
                save({
                  ...entries,
                  [section]: existing.some((row) => row.id === selected.id)
                    ? existing.map((row) => (row.id === selected.id ? selected : row))
                    : [...existing, selected],
                })
                setSelected(null)
              }}
            >
              <label>
                Tên / Tiêu đề
                <input
                  autoFocus
                  required
                  value={selected.title}
                  onChange={(e) => setSelected({ ...selected, title: e.target.value })}
                />
              </label>
              <label>
                Mô tả
                <input
                  value={selected.subtitle}
                  onChange={(e) => setSelected({ ...selected, subtitle: e.target.value })}
                />
              </label>
              <label>
                {section === 'inventory' ? 'Số lượng' : 'Giá trị (VND)'}
                <input
                  required
                  type="number"
                  min="0"
                  value={selected.amount}
                  onChange={(e) => setSelected({ ...selected, amount: Number(e.target.value) })}
                />
              </label>
              <label>
                Trạng thái
                <select
                  value={selected.status}
                  onChange={(e) => setSelected({ ...selected, status: e.target.value })}
                >
                  {['Bản nháp', 'Cần xử lý', 'Đang bán', 'Đang giao', 'Hoàn tất', 'Đã hủy'].map(
                    (status) => (
                      <option key={status}>{status}</option>
                    )
                  )}
                </select>
              </label>
              <label>
                Ghi chú nội bộ
                <textarea
                  rows={5}
                  value={selected.note}
                  onChange={(e) => setSelected({ ...selected, note: e.target.value })}
                />
              </label>
              <p className="ops-notice">Thao tác chỉ lưu dữ liệu demo trên trình duyệt.</p>
              <button className="ops-button" type="submit">
                Lưu bản demo
              </button>
            </form>
          </section>
        </div>
      )}
    </div>
  )
}

import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="market-container flex min-h-[60vh] flex-col items-center justify-center py-16 text-center">
      <span className="rounded-full bg-primary-50 px-5 py-2 text-sm font-extrabold text-primary-600">404</span>
      <h2 className="mt-5 text-2xl font-extrabold">Không tìm thấy trang</h2>
      <p className="mt-2 max-w-md text-slate-500">
        Trang bạn tìm kiếm không tồn tại hoặc đã được di chuyển.
      </p>
      <Link to="/" className="mt-8">
        <Button>
          <Home className="mr-2 h-4 w-4" />
          Về trang chủ
        </Button>
      </Link>
    </div>
  )
}

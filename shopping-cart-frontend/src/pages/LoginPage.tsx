import { Navigate, useLocation } from 'react-router-dom'
import { LockKeyhole, ShieldCheck, ShoppingBag } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { useAppAuth } from '@/contexts/AuthContext'

interface LoginLocationState {
  returnTo?: string
}

export default function LoginPage() {
  const location = useLocation()
  const auth = useAppAuth()

  const returnTo = (location.state as LoginLocationState | null)?.returnTo || '/'

  if (auth.isAuthenticated) {
    return <Navigate to={returnTo} replace />
  }

  return (
    <div className="market-container grid min-h-[72vh] items-center gap-10 py-10 lg:grid-cols-[1fr_440px]">
      <div className="hidden lg:block">
        <div className="flex h-14 w-14 items-center justify-center rounded-panel bg-primary-600 text-white shadow-soft">
          <ShoppingBag className="h-7 w-7" />
        </div>
        <p className="eyebrow mt-8">Tài khoản ShopCart</p>
        <h1 className="mt-2 max-w-xl text-4xl font-extrabold leading-tight tracking-[-0.04em] text-ink">
          Mua sắm thuận tiện, quản lý mọi đơn hàng tại một nơi
        </h1>
        <p className="mt-4 max-w-lg text-lg leading-8 text-slate-600">
          Đăng nhập để mua hàng, theo dõi vận chuyển, lưu sản phẩm yêu thích và làm việc trong Seller Center.
        </p>
        <div className="mt-8 flex items-center gap-3 text-sm font-medium text-emerald">
          <ShieldCheck className="h-5 w-5" />
          Phiên đăng nhập được bảo vệ và phân quyền theo vai trò
        </div>
      </div>
      <Card className="border-slate-200 p-2 shadow-lift">
        <CardHeader>
          <CardTitle className="text-2xl font-extrabold text-ink">Đăng nhập ShopCart</CardTitle>
          <p className="text-sm text-slate-500">Tiếp tục để mua sắm và quản lý hoạt động của bạn.</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Button type="button" className="w-full" loading={auth.isLoading} onClick={() => auth.login(returnTo)}>
              <LockKeyhole className="mr-2 h-4 w-4" />
              Tiếp tục với tài khoản ShopCart
            </Button>
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
            Bạn sẽ được chuyển tới cổng đăng nhập bảo mật. ShopCart không lưu token đăng nhập trong trình duyệt.
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

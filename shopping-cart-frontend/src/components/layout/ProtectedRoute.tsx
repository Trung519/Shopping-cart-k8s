import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAppAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

interface ProtectedRouteProps {
  children: ReactNode
  requiredRoles?: string[]
}

export default function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const auth = useAppAuth()
  const location = useLocation()

  if (auth.isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!auth.isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ returnTo: `${location.pathname}${location.search}` }}
      />
    )
  }

  // Check for required roles if specified
  if (requiredRoles && requiredRoles.length > 0) {
    const userRoles = new Set((auth.user?.roles || []).map((role) => role.toLowerCase()))
    const hasRequiredRole = requiredRoles.some((role) => userRoles.has(role.toLowerCase()))

    if (!hasRequiredRole) {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-4">
          <h2 className="text-xl font-semibold text-ink">Bạn không có quyền truy cập</h2>
          <p className="text-gray-600">Tài khoản hiện tại chưa được cấp vai trò phù hợp.</p>
        </div>
      )
    }
  }

  return <>{children}</>
}

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'
import { authService } from '@/services/authService'
import type { User } from '@/types'

interface AuthContextValue {
  isAuthenticated: boolean
  isLoading: boolean
  user: User | null
  isAdmin: boolean
  hasAnyRole: (...roles: string[]) => boolean
  login: (returnTo?: string) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true
    authService.getSession().then((currentUser) => {
      if (active) {
        setUser(currentUser)
        setIsLoading(false)
      }
    })
    const clearExpiredSession = () => setUser(null)
    window.addEventListener('shopcart:session-expired', clearExpiredSession)
    return () => {
      active = false
      window.removeEventListener('shopcart:session-expired', clearExpiredSession)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => {
      const hasAnyRole = (...roles: string[]) => {
        const normalizedRoles = new Set((user?.roles ?? []).map((role) => role.toLowerCase()))
        return roles.some((role) => normalizedRoles.has(role.toLowerCase()))
      }

      return {
        isAuthenticated: Boolean(user),
        isLoading,
        user,
        isAdmin: hasAnyRole(
          'admin',
          'catalog-admin',
          'platform-admin',
          'cart-admin',
          'user-admin',
          'seller-reviewer',
          'catalog-moderator',
          'order-operator',
          'finance-operator',
          'support-agent'
        ),
        hasAnyRole,
        login: (returnTo = '/') => {
          authService.beginLogin(returnTo)
        },
        logout: async () => {
          setIsLoading(true)
          try {
            await authService.logout()
            setUser(null)
          } finally {
            setIsLoading(false)
          }
        },
      }
    },
    [isLoading, user]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// The provider and its companion hook intentionally share this context module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAppAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAppAuth must be used inside AuthProvider')
  }
  return context
}

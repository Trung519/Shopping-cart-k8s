import { useEffect } from 'react'
import { X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Toast } from '@/components/ui/Feedback'
import { useAppAuth } from '@/contexts/AuthContext'
import { useMockEnabled } from '@/hooks/useMock'
import { MOCK_BASE } from '@/services/mockService'
import { useToastStore } from '@/stores/toastStore'
import type { MockNotification } from '@/types/mock'

/**
 * Opens one Server-Sent Events stream to the BFF mock API while a user is signed in
 * and shows each pushed notification as a toast. EventSource reconnects by itself,
 * which also covers the BFF closing the stream every five minutes.
 */
export function LiveNotifications() {
  const auth = useAppAuth()
  const { enabled } = useMockEnabled()
  const queryClient = useQueryClient()
  const push = useToastStore((state) => state.push)
  const active = enabled && auth.isAuthenticated

  useEffect(() => {
    if (!active || typeof EventSource === 'undefined') return
    const source = new EventSource(`${MOCK_BASE}/events`, { withCredentials: true })
    const onNotification = (event: MessageEvent<string>) => {
      try {
        const item = JSON.parse(event.data) as MockNotification
        push({ title: item.title, description: item.text, tone: 'default' })
        queryClient.invalidateQueries({ queryKey: ['mock', 'notifications'] })
      } catch {
        // Ignore malformed frames; the stream stays open.
      }
    }
    source.addEventListener('notification', onNotification as EventListener)
    return () => {
      source.removeEventListener('notification', onNotification as EventListener)
      source.close()
    }
  }, [active, push, queryClient])

  return null
}

export function ToastHost() {
  const toasts = useToastStore((state) => state.toasts)
  const dismiss = useToastStore((state) => state.dismiss)
  if (toasts.length === 0) return null
  return (
    <div className="fixed bottom-20 right-4 z-[90] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2 md:bottom-4" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className="relative">
          <Toast title={toast.title} description={toast.description} tone={toast.tone} />
          <button type="button" aria-label="Đóng thông báo" onClick={() => dismiss(toast.id)} className="focus-ring absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-ground"><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  )
}

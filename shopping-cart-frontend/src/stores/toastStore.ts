import { create } from 'zustand'

export interface ToastItem {
  id: number
  title: string
  description?: string
  tone: 'default' | 'success' | 'error'
}

interface ToastState {
  toasts: ToastItem[]
  push: (toast: Omit<ToastItem, 'id'>) => void
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = nextId++
    set((state) => ({ toasts: [...state.toasts.slice(-2), { ...toast, id }] }))
    setTimeout(() => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })), 5000)
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}))

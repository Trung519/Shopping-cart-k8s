import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AppliedVoucher } from '@/types/mock'

interface VoucherState {
  applied: AppliedVoucher | null
  apply: (voucher: AppliedVoucher) => void
  clear: () => void
}

/** Demo voucher chosen in the cart; it only changes what the UI displays, never the real order total. */
export const useVoucherStore = create<VoucherState>()(
  persist(
    (set) => ({ applied: null, apply: (applied) => set({ applied }), clear: () => set({ applied: null }) }),
    { name: 'shopcart-demo-voucher' },
  ),
)

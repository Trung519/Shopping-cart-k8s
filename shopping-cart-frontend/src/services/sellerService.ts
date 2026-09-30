import api from './api'

export type SellerApplicationStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'SUSPENDED'

export interface SellerApplication {
  id: string
  ownerUserId: string
  slug: string
  name: string
  description: string
  status: SellerApplicationStatus
  rejectionReason?: string
  createdAt: string
  updatedAt: string
}

const BASE_URL = '/api/v2/sellers'

export const sellerService = {
  async getMine(): Promise<SellerApplication | null> {
    const response = await api.get<{ success: boolean; data: SellerApplication } | undefined>(`${BASE_URL}/me`, {
      validateStatus: (status) => status === 200 || status === 204,
    })
    return response.status === 204 ? null : response.data?.data ?? null
  },
  async apply(input: { name: string; description: string }): Promise<SellerApplication> {
    const response = await api.post<{ success: boolean; data: SellerApplication }>(`${BASE_URL}/applications`, input)
    return response.data.data
  },
  async list(status?: SellerApplicationStatus): Promise<SellerApplication[]> {
    const response = await api.get<{ success: boolean; data: SellerApplication[] }>(`${BASE_URL}/applications`, { params: { status } })
    return response.data.data
  },
  async review(id: string, status: 'APPROVED' | 'REJECTED', reason = ''): Promise<SellerApplication> {
    const response = await api.patch<{ success: boolean; data: SellerApplication }>(`${BASE_URL}/applications/${id}`, { status, reason })
    return response.data.data
  },
}

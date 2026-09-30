import api from './api'
import { API_CONFIG } from '@/config/api'
import type { ManagedUser, ManagedUserFormInput, User } from '@/types'

export const authService = {
  beginLogin(returnTo = '/'): void {
    window.location.assign(`${API_CONFIG.AUTH_SERVICE_URL}/login?returnTo=${encodeURIComponent(returnTo)}`)
  },

  async getSession(): Promise<User | null> {
    try {
      const response = await api.get<{ success: boolean; data: User }>(`${API_CONFIG.AUTH_SERVICE_URL}/me`)
      return response.data.data
    } catch {
      return null
    }
  },

  async logout(): Promise<void> {
    const response = await api.post<{ success: boolean; data: { logoutUrl: string } }>(
      `${API_CONFIG.AUTH_SERVICE_URL}/logout`
    )
    window.location.assign(response.data.data.logoutUrl)
  },

  async listUsers(): Promise<ManagedUser[]> {
    const response = await api.get<{ success: boolean; data: ManagedUser[] }>(
      `${API_CONFIG.ACCOUNT_SERVICE_URL}/users`
    )
    return response.data.data
  },

  async createUser(input: ManagedUserFormInput): Promise<ManagedUser> {
    const response = await api.post<{ success: boolean; data: ManagedUser }>(
      `${API_CONFIG.ACCOUNT_SERVICE_URL}/users`,
      input
    )
    return response.data.data
  },

  async updateUser(id: string, input: ManagedUserFormInput): Promise<ManagedUser> {
    const payload: Record<string, unknown> = {
      username: input.username,
      name: input.name,
      email: input.email,
      countryId: input.countryId,
      roles: input.roles,
    }

    if (input.password.trim() !== '') {
      payload.password = input.password
    }

    const response = await api.put<{ success: boolean; data: ManagedUser }>(
      `${API_CONFIG.ACCOUNT_SERVICE_URL}/users/${id}`,
      payload
    )
    return response.data.data
  },

  async deleteUser(id: string): Promise<void> {
    await api.delete(`${API_CONFIG.ACCOUNT_SERVICE_URL}/users/${id}`)
  },
}

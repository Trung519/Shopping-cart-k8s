import axios, { type AxiosError, type AxiosInstance } from 'axios'
import type { ApiError } from '@/types'

// Create axios instance
const api: AxiosInstance = axios.create({
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('shopcart:session-expired'))
    }

    const message = error.response?.data?.message || error.message || 'An error occurred'
    return Promise.reject(new Error(message))
  }
)

export default api

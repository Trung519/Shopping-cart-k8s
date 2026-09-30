export const API_CONFIG = {
  AUTH_SERVICE_URL: import.meta.env.VITE_AUTH_SERVICE_URL || '/api/v2/auth',
  ACCOUNT_SERVICE_URL: import.meta.env.VITE_ACCOUNT_SERVICE_URL || '/api/v2/accounts',
  ORDER_SERVICE_URL: import.meta.env.VITE_ORDER_SERVICE_URL || '/api/v2/orders',
  PRODUCT_SERVICE_URL: import.meta.env.VITE_PRODUCT_SERVICE_URL || '/api/v2/products',
  CART_SERVICE_URL: import.meta.env.VITE_CART_SERVICE_URL || '/api/v2/cart',
} as const

export const ENDPOINTS = {
  // Product endpoints
  PRODUCTS: `${API_CONFIG.PRODUCT_SERVICE_URL}`,
  PRODUCT_BY_ID: (id: string) => `${API_CONFIG.PRODUCT_SERVICE_URL}/${id}`,
  PRODUCT_CATEGORIES: `${API_CONFIG.PRODUCT_SERVICE_URL}/categories`,

  // Cart endpoints
  CART: `${API_CONFIG.CART_SERVICE_URL}`,
  CART_ITEMS: `${API_CONFIG.CART_SERVICE_URL}/items`,
  CART_ITEM_BY_ID: (id: string) => `${API_CONFIG.CART_SERVICE_URL}/items/${id}`,
  CART_CHECKOUT: `${API_CONFIG.CART_SERVICE_URL}/checkout`,

  // Order endpoints
  ORDERS: `${API_CONFIG.ORDER_SERVICE_URL}`,
  ORDER_BY_ID: (id: string) => `${API_CONFIG.ORDER_SERVICE_URL}/${id}`,
} as const

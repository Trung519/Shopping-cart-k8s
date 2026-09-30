// Product types
export interface Product {
  id: string
  sku: string
  name: string
  description: string
  price: number
  currency: string
  category: string
  imageUrl?: string
  stock: number
  isActive: boolean
  createdAt: string
  updatedAt: string
  brand?: string
  shopName?: string
  sellerId?: string
  ratingAverage?: number
  ratingCount?: number
  soldCount?: number
  originalPrice?: number
}

export interface ProductFormInput {
  sku: string
  name: string
  description: string
  price: number
  currency: string
  quantity: number
  category: string
  imageUrl: string
}

export interface ProductCategory {
  id: number
  slug: string
  name: string
  sortOrder: number
  isActive: boolean
}

// Cart types
export interface CartItem {
  id: string
  productId: string
  name: string
  quantity: number
  unitPrice: number
  subTotal: number
  variantId?: string
  sku?: string
  imageUrl?: string
  category?: string
  sellerId?: string
  shopName?: string
}

export interface Cart {
  id: string
  customerId: string
  items: CartItem[]
  totalAmount: number
  currency: string
  createdAt: string
  updatedAt: string
  expiresAt: string
}

export interface AddToCartRequest {
  productId: string
  quantity: number
  variantId?: string
  name?: string
  unitPrice?: number
}

export interface UpdateCartItemRequest {
  quantity: number
}

// Order types
export interface OrderItem {
  id: string
  productId: string
  name: string
  quantity: number
  unitPrice: number
  subTotal: number
}

export interface Order {
  id: string
  customerId: string
  items: OrderItem[]
  totalAmount: number
  currency: string
  status: OrderStatus
  shippingAddress?: Address
  createdAt: string
  updatedAt: string
}

export type OrderStatus =
  | 'PENDING'
  | 'PAID'
  | 'CONFIRMED'
  | 'PROCESSING'
  | 'SHIPPED'
  | 'COMPLETED'
  | 'DELIVERED'
  | 'CANCELLED'

export interface Address {
  street: string
  city: string
  state: string
  postalCode: string
  country: string
}

export interface CheckoutAddress extends Address {
  fullName: string
  phone: string
  district: string
  ward: string
  province?: string
}

// API Response types
export interface ApiError {
  message: string
  code?: string
  details?: Record<string, string>
}

export interface PaginatedResponse<T> {
  data: T[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

// User types
export interface User {
  id: string
  username: string
  email: string
  name: string
  roles: string[]
}

export interface ManagedUser extends User {
  countryId: string
}

export interface ManagedUserFormInput {
  username: string
  password: string
  name: string
  email: string
  countryId: string
  roles: string[]
}

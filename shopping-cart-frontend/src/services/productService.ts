import api from './api'
import { ENDPOINTS } from '@/config/api'
import type { Product, ProductCategory, PaginatedResponse, ProductFormInput } from '@/types'

export interface GetProductsParams {
  page?: number
  pageSize?: number
  category?: string
  search?: string
  minPrice?: number
  maxPrice?: number
  sort?: 'newest' | 'price_asc' | 'price_desc' | 'name'
  sellerId?: string
}

interface CatalogProductResponse {
  id: string
  sku: string
  name: string
  description: string
  price: number | string
  currency: string
  category: string
  image_url?: string | null
  is_active?: boolean
  stock?: number
  quantity?: number
  created_at?: string
  updated_at?: string
  brand?: string | null
  shop_name?: string | null
  seller_id?: string | null
  rating_average?: number | string | null
  rating_count?: number | null
  sold_count?: number | null
  original_price?: number | string | null
}

interface CatalogPaginatedResponse {
  items: CatalogProductResponse[]
  page: number
  page_size: number
  total: number
  pages: number
}

function isFrontendProduct(product: CatalogProductResponse | Product): product is Product {
  return 'imageUrl' in product && 'stock' in product && 'createdAt' in product && 'updatedAt' in product
}

function normalizeProduct(product: CatalogProductResponse | Product): Product {
  if (isFrontendProduct(product)) {
    return product
  }

  return {
    id: product.id,
    sku: product.sku,
    name: product.name,
    description: product.description ?? '',
    price: Number(product.price),
    currency: product.currency,
    category: product.category ?? '',
    imageUrl: product.image_url ?? undefined,
    stock: product.stock ?? product.quantity ?? 0,
    isActive: product.is_active ?? true,
    createdAt: product.created_at ?? '',
    updatedAt: product.updated_at ?? '',
    brand: product.brand ?? undefined,
    shopName: product.shop_name ?? undefined,
    sellerId: product.seller_id ?? undefined,
    ratingAverage: product.rating_average == null ? undefined : Number(product.rating_average),
    ratingCount: product.rating_count ?? undefined,
    soldCount: product.sold_count ?? undefined,
    originalPrice: product.original_price == null ? undefined : Number(product.original_price),
  }
}

function normalizePaginatedProducts(
  response: CatalogPaginatedResponse | PaginatedResponse<Product>
): PaginatedResponse<Product> {
  if ('data' in response) {
    return response
  }

  return {
    data: response.items.map(normalizeProduct),
    page: response.page,
    pageSize: response.page_size,
    totalItems: response.total,
    totalPages: response.pages,
  }
}

export const productService = {
  async getProducts(params: GetProductsParams = {}): Promise<PaginatedResponse<Product>> {
    const { page = 1, pageSize = 12, category, search, minPrice, maxPrice, sort = 'newest', sellerId } = params
    const queryParams = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort,
    })

    if (category) queryParams.append('category', category)
    if (search) queryParams.append('search', search)
    if (minPrice != null) queryParams.append('min_price', String(minPrice))
    if (maxPrice != null) queryParams.append('max_price', String(maxPrice))
    if (sellerId) queryParams.append('seller_id', sellerId)

    const response = await api.get<CatalogPaginatedResponse | PaginatedResponse<Product>>(
      `${ENDPOINTS.PRODUCTS}?${queryParams}`
    )
    return normalizePaginatedProducts(response.data)
  },

  async getProductById(id: string): Promise<Product> {
    const response = await api.get<CatalogProductResponse | Product>(ENDPOINTS.PRODUCT_BY_ID(id))
    return normalizeProduct(response.data)
  },

  async getCategories(includeInactive = false): Promise<ProductCategory[]> {
    const response = await api.get<Array<{ id: number; slug: string; name: string; sort_order: number; is_active: boolean }>>(
      `${ENDPOINTS.PRODUCT_CATEGORIES}${includeInactive ? '?include_inactive=true' : ''}`
    )
    return response.data.map((category) => ({
      id: category.id,
      slug: category.slug,
      name: category.name,
      sortOrder: category.sort_order,
      isActive: category.is_active,
    }))
  },

  async createCategory(input: { slug: string; name: string; sortOrder: number }): Promise<void> {
    await api.post(ENDPOINTS.PRODUCT_CATEGORIES, { slug: input.slug, name: input.name, sort_order: input.sortOrder })
  },

  async updateCategory(id: number, input: { name?: string; sortOrder?: number; isActive?: boolean }): Promise<void> {
    await api.patch(`${ENDPOINTS.PRODUCT_CATEGORIES}/${id}`, {
      name: input.name,
      sort_order: input.sortOrder,
      is_active: input.isActive,
    })
  },

  async deleteCategory(id: number): Promise<void> {
    await api.delete(`${ENDPOINTS.PRODUCT_CATEGORIES}/${id}`)
  },

  async createProduct(input: ProductFormInput): Promise<Product> {
    const response = await api.post<CatalogProductResponse>(ENDPOINTS.PRODUCTS, {
      sku: input.sku,
      name: input.name,
      description: input.description,
      price: input.price,
      currency: input.currency,
      quantity: input.quantity,
      category: input.category,
      image_url: input.imageUrl || null,
    })
    return normalizeProduct(response.data)
  },

  async updateProduct(id: string, input: ProductFormInput): Promise<Product> {
    const response = await api.patch<CatalogProductResponse>(ENDPOINTS.PRODUCT_BY_ID(id), {
      name: input.name,
      description: input.description,
      price: input.price,
      quantity: input.quantity,
      category: input.category,
      image_url: input.imageUrl || null,
    })
    return normalizeProduct(response.data)
  },

  async deleteProduct(id: string): Promise<void> {
    await api.delete(ENDPOINTS.PRODUCT_BY_ID(id))
  },
}

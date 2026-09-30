import { categories, products, sellers } from './fixtures'
import type { DemoProduct, Seller, Variant } from './types'

export const demoPath = (path = '') => `/demo/shop${path.startsWith('/') ? path : `/${path}`}`
export const normalizeVietnamese = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase()
export const findProduct = (id?: string) => products.find(product => product.id === id || product.slug === id)
export const productVariant = (product: DemoProduct, id?: string): Variant => product.variants.find(variant => variant.id === id) ?? product.variants[0]
export const sellerFor = (id: string): Seller => sellers.find(seller => seller.id === id) ?? sellers[0]
export const categoryLabel = (id: string) => categories.find(category => category[0] === id)?.[1] ?? id
export const imageFor = (product: DemoProduct) => product.gallery[0]

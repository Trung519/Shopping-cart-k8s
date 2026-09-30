import { Heart, Minus, Plus, ShoppingBag, Star, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { money, useBuyerDemo } from './demoStore'
import type { DemoProduct } from './types'
import { demoPath, imageFor, productVariant, sellerFor } from './utils'

export function ProductImage({ product, className = '' }: { product: DemoProduct; className?: string }) {
  const [broken, setBroken] = useState(!product.gallery[0])
  if (broken) return <div className={`shop-product-image shop-image-fallback ${className}`} aria-label={`Ảnh minh họa ${product.name}`}><ShoppingBag size={34} /><span>ShopCart</span></div>
  return <img className={`shop-product-image ${className}`} src={imageFor(product)} alt={product.name} onError={() => setBroken(true)} />
}
export function Quantity({ value, max, onChange }: { value: number; max: number; onChange: (next: number) => void }) {
  return <div className="shop-quantity" aria-label="Số lượng"><button type="button" aria-label="Giảm số lượng" disabled={value <= 1} onClick={() => onChange(value - 1)}><Minus size={16} /></button><output>{value}</output><button type="button" aria-label="Tăng số lượng" disabled={value >= max} onClick={() => onChange(value + 1)}><Plus size={16} /></button></div>
}
export function ProductCard({ product, onNeedVariant }: { product: DemoProduct; onNeedVariant?: (product: DemoProduct) => void }) {
  const { wishlist, toggleWishlist, addCart } = useBuyerDemo(); const variant = productVariant(product); const seller = sellerFor(product.sellerId); const soldOut = !product.variants.some(item => item.stock > 0)
  const add = () => { if (product.variants.length > 1) return onNeedVariant?.(product); if (!soldOut) { addCart({ productId: product.id, variantId: variant.id, quantity: 1, selected: true }) } }
  return <article className="shop-product-card">
    <div className="shop-card-image-wrap"><Link to={demoPath(`/products/${product.id}`)} aria-label={`Xem ${product.name}`}><ProductImage product={product} /></Link>{product.badge && <span className={`shop-badge ${product.badge === 'Giảm giá' ? 'deal' : ''}`}>{product.badge}</span>}<button className="shop-icon-button card-heart" type="button" aria-label="Yêu thích" aria-pressed={wishlist.includes(product.id)} onClick={() => toggleWishlist(product.id)}><Heart size={19} fill={wishlist.includes(product.id) ? 'currentColor' : 'none'} /></button></div>
    <div className="shop-card-body"><Link className="shop-product-name" to={demoPath(`/products/${product.id}`)}>{product.name}</Link><div className="shop-card-price">{money(variant.price)} {variant.originalPrice && <del>{money(variant.originalPrice)}</del>}</div>{product.rating ? <div className="shop-rating"><Star size={14} fill="currentColor" /> {product.rating.toFixed(1)} <span>({product.reviewCount})</span></div> : <div className="shop-rating shop-muted">Chưa có đánh giá</div>}<div className="shop-card-meta"><span>{seller.name}</span><span>Giao từ 30.000đ</span></div><button type="button" className="shop-button shop-button-secondary shop-card-add" disabled={soldOut} onClick={add}>{soldOut ? 'Hết hàng' : 'Thêm vào giỏ'}</button></div>
  </article>
}
export function VariantModal({ product, onClose }: { product: DemoProduct | null; onClose: () => void }) {
  const { addCart } = useBuyerDemo(); const [selected, setSelected] = useState(product?.variants.find(item => item.stock > 0)?.id); if (!product) return null; const variant = productVariant(product, selected)
  return <div className="shop-modal-backdrop" role="presentation" onMouseDown={onClose}><section className="shop-modal" role="dialog" aria-modal="true" aria-label="Chọn phiên bản" onMouseDown={event => event.stopPropagation()}><button className="shop-icon-button shop-close" onClick={onClose} aria-label="Đóng"><X size={20} /></button><h2>Chọn phiên bản</h2><p>{product.name}</p><div className="shop-variant-options">{product.variants.map(item => <button type="button" key={item.id} className={selected === item.id ? 'selected' : ''} disabled={!item.stock} onClick={() => setSelected(item.id)}>{item.label} {!item.stock && '— hết hàng'}</button>)}</div><strong>{money(variant.price)}</strong><button type="button" className="shop-button shop-button-primary shop-full" disabled={!variant.stock} onClick={() => { addCart({ productId: product.id, variantId: variant.id, quantity: 1, selected: true }); onClose() }}>Thêm vào giỏ</button></section></div>
}
export function EmptyState({ title, body, href = '/products', action = 'Khám phá sản phẩm' }: { title: string; body: string; href?: string; action?: string }) { return <div className="shop-empty"><ShoppingBag size={38} /><h2>{title}</h2><p>{body}</p><Link className="shop-button shop-button-primary" to={demoPath(href)}>{action}</Link></div> }

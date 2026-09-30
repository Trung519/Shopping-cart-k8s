import type { Address, DemoOrder, DemoProduct, Notice, Review, Seller, Voucher } from './types'

export const categories = [
  ['phone', 'Điện thoại & phụ kiện', '📱'], ['computer', 'Máy tính', '💻'], ['audio', 'Âm thanh', '🎧'], ['fashion', 'Thời trang', '👕'],
  ['home', 'Nhà cửa', '⌂'], ['book', 'Sách', '📚'], ['beauty', 'Làm đẹp', '✦'], ['sport', 'Thể thao', '⚽'],
] as const

export const sellers: Seller[] = [
  { id: 'nexa', name: 'Nexa Tech', logo: 'NT', category: 'Công nghệ', description: 'Thiết bị số được tuyển chọn cho nhịp sống hiện đại.' },
  { id: 'mori', name: 'Mori Living', logo: 'ML', category: 'Nhà cửa', description: 'Đồ dùng nhỏ giúp căn nhà dễ chịu hơn mỗi ngày.' },
  { id: 'lumi', name: 'Lumi Studio', logo: 'LS', category: 'Phong cách sống', description: 'Sách, làm đẹp và những điều nhỏ xinh.' },
  { id: 'move', name: 'Move Everyday', logo: 'ME', category: 'Thể thao', description: 'Đồng hành cùng các vận động thường ngày.' },
]

const img: Record<string, string> = {
  phone: '/assets/products/smartphones.jpg', computer: '/assets/products/computers.jpg', audio: '/assets/products/smartphones.jpg', fashion: '/assets/products/fashion.jpg',
  home: '/assets/demo-shop/living-hero.png', book: '/assets/products/books.jpg', beauty: '/assets/products/fashion.jpg', sport: '/assets/products/computers.jpg',
}
const names: Record<string, string[]> = {
  phone: ['Điện thoại Nova 128GB', 'Ốp lưng trong chống sốc', 'Sạc nhanh GaN 33W', 'Cáp bện USB-C 1m'],
  computer: ['Laptop Air 14 inch', 'Chuột không dây Orbit', 'Bàn phím cơ Mini 75', 'Đế nâng laptop gỗ'],
  audio: ['Tai nghe Pulse Pro', 'Loa mini Room One', 'Tai nghe chụp tai Cloud', 'Micro USB Voice'],
  fashion: ['Áo thun cotton dáng rộng', 'Túi tote canvas', 'Áo khoác nhẹ Everyday', 'Giày sneaker Run Low'],
  home: ['Đèn bàn Halo', 'Bình giữ nhiệt 600ml', 'Bộ ga gối Cotton Cloud', 'Kệ gỗ để bàn'],
  book: ['Sống sâu trong thế giới vội', 'Thiết kế một đời đáng sống', 'Bếp nhỏ, niềm vui lớn', 'Nhật ký tập trung'],
  beauty: ['Kem chống nắng Daily SPF50', 'Son dưỡng Dewy Care', 'Serum phục hồi 30ml', 'Bộ cọ trang điểm Mini'],
  sport: ['Bình nước tập luyện 1L', 'Thảm yoga Balance', 'Dây kháng lực 3 mức', 'Túi đeo chạy bộ'],
}
const base: Record<string, number> = { phone: 3990000, computer: 449000, audio: 690000, fashion: 179000, home: 219000, book: 99000, beauty: 189000, sport: 149000 }
const brand: Record<string, string> = { phone: 'Nova', computer: 'Orbit', audio: 'Pulse', fashion: 'Everyday', home: 'Mori', book: 'Nhã Nam', beauty: 'Lumi', sport: 'Move' }
const sellerFor: Record<string, string> = { phone: 'nexa', computer: 'nexa', audio: 'nexa', fashion: 'lumi', home: 'mori', book: 'lumi', beauty: 'lumi', sport: 'move' }

export const products: DemoProduct[] = categories.flatMap(([category], categoryIndex) => names[category].map((name, index) => {
  const id = `${category}-${index + 1}`
  const price = base[category] + index * Math.round(base[category] * 0.24)
  const discounted = (categoryIndex + index) % 4 === 0
  const hasVariants = index === 0 || (category === 'fashion' && index === 3)
  const stock = id === 'audio-4' || id === 'beauty-4' ? 0 : id === 'phone-3' || id === 'sport-2' ? 3 : 12 + index * 9
  const variants = hasVariants
    ? ['Xanh cobalt', 'Trắng mây', 'Mint dịu'].map((label, variantIndex) => ({ id: `${id}-v${variantIndex + 1}`, sku: `${id.toUpperCase()}-${variantIndex + 1}`, label, options: { 'Phiên bản': label }, price: price + variantIndex * 70000, originalPrice: discounted ? price + variantIndex * 70000 + 180000 : undefined, stock: variantIndex === 2 ? 0 : stock, image: img[category] }))
    : [{ id: `${id}-v1`, sku: id.toUpperCase(), label: 'Tiêu chuẩn', options: {}, price, originalPrice: discounted ? price + Math.max(30000, Math.round(price * .18)) : undefined, stock, image: img[category] }]
  return { id, slug: id, name, category, brand: brand[category], sellerId: sellerFor[category], description: `${name} là lựa chọn mẫu trong bản trải nghiệm ShopCart. Thông tin, giá và giao dịch đều được mô phỏng để thử hành trình mua sắm.`, gallery: id === 'home-1' || id === 'phone-1' || id === 'fashion-1' ? [img[category], img[category], img[category]] : id === 'book-4' ? [] : [img[category]], specifications: [['Thương hiệu', brand[category]], ['Danh mục', categories.find(c => c[0] === category)?.[1] ?? ''], ['Tình trạng', stock ? 'Còn hàng' : 'Hết hàng']], variants, badge: discounted ? 'Giảm giá' : index === 1 ? 'Mới' : undefined, rating: id === 'book-4' ? undefined : 4 + ((categoryIndex + index) % 9) / 10, reviewCount: id === 'book-4' ? undefined : 4 + categoryIndex * 3 + index, soldCount: 12 + categoryIndex * 19 + index * 7 }
}))

export const vouchers: Voucher[] = [
  { id: 'welcome10', code: 'WELCOME10', kind: 'percent', value: 10, minOrder: 300000, cap: 100000, status: 'available' },
  { id: 'save50', code: 'SAVE50', kind: 'fixed', value: 50000, minOrder: 500000, status: 'available' },
  { id: 'freeship', code: 'FREESHIP', kind: 'shipping', value: 30000, minOrder: 299000, status: 'available' },
]
export const addresses: Address[] = [
  { id: 'address-1', fullName: 'Khách thử nghiệm', phone: '0900 000 001', city: 'TP. Hồ Chí Minh', ward: 'Phường Bến Nghé', detail: '12 Đường Mẫu, Quận 1', isDefault: true },
  { id: 'address-2', fullName: 'Người nhận mẫu', phone: '0900 000 002', city: 'Hà Nội', ward: 'Phường Cửa Nam', detail: '08 Phố Minh Họa, Hoàn Kiếm', isDefault: false },
]
export const reviews: Review[] = Array.from({ length: 12 }, (_, i) => ({ id: `review-${i + 1}`, productId: products[i % 8].id, author: ['Minh Anh', 'Gia Hân', 'Quốc Bảo', 'Thảo Vy'][i % 4], rating: 5 - (i % 3), content: ['Đóng gói gọn, dùng đúng như mô tả.', 'Chất lượng ổn trong tầm giá.', 'Màu sắc đẹp, giao diện demo rất rõ ràng.'][i % 3], date: `2026-0${(i % 8) + 1}-12` }))
export const orders: DemoOrder[] = ['pending', 'shipping', 'delivered', 'cancelled', 'delivered', 'shipping'].map((status, i) => ({ id: `DEMO-20260${i + 1}-${102 + i}`, items: [{ productId: products[i].id, variantId: products[i].variants[0].id, name: products[i].name, variant: products[i].variants[0].label, sellerId: products[i].sellerId, quantity: 1, unitPrice: products[i].variants[0].price, image: products[i].gallery[0] }], address: addresses[i % 2], status: status as DemoOrder['status'], createdAt: `2026-0${i + 1}-15T09:00:00.000Z`, subtotal: products[i].variants[0].price, productDiscount: 0, shipping: 30000, shippingDiscount: 0, total: products[i].variants[0].price + 30000, payment: i % 2 ? 'Thanh toán online mô phỏng' : 'COD mô phỏng', shippingMethod: 'Giao tiêu chuẩn', timeline: [{ label: 'Đơn demo đã được tạo', at: `2026-0${i + 1}-15 09:00` }] }))
export const notices: Notice[] = [{ id: 'notice-1', title: 'Chào mừng bạn đến ShopCart Demo', body: 'Mọi dữ liệu và giao dịch ở đây là mô phỏng.', href: '/demo/shop/vouchers', read: false }, { id: 'notice-2', title: 'Voucher WELCOME10 đang sẵn sàng', body: 'Áp dụng cho đơn từ 300.000đ.', href: '/demo/shop/vouchers', read: false }]

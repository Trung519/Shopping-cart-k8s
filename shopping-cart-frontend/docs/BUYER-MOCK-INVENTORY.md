# ShopCart Buyer Demo — mock inventory

Demo chạy độc lập tại `/demo/shop`. Nó không gọi `/api/v2`, không đọc JWT, không dùng store giỏ/yêu thích thật và không phải storefront nhận thanh toán.

| Mock ID | Route / component | Model & fixture | Hành động, kết quả local | Backend adapter cần thay |
|---|---|---|---|---|
| BUY-001 | Home, ProductCard | Product, 32 sản phẩm / 8 danh mục | Search, wishlist, add-cart | catalog search, product read, wishlist write |
| BUY-002 | `/products`, CatalogPage | query URL và catalog fixture | filter/sort/page giữ trong URL | catalog query API |
| BUY-003 | `/products/:id`, DetailPage | product, variant, review | chọn variant đổi giá/tồn; buy-now tạo intent | product detail, inventory, reviews, checkout intent |
| BUY-004 | `/shops/:id` | 4 Seller | xem catalog theo shop | seller storefront read |
| BUY-005 | `/cart` | CartLine khóa productId+variantId | chọn, đổi lượng, xóa, chuyển wishlist; quote local | cart CRUD, promotion quote |
| BUY-006 | `/checkout` | Address, Voucher, checkout snapshot | shipping/payment mô phỏng; tạo đơn local | address CRUD, shipping quote, payment intent, order create |
| BUY-007 | `/orders*` | 6 DemoOrder + order mới | success không tạo lại sau refresh; snapshot độc lập | orders read, cancel/return/review endpoints |
| BUY-008 | `/account/*` | profile, address, notice, voucher, support | các thay đổi lưu browser | buyer profile, addresses, notifications, vouchers, ticket APIs |

## Quy tắc tính tiền mô phỏng

- `WELCOME10`: 10%, đơn từ 300.000đ, giảm tối đa 100.000đ.
- `SAVE50`: giảm 50.000đ, đơn từ 500.000đ.
- `FREESHIP`: giảm phí giao tối đa 30.000đ, đơn từ 299.000đ.
- Standard: 30.000đ/shop; express: 50.000đ/shop.
- `grandTotal = subtotal − productDiscount + shipping − shippingDiscount`; giá/phí không tách thuế.

## Persistence và thay thế backend

State lưu với key `shopcart-buyer-demo-v1`. JSON hỏng reset về fixture; nếu storage bị chặn, UI tiếp tục bằng memory và hiện cảnh báo. Adapter thật phải thay rõ ràng — không fallback âm thầm sang mock khi API lỗi.

Đề xuất contract: `searchProducts`, `getProduct`, `getShop`, `getReviews`, `quoteCheckout`, `createOrder`, `listOrders`, `saveAddress`, `saveWishlist`, `createSupportTicket`.

## Assets và hạn chế

`public/assets/demo-shop/living-hero.png` là asset local tạo bằng OpenAI Image Generation cho demo. Catalog dùng asset public local có sẵn làm minh họa category; trước khi phát hành thương mại cần thay toàn bộ bằng ảnh product-level có quyền sử dụng và asset registry đầy đủ.

- Chưa có API adapter/backend, payment/shipping provider hay Keycloak flow.
- Mobile hiện có toolbar filter nhưng chưa có bottom sheet áp dụng tạm.
- Review, ticket, return và trạng thái đơn chỉ là local UI scenario; không có network request.

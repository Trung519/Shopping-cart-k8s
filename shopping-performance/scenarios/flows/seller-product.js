import {check} from 'k6'
import {fixture, login, recordBusiness, request, responseData, runId, think} from '../lib/context.js'

export default function sellerProduct() {
  const user = fixture.users.sellerProduct[(__VU - 1) % fixture.users.sellerProduct.length]
  if (!login(user)) return recordBusiness('seller_product', false, Date.now())
  const started = Date.now()
  const sku = `${runId}-sku-${__VU}-${__ITER}`
  const payload = {
    sku,
    name: `${runId} Seller Product ${__VU}-${__ITER}`,
    description: 'Load-test fixture',
    price: fixture.config.productPrice,
    currency: fixture.config.currency,
    quantity: fixture.config.sellerProductStock,
    category: fixture.config.category,
    image_url: null,
  }
  const created = request('seller_product', 'POST', '/api/v2/products', payload, {}, [201], '/api/v2/products')
  const id = responseData(created)?.id
  const detail = id ? request('seller_product', 'GET', `/api/v2/products/${id}`, null, {}, [200], '/api/v2/products/:productId') : {status: 0}
  const product = responseData(detail)
  const ok = check(created, {'seller product is created': () => created.status === 201 && Boolean(id)}) &&
    check(detail, {'seller product ownership and fields persist': () => detail.status === 200 && product?.sku === sku && product?.seller_id === user.id && product?.category === fixture.config.category && Number(product?.quantity) === fixture.config.sellerProductStock})
  recordBusiness('seller_product', ok, started)
  think()
}

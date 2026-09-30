import {check} from 'k6'
import {fixture, inventoryVerified, login, pickProduct, recordBusiness, request, responseData, think, verifyNoDuplicateOrder, verifyOrder} from '../lib/context.js'

export default function buyNow() {
  const user = fixture.users.buyNow[(__VU - 1) % fixture.users.buyNow.length]
  if (!login(user)) return recordBusiness('buy_now', false, Date.now())
  const started = Date.now()
  request('buy_now', 'DELETE', '/api/v2/cart', null, {}, [200, 204, 404], '/api/v2/cart')
  const product = pickProduct()
  const before = responseData(request('buy_now', 'GET', `/api/v2/products/${product.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const added = request('buy_now', 'POST', '/api/v2/cart/items', {productId: product.id, quantity: 1, unitPrice: 1}, {}, [201], '/api/v2/cart/items')
  const checkout = request('buy_now', 'POST', '/api/v2/cart/checkout', {shippingAddress: fixture.config.shippingAddress}, {}, [200], '/api/v2/cart/checkout')
  const checkoutData = responseData(checkout)
  const orderId = checkoutData?.orderId
  const verified = orderId ? verifyOrder('buy_now', user, orderId, [{productId: product.id, quantity: 1}], fixture.config.shippingAddress) : {ok: false}
  const after = responseData(request('buy_now', 'GET', `/api/v2/products/${product.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const cart = responseData(request('buy_now', 'GET', '/api/v2/cart', null, {}, [200], '/api/v2/cart'))
  const stockOk = Number(after?.quantity) === Number(before?.quantity) - 1
  if (stockOk) inventoryVerified.add(1, {flow: 'buy_now', run_id: fixture.runId})
  const unique = orderId ? verifyNoDuplicateOrder('buy_now', user, orderId) : false
  const ok = check(added, {'buy now ignores client price': () => added.status === 201 && Number(responseData(added)?.items?.[0]?.unitPrice) === Number(product.price)}) &&
    check(checkout, {'buy now returns a real order': () => checkout.status === 200 && Boolean(orderId)}) &&
    check(checkout, {'buy now order, inventory and cart are consistent': () => verified.ok && stockOk && unique && cart?.items?.length === 0})
  recordBusiness('buy_now', ok, started)
  think()
}

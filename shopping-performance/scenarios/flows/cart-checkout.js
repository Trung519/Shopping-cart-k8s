import {check} from 'k6'
import {fixture, inventoryVerified, itemByProduct, login, pickProduct, recordBusiness, request, responseData, think, verifyNoDuplicateOrder, verifyOrder} from '../lib/context.js'

export default function cartCheckout() {
  const user = fixture.users.cartCheckout[(__VU - 1) % fixture.users.cartCheckout.length]
  if (!login(user)) return recordBusiness('cart_checkout', false, Date.now())
  const started = Date.now()
  request('cart_checkout', 'DELETE', '/api/v2/cart', null, {}, [200, 204, 404], '/api/v2/cart')
  const first = pickProduct()
  const second = pickProduct(Math.floor(fixture.products.length / 2))
  const beforeFirst = responseData(request('cart_checkout', 'GET', `/api/v2/products/${first.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const beforeSecond = responseData(request('cart_checkout', 'GET', `/api/v2/products/${second.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const a = request('cart_checkout', 'POST', '/api/v2/cart/items', {productId: first.id, quantity: 1}, {}, [201], '/api/v2/cart/items')
  const b = request('cart_checkout', 'POST', '/api/v2/cart/items', {productId: second.id, quantity: 1}, {}, [201], '/api/v2/cart/items')
  const firstItem = itemByProduct(responseData(b) || responseData(a), first.id)
  const changed = firstItem?.id
    ? request('cart_checkout', 'PUT', `/api/v2/cart/items/${firstItem.id}`, {quantity: 2}, {}, [200], '/api/v2/cart/items/:itemId')
    : {status: 0}
  const cartBeforeCheckout = responseData(request('cart_checkout', 'GET', '/api/v2/cart', null, {}, [200], '/api/v2/cart'))
  const checkout = request('cart_checkout', 'POST', '/api/v2/cart/checkout', {shippingAddress: fixture.config.shippingAddress}, {}, [200], '/api/v2/cart/checkout')
  const orderId = responseData(checkout)?.orderId
  const expectedItems = [{productId: first.id, quantity: 2}, {productId: second.id, quantity: 1}]
  const verified = orderId ? verifyOrder('cart_checkout', user, orderId, expectedItems, fixture.config.shippingAddress) : {ok: false}
  const afterFirst = responseData(request('cart_checkout', 'GET', `/api/v2/products/${first.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const afterSecond = responseData(request('cart_checkout', 'GET', `/api/v2/products/${second.id}`, null, {}, [200], '/api/v2/products/:productId'))
  const finalCart = responseData(request('cart_checkout', 'GET', '/api/v2/cart', null, {}, [200], '/api/v2/cart'))
  const stockOk = Number(afterFirst?.quantity) === Number(beforeFirst?.quantity) - 2 && Number(afterSecond?.quantity) === Number(beforeSecond?.quantity) - 1
  if (stockOk) inventoryVerified.add(1, {flow: 'cart_checkout', run_id: fixture.runId})
  const unique = orderId ? verifyNoDuplicateOrder('cart_checkout', user, orderId) : false
  const cartValid = itemByProduct(cartBeforeCheckout, first.id)?.quantity === 2 && itemByProduct(cartBeforeCheckout, second.id)?.quantity === 1
  const ok = check(changed, {'cart checkout persists all quantities': () => changed.status === 200 && cartValid}) &&
    check(checkout, {'cart checkout returns a real order': () => checkout.status === 200 && Boolean(orderId)}) &&
    check(checkout, {'cart checkout order, inventory and cart are consistent': () => verified.ok && stockOk && unique && finalCart?.items?.length === 0})
  recordBusiness('cart_checkout', ok, started)
  think()
}

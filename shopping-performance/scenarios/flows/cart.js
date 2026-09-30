import {check} from 'k6'
import {fixture, itemByProduct, login, pickProduct, recordBusiness, request, responseData, think} from '../lib/context.js'

export default function cart() {
  const user = fixture.users.cart[(__VU - 1) % fixture.users.cart.length]
  if (!login(user)) return recordBusiness('cart', false, Date.now())
  const started = Date.now()
  const cleared = request('cart', 'DELETE', '/api/v2/cart', null, {}, [200, 204, 404], '/api/v2/cart')
  const product = pickProduct()
  const added = request('cart', 'POST', '/api/v2/cart/items', {productId: product.id, quantity: 1}, {}, [201], '/api/v2/cart/items')
  const addedCart = responseData(added)
  const addedItem = itemByProduct(addedCart, product.id)
  const viewed = request('cart', 'GET', '/api/v2/cart', null, {}, [200], '/api/v2/cart')
  const viewedItem = itemByProduct(responseData(viewed), product.id)
  const changed = addedItem?.id
    ? request('cart', 'PUT', `/api/v2/cart/items/${addedItem.id}`, {quantity: 2}, {}, [200], '/api/v2/cart/items/:itemId')
    : {status: 0}
  const changedItem = itemByProduct(responseData(changed), product.id)
  const removed = addedItem?.id
    ? request('cart', 'DELETE', `/api/v2/cart/items/${addedItem.id}`, null, {}, [200], '/api/v2/cart/items/:itemId')
    : {status: 0}
  const finalCart = request('cart', 'GET', '/api/v2/cart', null, {}, [200], '/api/v2/cart')
  const ok = check(added, {'cart stores server-owned product data': () => added.status === 201 && addedItem?.quantity === 1 && Number(addedItem?.unitPrice) === Number(product.price)}) &&
    check(viewed, {'cart read contains added product': () => viewed.status === 200 && viewedItem?.quantity === 1}) &&
    check(changed, {'cart update persists quantity': () => changed.status === 200 && changedItem?.quantity === 2}) &&
    check(removed, {'cart item deletion succeeds': () => removed.status === 200}) &&
    check(finalCart, {'deleted item is absent': () => finalCart.status === 200 && !itemByProduct(responseData(finalCart), product.id)}) &&
    [200, 204, 404].includes(cleared.status)
  recordBusiness('cart', ok, started)
  think()
}

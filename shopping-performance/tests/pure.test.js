import test from 'node:test'
import assert from 'node:assert/strict'
import {allocateShares, classifyRun, createRng, normalizeEndpoint} from '../scenarios/lib/pure.js'

test('seeded random is reproducible', () => {
  const first = createRng(42)
  const second = createRng(42)
  assert.deepEqual([first(), first(), first()], [second(), second(), second()])
})

test('flow allocation preserves the configured peak shares', () => {
  assert.deepEqual(allocateShares(200, {browse: 0.45, cart: 0.20, buyNow: 0.10, cartCheckout: 0.10, sellerProduct: 0.10, sellerApplication: 0.05}), {
    browse: 90, cart: 40, buyNow: 20, cartCheckout: 20, sellerProduct: 20, sellerApplication: 10,
  })
})

test('dynamic resource IDs do not become Prometheus labels', () => {
  assert.equal(normalizeEndpoint('/api/v2/products/9b85938c-e0ab-414c-bc9d-6f8e0e0c04d5'), '/api/v2/products/:productId')
  assert.equal(normalizeEndpoint('/api/v2/cart/items/cart-item-123'), '/api/v2/cart/items/:itemId')
  assert.equal(normalizeEndpoint('/api/v2/orders/6a17894f-1111-2222-3333-444444444444'), '/api/v2/orders/:orderId')
})

test('run classification never hides k6 or cleanup failure', () => {
  assert.equal(classifyRun({k6Exit: 99, cleanupOk: true, verificationOk: true}), 'FAILED')
  assert.equal(classifyRun({k6Exit: 0, cleanupOk: false, verificationOk: true}), 'CLEANUP_FAILED')
  assert.equal(classifyRun({k6Exit: 0, cleanupOk: true, verificationOk: true}), 'PASS')
})

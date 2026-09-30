import http from 'k6/http'
import {check, sleep} from 'k6'
import exec from 'k6/execution'
import {Counter, Rate, Trend} from 'k6/metrics'
import {createRng, hashString, normalizeEndpoint} from './pure.js'

export const runId = __ENV.RUN_ID || 'manual'
export const fixture = JSON.parse(open(__ENV.FIXTURE_FILE || `/work/.local/fixtures/${runId}.json`))
export const baseURL = __ENV.BASE_URL || 'http://shopping-cart.localhost:8080'
export const publicHost = __ENV.PUBLIC_HOST || 'shopping-cart.localhost'

export const flowRequests = new Counter('shopcart_flow_requests')
export const flowFailures = new Rate('shopcart_flow_failures')
export const requestDuration = new Trend('shopcart_request_duration', true)
export const flowDuration = new Trend('shopcart_flow_duration', true)
export const authDuration = new Trend('shopcart_auth_duration', true)
export const businessSuccess = new Rate('shopcart_business_success')
export const ordersRequested = new Counter('shopcart_orders_requested')
export const ordersVerified = new Counter('shopcart_orders_verified')
export const inventoryVerified = new Counter('shopcart_inventory_verified')
export const duplicateOrders = new Counter('shopcart_duplicate_orders')

let authenticatedUser = ''
let seededRandom

export function flowOptions(name, endpoint = '') {
  const tags = {flow: name, run_id: runId, profile: __ENV.PROFILE || 'manual'}
  if (endpoint) tags.endpoint = endpoint
  return {tags}
}

export function random() {
  if (!seededRandom) {
    const seed = Number(fixture.seed || 1) ^ hashString(`${exec.vu.idInTest}:${exec.scenario.name}`)
    seededRandom = createRng(seed)
  }
  return seededRandom()
}

export function request(name, method, path, body, params = {}, expected = [200], endpoint = normalizeEndpoint(path)) {
  const options = Object.assign({}, params, flowOptions(name, endpoint))
  options.tags = Object.assign({}, options.tags, flowOptions(name, endpoint).tags)
  const payload = body == null ? null : JSON.stringify(body)
  options.headers = Object.assign({'Host': publicHost, 'X-Forwarded-Host': `${publicHost}:8080`}, payload != null ? {'Content-Type': 'application/json'} : {}, options.headers || {})
  const response = http.request(method, `${baseURL}${path}`, payload, options)
  const ok = expected.includes(response.status)
  flowRequests.add(1, flowOptions(name).tags)
  flowFailures.add(!ok, flowOptions(name).tags)
  requestDuration.add(response.timings.duration, flowOptions(name, endpoint).tags)
  return response
}

function decodeAction(action) {
  return action.replace(/&amp;/g, '&').replace(/&#x27;/g, "'").replace(/&#39;/g, "'")
}

export function login(user) {
  if (authenticatedUser === user.username.toLowerCase()) return true
  const started = Date.now()
  const jar = http.cookieJar()
  jar.clear(baseURL)
  const first = http.get(`${baseURL}/api/v2/auth/login`, {redirects: 10, jar, tags: {flow: 'auth', run_id: runId, endpoint: '/api/v2/auth/login'}})
  const match = first.body.match(/<form[^>]+action=["']([^"']+)["']/i)
  if (!match) {
    authDuration.add(Date.now() - started, flowOptions('auth').tags)
    return false
  }
  const auth = http.post(decodeAction(match[1]), {username: user.username, password: user.password, credentialId: ''}, {
    redirects: 10, jar, tags: {flow: 'auth', run_id: runId, endpoint: 'keycloak-login'},
  })
  const me = http.get(`${baseURL}/api/v2/auth/me`, {
    redirects: 5, jar, headers: {'Host': publicHost, 'X-Forwarded-Host': `${publicHost}:8080`},
    tags: {flow: 'auth', endpoint: '/api/v2/auth/me', run_id: runId},
  })
  const meData = responseData(me)
  authenticatedUser = auth.status >= 200 && auth.status < 400 && me.status === 200 && meData?.id === user.id
    ? user.username.toLowerCase() : ''
  authDuration.add(Date.now() - started, flowOptions('auth').tags)
  check(me, {'OIDC identity matches fixture': () => authenticatedUser !== ''})
  return authenticatedUser !== ''
}

export function pickProduct(offset = 0) {
  const index = (exec.vu.idInTest - 1 + offset + fixture.products.length) % fixture.products.length
  return fixture.products[index]
}

export function think(min = fixture.config.thinkTimeSeconds.min, max = fixture.config.thinkTimeSeconds.max) {
  sleep(min + random() * (max - min))
}

export function recordBusiness(flow, ok, started) {
  businessSuccess.add(ok, flowOptions(flow).tags)
  flowDuration.add(Date.now() - started, flowOptions(flow).tags)
}

export function responseData(response) {
  try {
    const parsed = response.json()
    return parsed && parsed.data !== undefined ? parsed.data : parsed
  } catch (_) {
    return null
  }
}

export function itemByProduct(cart, productId) {
  return cart?.items?.find((item) => item.productId === productId)
}

export function verifyOrder(flow, user, orderId, expectedItems, address) {
  ordersRequested.add(1, flowOptions(flow).tags)
  const response = request(flow, 'GET', `/api/v2/orders/${orderId}`, null, {}, [200], '/api/v2/orders/:orderId')
  const order = responseData(response)
  const itemMap = new Map((order?.items || []).map((item) => [item.productId, item]))
  const itemsMatch = expectedItems.every((expected) => itemMap.get(expected.productId)?.quantity === expected.quantity)
  const calculatedTotal = (order?.items || []).reduce((sum, item) => sum + Number(item.subtotal), 0)
  const totalMatches = Number(order?.totalAmount) === calculatedTotal && calculatedTotal > 0
  const addressMatches = order?.shippingAddress?.street === address.street && order?.shippingAddress?.country === address.country
  const ok = response.status === 200 && order?.id === orderId && order?.customerId === user.id && itemsMatch && totalMatches && addressMatches
  if (ok) ordersVerified.add(1, flowOptions(flow).tags)
  return {ok, order}
}

export function verifyNoDuplicateOrder(flow, user, orderId) {
  const response = request(flow, 'GET', `/api/v2/orders?customerId=${encodeURIComponent(user.id)}`, null, {}, [200], '/api/v2/orders')
  const orders = responseData(response) || []
  const duplicates = orders.filter((order) => order.id === orderId).length
  duplicateOrders.add(Math.max(0, duplicates - 1), flowOptions(flow).tags)
  return response.status === 200 && duplicates === 1
}

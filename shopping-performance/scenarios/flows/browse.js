import {check} from 'k6'
import {fixture, login, pickProduct, random, recordBusiness, request, responseData, think} from '../lib/context.js'

export default function browse() {
  const user = fixture.users.browse[(__VU - 1) % fixture.users.browse.length]
  if (!login(user)) return recordBusiness('browse', false, Date.now())
  const started = Date.now()
  const product = pickProduct()
  const page = 1 + Math.floor(random() * 4)
  const list = request('browse', 'GET', `/api/v2/products?page=${page}&page_size=12&category=${fixture.config.category}&sort=newest`, null, {}, [200], '/api/v2/products')
  const search = request('browse', 'GET', `/api/v2/products?search=${encodeURIComponent(product.sku)}&page_size=10`, null, {}, [200], '/api/v2/products')
  const detail = request('browse', 'GET', `/api/v2/products/${product.id}`, null, {}, [200], '/api/v2/products/:productId')
  const listed = responseData(list)?.items || []
  const found = responseData(search)?.items || []
  const selected = responseData(detail)
  const ok = check(list, {'browse category filter is valid': () => list.status === 200 && listed.every((item) => item.category === fixture.config.category)}) &&
    check(search, {'browse search finds fixture SKU': () => search.status === 200 && found.some((item) => item.id === product.id)}) &&
    check(detail, {'browse detail matches requested product': () => detail.status === 200 && selected?.id === product.id && selected?.sku === product.sku})
  recordBusiness('browse', ok, started)
  think()
}

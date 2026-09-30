import browse from './flows/browse.js'
import cart from './flows/cart.js'
import buyNow from './flows/buy-now.js'
import cartCheckout from './flows/cart-checkout.js'
import sellerProduct from './flows/seller-product.js'
import sellerApplication from './flows/seller-application.js'
import {fixture} from './lib/context.js'

const profile = JSON.parse(open(`/work/profiles/${__ENV.PROFILE || 'smoke'}.json`))

function scaleStages(stages, share) {
  return stages.map((stage) => ({duration: stage.duration, target: Math.max(share > 0 && stage.target > 0 ? 1 : 0, Math.round(stage.target * share))}))
}

const rampingFlows = [
  ['browse', 0.45],
  ['cart', 0.20],
  ['buy_now', 0.10],
  ['cart_checkout', 0.10],
  ['seller_product', 0.10],
]

const scenarios = Object.fromEntries(rampingFlows.map(([name, share]) => [name, {
  executor: profile.mode === 'smoke' ? 'per-vu-iterations' : 'ramping-vus',
  exec: name,
  startTime: '0s',
  gracefulStop: '15s',
  ...(profile.mode === 'smoke'
    ? {vus: profile.vusPerFlow, iterations: 1, maxDuration: '2m'}
    : {startVUs: 0, stages: scaleStages(profile.stages, share), gracefulRampDown: '15s'}),
}]))

scenarios.seller_application = {
  executor: 'shared-iterations',
  exec: 'seller_application',
  vus: fixture.users.sellerApplication.length,
  iterations: fixture.users.sellerApplication.length,
  maxDuration: `${Math.max(120, profile.applicationSpreadSeconds + 120)}s`,
}

const slo = profile.slo
export const options = {
  scenarios,
  thresholds: {
    http_req_failed: [{threshold: `rate<${slo.httpFailureRate}`, abortOnFail: false}],
    shopcart_business_success: [{threshold: `rate>${slo.businessSuccessRate}`, abortOnFail: false}],
    shopcart_duplicate_orders: [{threshold: 'count==0', abortOnFail: false}],
    'shopcart_flow_duration{flow:browse}': [{threshold: `p(95)<${slo.browseP95Ms}`, abortOnFail: false}],
    'shopcart_flow_duration{flow:cart}': [{threshold: `p(95)<${slo.cartP95Ms}`, abortOnFail: false}],
    'shopcart_flow_duration{flow:buy_now}': [{threshold: `p(95)<${slo.buyNowP95Ms}`, abortOnFail: false}],
    'shopcart_flow_duration{flow:cart_checkout}': [{threshold: `p(95)<${slo.cartCheckoutP95Ms}`, abortOnFail: false}],
    'shopcart_flow_duration{flow:seller_product}': [{threshold: `p(95)<${slo.sellerProductP95Ms}`, abortOnFail: false}],
    'shopcart_flow_duration{flow:seller_application}': [{threshold: `p(95)<${slo.sellerApplicationP95Ms}`, abortOnFail: false}],
  },
}

export {browse, cart}
export function buy_now() { return buyNow() }
export function cart_checkout() { return cartCheckout() }
export function seller_product() { return sellerProduct() }
export function seller_application() { return sellerApplication() }

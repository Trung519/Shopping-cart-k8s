export function hashString(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

export function createRng(seed) {
  let state = seed >>> 0
  return () => {
    state += 0x6d2b79f5
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

export function normalizeEndpoint(path) {
  return path.split('?')[0]
    .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, ':id')
    .replace(/\/items\/[^/]+$/i, '/items/:itemId')
    .replace(/\/orders\/[^/]+$/i, '/orders/:orderId')
    .replace(/\/products\/[^/]+$/i, '/products/:productId')
}

export function allocateShares(total, shares) {
  const result = {}
  for (const [name, share] of Object.entries(shares)) {
    result[name] = Math.max(1, Math.ceil(total * share))
  }
  return result
}

export function classifyRun({k6Exit, cleanupOk, verificationOk}) {
  if (!cleanupOk) return 'CLEANUP_FAILED'
  if (k6Exit !== 0 || !verificationOk) return 'FAILED'
  return 'PASS'
}

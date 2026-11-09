/**
 * Pass-through for /v1/** to the backend when the storefront is served without a reverse proxy.
 * Not a BFF: no logic, no transformation. The visitor's host is forwarded so the backend resolves the
 * tenant (the backend must run with TRUST_FORWARDED_HOST=true and be reachable only from here/proxy).
 */
export default defineEventHandler(async (event) => {
  if (!event.path.startsWith('/v1/')) {
    return
  }
  const { apiInternalUrl, proxyApi } = useRuntimeConfig(event)
  if (!proxyApi) {
    return
  }
  const host = getRequestHeader(event, 'host') ?? ''
  return proxyRequest(event, `${apiInternalUrl}${event.path}`, {
    headers: {
      'x-forwarded-host': host,
      'x-forwarded-for': getRequestIP(event, { xForwardedFor: true }) ?? '',
    },
  })
})

import { createApiClient } from '@delivery/api-client'

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const platform = usePlatform()
  const cartToken = useCartToken()

  const api = createApiClient({
    // SSR talks to the backend directly and forwards the visitor's host for tenant resolution.
    baseUrl: import.meta.server ? config.apiInternalUrl : config.public.apiBaseUrl,
    forwardedHost: import.meta.server ? useRequestURL().host : undefined,
    channel: platform,
    // Mobile: the cafe chosen in the app; white-label builds may fix it at build time.
    tenantSlug: () => (platform === 'mobile' ? useVenues().current.value : null) || config.public.tenantSlug || undefined,
    cartToken: () => cartToken.value,
  })

  return { provide: { api } }
})

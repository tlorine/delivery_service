import type { CookieRef } from '#app'

/**
 * The server-side cart is addressed by a secret token (ADR-0004). Kept in a cookie so SSR and the
 * browser see the same cart; it holds no personal data. Mobile replaces the storage in its adapter.
 *
 * One ref per app instance: two `useCookie` refs for the same name are not synchronised within a tick,
 * which made the API client send a stale token right after a cart was created.
 */
export function useCartToken(): CookieRef<string | null> {
  const nuxtApp = useNuxtApp() as unknown as { _cartToken?: CookieRef<string | null> }
  if (nuxtApp._cartToken) {
    return nuxtApp._cartToken
  }
  if (usePlatform() === 'mobile') {
    // No cookies on capacitor:// origins: one cart per cafe in durable storage.
    const venue = useVenues().current
    const token = ref<string | null>(venue.value ? mobileGet(`cart_token:${venue.value}`) : null)
    watch(token, (value) => {
      if (venue.value) {
        mobileSet(`cart_token:${venue.value}`, value)
      }
    })
    nuxtApp._cartToken = token as CookieRef<string | null>
    return nuxtApp._cartToken
  }
  nuxtApp._cartToken = useCookie<string | null>('cart_token', {
    default: () => null,
    maxAge: 60 * 60 * 24 * 30,
    sameSite: 'lax',
    secure: !import.meta.dev,
  })
  return nuxtApp._cartToken
}

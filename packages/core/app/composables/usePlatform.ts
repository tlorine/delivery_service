import type { ClientChannel } from '@delivery/api-client'

/** Which client the storefront runs in. Telegram is detected by signed initData presence. */
export function usePlatform(): ClientChannel {
  const configured = useRuntimeConfig().public.platform as ClientChannel | ''
  if (configured) {
    return configured
  }
  if (import.meta.client) {
    const tg = (window as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp
    if (tg?.initData) {
      return 'telegram'
    }
  }
  return 'web'
}

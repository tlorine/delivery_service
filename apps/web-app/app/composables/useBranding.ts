/** Tenant branding from /v1/storefront (data, not code): accent colour, logo, cover. */
export function useBranding() {
  const storefront = useStorefrontStore()
  const branding = computed(() => (storefront.data?.branding ?? {}) as Record<string, unknown>)
  const tokens = computed(() => brandTokens(branding.value.accent_color))
  const logoUrl = computed(() => httpsUrl(branding.value.logo_url))
  const coverUrl = computed(() => httpsUrl(branding.value.cover_url))
  return { tokens, logoUrl, coverUrl }
}

function httpsUrl(value: unknown): string | undefined {
  return typeof value === 'string' && value.startsWith('https://') ? value : undefined
}

export default defineNuxtConfig({
  modules: [
    '@nuxtjs/i18n',
    '@pinia/nuxt',
  ],
  runtimeConfig: {
    // Server-side (SSR) address of the FastAPI backend, e.g. http://api:8000
    apiInternalUrl: 'http://localhost:8000',
    // Proxy /v1/** to apiInternalUrl when no reverse proxy sits in front (local dev, simple deploys).
    proxyApi: true,
    public: {
      // Browser-side API base: '' = same origin (/v1 via reverse proxy or the built-in proxy).
      apiBaseUrl: '',
      // Fixed tenant for white-label/mobile builds that run without the tenant's domain.
      tenantSlug: '',
      // web | telegram | mobile; empty = detect at runtime.
      platform: '',
    },
  },
  i18n: {
    strategy: 'no_prefix',
  },
  compatibilityDate: '2025-07-15',
})

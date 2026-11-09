import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  extends: ['@nextorders/ui'],
  // Staff tool behind login: no SEO, no SSR. Served by Nitro for the /v1 pass-through only.
  ssr: false,
  runtimeConfig: {
    apiInternalUrl: 'http://localhost:8000',
    proxyApi: true,
  },
  // Same pass-through as the storefront (same origin => HttpOnly session cookie, no CORS).
  serverHandlers: [
    { middleware: true, handler: fileURLToPath(new URL('../../packages/core/server/middleware/api-proxy.ts', import.meta.url)) },
  ],
  app: {
    head: {
      title: 'Панель заведения',
      htmlAttrs: { lang: 'ru' },
      meta: [{ name: 'robots', content: 'noindex' }],
    },
  },
  i18n: {
    defaultLocale: 'ru',
  },
  compatibilityDate: '2025-07-15',
})

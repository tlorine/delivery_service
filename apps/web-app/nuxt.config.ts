import process from 'node:process'

// `NUXT_BUILD_TARGET=mobile nuxt generate`: SPA for the Capacitor shell (ADR-0005, variant A).
const mobile = process.env.NUXT_BUILD_TARGET === 'mobile'

export default defineNuxtConfig({
  extends: ['@nextorders/ui', '@nextorders/core'],
  css: ['~/assets/css/storefront.css'],
  ssr: !mobile,
  // Separate dirs: the mobile build must not overwrite the SSR server build.
  buildDir: mobile ? '.nuxt-mobile' : '.nuxt',
  nitro: mobile ? { output: { dir: '.output-mobile' } } : {},
  // One typeface for the storefront: Onest (Cyrillic-first, OFL), self-hosted by @nuxt/fonts at build time.
  fonts: {
    families: [
      { name: 'Onest', provider: 'google', weights: [400, 500, 600, 700] },
    ],
  },
  runtimeConfig: mobile
    ? {
        proxyApi: false,
        public: {
          platform: 'mobile',
          // Absolute API origin for the app (a platform host where X-Tenant is honoured).
          apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL ?? 'https://api.example.ru',
        },
      }
    : {},
  app: {
    head: {
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' }],
    },
  },
  router: {
    options: {
      scrollBehaviorType: 'smooth',
    },
  },
  compatibilityDate: '2025-07-15',
})

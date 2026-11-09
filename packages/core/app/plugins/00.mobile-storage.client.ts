/** Mobile: restore durable storage before anything reads cafe/cart state (see utils/mobileStorage.ts). */
export default defineNuxtPlugin({
  name: 'mobile-storage',
  enforce: 'pre',
  async setup() {
    if (useRuntimeConfig().public.platform === 'mobile') {
      await restoreMobileStorage()
    }
  },
})

import type { ApiError, Storefront } from '@delivery/api-client'

/** Raw storefront data from GET /v1/storefront; channel/options stores are views over it. */
export const useStorefrontStore = defineStore('storefront', () => {
  const data = ref<Storefront | null>(null)
  const error = ref<ApiError | null>(null)

  async function update(): Promise<void> {
    try {
      data.value = await useNuxtApp().$api.get('/v1/storefront')
      error.value = null
    } catch (e) {
      // Keep the last known data; pages show maintenance only when nothing was ever loaded.
      error.value = e as ApiError
    }
  }

  return { data, error, update }
})

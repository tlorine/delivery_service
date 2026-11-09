import type { ApiError } from '@delivery/api-client'

/** Calls an admin action, shows a Russian toast for failures; returns undefined on error. */
export function useAdminAction() {
  const toast = useToast()

  async function run<T>(action: () => Promise<T>, success?: string): Promise<T | undefined> {
    try {
      const result = await action()
      if (success) {
        toast.add({ title: success, color: 'success', icon: 'lucide:check', duration: 1500 })
      }
      return result
    } catch (e) {
      const error = e as ApiError
      if (error.status === 401) {
        await navigateTo('/login')
        return
      }
      toast.add({ title: errorText(error.code), description: error.status === 422 ? error.problem?.detail : undefined, color: 'error', icon: 'lucide:circle-alert' })
    }
  }

  /** For calls without a response body (204): true on success, false after showing the error. */
  async function ok(action: () => Promise<unknown>, success?: string): Promise<boolean> {
    let succeeded = false
    await run(async () => {
      await action()
      succeeded = true
    }, success)
    return succeeded
  }

  return { run, ok }
}

export function useAdminApi() {
  return useNuxtApp().$adminApi
}

import type { StaffRole } from '~/composables/useSession'

export default defineNuxtRouteMiddleware(async (to) => {
  const session = useSession()
  if (to.path === '/login') {
    return
  }
  if (!session.me.value && !(await session.load())) {
    return navigateTo({ path: '/login', query: { next: to.fullPath } })
  }
  const required = to.meta.role as StaffRole | undefined
  if (required && !session.can(required)) {
    return navigateTo('/orders')
  }
})

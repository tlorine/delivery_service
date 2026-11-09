/**
 * Mobile app: no cafe selected → "Мои заведения". Links /t/<slug> opened inside the app select the cafe.
 * On the web the cafe comes from the domain, so this middleware does nothing there.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  if (usePlatform() !== 'mobile') {
    return
  }
  const venues = useVenues()
  const linked = to.path.startsWith('/t/') ? venueFromInput(to.path.slice(3)) : null
  if (linked) {
    if (await venues.open(linked)) {
      return reloadNuxtApp({ path: '/', force: true })
    }
    return navigateTo('/venues?error=not-found', { replace: true })
  }
  if (!venues.current.value && to.path !== '/venues') {
    return navigateTo('/venues', { replace: true })
  }
})

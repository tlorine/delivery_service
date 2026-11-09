/**
 * Native shell integration (Capacitor): Android back button and opening a cafe from a link or QR code.
 * Loaded only in the mobile build; the web storefront does not import Capacitor plugins.
 */
export default defineNuxtPlugin(async () => {
  if (useRuntimeConfig().public.platform !== 'mobile') {
    return
  }
  const { Capacitor } = await import('@capacitor/core')
  if (!Capacitor.isNativePlatform()) {
    return
  }
  const { App } = await import('@capacitor/app')
  const router = useRouter()
  const venues = useVenues()

  // Android hardware back: navigate back, or leave the app from the first screen.
  await App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack && window.history.length > 1) {
      router.back()
    } else {
      App.exitApp()
    }
  })

  // https://<app-domain>/t/<slug> (App/Universal Links) or <scheme>://t/<slug>
  const openLink = async (url: string) => {
    const slug = venueFromLink(url)
    if (slug && (await venues.open(slug))) {
      reloadNuxtApp({ path: '/', force: true })
    }
  }
  await App.addListener('appUrlOpen', ({ url }) => openLink(url))
  const launch = await App.getLaunchUrl()
  if (launch?.url) {
    await openLink(launch.url)
  }
})

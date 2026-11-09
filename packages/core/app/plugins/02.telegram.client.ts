const SCRIPT = 'https://telegram.org/js/telegram-web-app.js'
const FLAG = 'opened-in-telegram'

function openedInTelegram(): boolean {
  if (window.location.hash.includes('tgWebAppData')) {
    try {
      sessionStorage.setItem(FLAG, '1')
    } catch {}
    return true
  }
  try {
    return sessionStorage.getItem(FLAG) === '1'
  } catch {
    return false
  }
}

function loadScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    const el = document.createElement('script')
    el.src = SCRIPT
    el.onload = () => resolve()
    el.onerror = () => reject(new Error('telegram script failed'))
    document.head.appendChild(el)
  })
}

/**
 * Activates the Telegram adapter only inside Telegram: ordinary web visitors make no request to telegram.org.
 */
export default defineNuxtPlugin(async (nuxtApp) => {
  if (!window.Telegram?.WebApp) {
    if (!openedInTelegram()) {
      return
    }
    try {
      await loadScript()
    } catch {
      return
    }
  }
  const app = window.Telegram?.WebApp
  if (!app?.initData) {
    return // the script is present but we are not inside a Mini App
  }

  useState<boolean>('telegram-active').value = true
  app.ready()
  app.expand()

  // Theme: follow Telegram's light/dark scheme and paint the native header like the page.
  const applyTheme = () => {
    const colorMode = (nuxtApp.vueApp.config.globalProperties as { $colorMode?: { preference: string } }).$colorMode
    if (colorMode) {
      colorMode.preference = app.colorScheme
    }
    const root = document.documentElement.style
    for (const [key, value] of Object.entries(app.themeParams)) {
      if (value) {
        root.setProperty(`--tg-theme-${key.replaceAll('_', '-')}`, value)
      }
    }
    if (app.themeParams.bg_color) {
      app.setHeaderColor?.(app.themeParams.bg_color)
      app.setBackgroundColor?.(app.themeParams.bg_color)
    }
  }
  const applyViewport = () => {
    document.documentElement.style.setProperty('--tg-viewport-height', `${app.viewportStableHeight}px`)
  }
  applyTheme()
  applyViewport()
  app.onEvent('themeChanged', applyTheme)
  app.onEvent('viewportChanged', applyViewport)

  // Native back button instead of browser history UI.
  const router = useRouter()
  app.BackButton.onClick(() => router.back())
  const syncBack = (path: string) => path === '/' ? app.BackButton.hide() : app.BackButton.show()
  syncBack(router.currentRoute.value.path)
  router.afterEach((to) => syncBack(to.path))
})

import type { CapacitorConfig } from '@capacitor/cli'

/**
 * One platform app (decision D2): the storefront SPA build inside a native shell.
 * appId / appName are placeholders until the owner fixes them: the bundle id is permanent once published.
 */
const config: CapacitorConfig = {
  appId: 'ru.example.cafeorders',
  appName: 'Заказ в кафе',
  // `pnpm --filter @nextorders/web-app generate:mobile` (NUXT_PUBLIC_API_BASE_URL=https://api.<platform>)
  webDir: '../web-app/.output-mobile/public',
  android: {
    // WebView origin https://localhost (must be in the API's CORS_ORIGINS)
    allowMixedContent: false,
  },
  server: {
    androidScheme: 'https',
    // iOS origin is capacitor://localhost (also in CORS_ORIGINS)
  },
  plugins: {
    // No native splash plugin: the web layer renders immediately.
  },
}

export default config

/** Minimal typing of Telegram.WebApp (https://core.telegram.org/bots/webapps). */
export interface TelegramWebApp {
  initData: string
  initDataUnsafe: { user?: { first_name?: string } }
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string | undefined>
  viewportStableHeight: number
  ready: () => void
  expand: () => void
  close: () => void
  onEvent: (event: string, cb: () => void) => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  enableClosingConfirmation: () => void
  disableClosingConfirmation: () => void
  BackButton: { show: () => void, hide: () => void, onClick: (cb: () => void) => void, offClick: (cb: () => void) => void }
  MainButton: {
    setParams: (p: { text?: string, is_active?: boolean, is_visible?: boolean }) => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
    showProgress: (leaveActive?: boolean) => void
    hideProgress: () => void
  }
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy') => void
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void
  }
}

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp } }
}

/**
 * Telegram platform adapter. Everything is a no-op outside Telegram, so shared components call it freely.
 * initDataUnsafe is used only for display (name prefill), never for authorization (ADR-0007).
 */
export function useTelegram() {
  const active = useState<boolean>('telegram-active', () => false)

  function webApp(): TelegramWebApp | undefined {
    return import.meta.client && active.value ? window.Telegram?.WebApp : undefined
  }

  return {
    isActive: computed(() => active.value),
    webApp,
    initData: () => webApp()?.initData || undefined,
    firstName: () => webApp()?.initDataUnsafe.user?.first_name,
    impact: (style: 'light' | 'medium' | 'heavy' = 'light') => webApp()?.HapticFeedback.impactOccurred(style),
    notify: (type: 'error' | 'success' | 'warning') => webApp()?.HapticFeedback.notificationOccurred(type),
    close: () => webApp()?.close(),
    setClosingConfirmation: (on: boolean) => on ? webApp()?.enableClosingConfirmation() : webApp()?.disableClosingConfirmation(),
  }
}

/** Telegram's native bottom button bound to reactive state; removed when the component unmounts. */
export function useTelegramMainButton(options: {
  text: MaybeRefOrGetter<string>
  enabled: MaybeRefOrGetter<boolean>
  loading?: MaybeRefOrGetter<boolean>
  /** Only one visible owner per screen: Telegram calls every registered click handler. */
  visible?: MaybeRefOrGetter<boolean>
  onClick: () => void
}) {
  const { webApp, isActive } = useTelegram()
  const visible = () => toValue(options.visible ?? true)
  const handler = () => {
    if (visible()) {
      options.onClick()
    }
  }

  onMounted(() => {
    const app = webApp()
    if (!app) {
      return
    }
    app.MainButton.onClick(handler)
    watchEffect(() => {
      if (!visible()) {
        app.MainButton.setParams({ is_visible: false })
        return
      }
      app.MainButton.setParams({ text: toValue(options.text), is_active: toValue(options.enabled), is_visible: true })
      if (toValue(options.loading)) {
        app.MainButton.showProgress(false)
      } else {
        app.MainButton.hideProgress()
      }
    })
  })
  onBeforeUnmount(() => {
    const app = webApp()
    app?.MainButton.offClick(handler)
    app?.MainButton.setParams({ is_visible: false })
  })
  return { isActive }
}

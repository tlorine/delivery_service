import { Preferences } from '@capacitor/preferences'

/**
 * Mobile persistence. Pages read localStorage synchronously; every write is mirrored to Capacitor
 * Preferences (native storage), because iOS may evict WebView localStorage under storage pressure.
 * On start, restoreMobileStorage() copies Preferences back before the app reads anything.
 */
const PREFIX = 'app:'

export function mobileGet(key: string): string | null {
  try {
    return localStorage.getItem(PREFIX + key)
  } catch {
    return null
  }
}

export function mobileSet(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(PREFIX + key)
    } else {
      localStorage.setItem(PREFIX + key, value)
    }
  } catch {}
  const op = value === null ? Preferences.remove({ key: PREFIX + key }) : Preferences.set({ key: PREFIX + key, value })
  op.catch(() => {}) // on the web build Preferences falls back to localStorage itself
}

export async function restoreMobileStorage(): Promise<void> {
  try {
    const { keys } = await Preferences.keys()
    for (const key of keys.filter((k) => k.startsWith(PREFIX))) {
      if (localStorage.getItem(key) === null) {
        const { value } = await Preferences.get({ key })
        if (value !== null) {
          localStorage.setItem(key, value)
        }
      }
    }
  } catch {}
}

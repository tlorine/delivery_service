import type { SavedVenue } from '../utils/venues'

const LIST_KEY = 'venues'
const CURRENT_KEY = 'current-venue'

/** Mobile only: the cafe the app works with now, and "Мои заведения". */
export function useVenues() {
  const current = useState<string | null>('venue-current', () => (import.meta.client ? mobileGet(CURRENT_KEY) : null))
  const list = useState<SavedVenue[]>('venue-list', () => {
    if (!import.meta.client) {
      return []
    }
    try {
      return JSON.parse(mobileGet(LIST_KEY) ?? '[]') as SavedVenue[]
    } catch {
      return []
    }
  })

  function save() {
    mobileSet(LIST_KEY, JSON.stringify(list.value))
  }

  /** Verifies the code with the API (X-Tenant), remembers the cafe and makes it current. */
  async function open(slug: string): Promise<SavedVenue | null> {
    try {
      const sf = await useNuxtApp().$api.get('/v1/storefront', { headers: { 'X-Tenant': slug } })
      const venue: SavedVenue = {
        slug: sf.slug,
        name: sf.name,
        logoUrl: typeof sf.branding.logo_url === 'string' ? sf.branding.logo_url : undefined,
        openedAt: Date.now(),
      }
      list.value = rememberVenue(list.value, venue)
      save()
      current.value = venue.slug
      mobileSet(CURRENT_KEY, venue.slug)
      return venue
    } catch {
      return null
    }
  }

  function forget(slug: string) {
    list.value = forgetVenue(list.value, slug)
    save()
    mobileSet(`cart_token:${slug}`, null)
    if (current.value === slug) {
      current.value = null
      mobileSet(CURRENT_KEY, null)
    }
  }

  function leave() {
    current.value = null
    mobileSet(CURRENT_KEY, null)
  }

  return { current, list, open, forget, leave }
}

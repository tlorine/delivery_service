/**
 * Mobile app venues (D2): one platform app without a public catalogue. A user reaches a cafe by QR code,
 * link or from Telegram; "Мои заведения" lists only cafes the user opened. Pure functions, unit-tested.
 */
export interface SavedVenue {
  slug: string
  name: string
  logoUrl?: string
  openedAt: number
}

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/
const MAX_VENUES = 20

export function isVenueSlug(value: string): boolean {
  return SLUG_RE.test(value)
}

/**
 * Venue slug from a link: https://<app-domain>/t/<slug>, <scheme>://t/<slug> or ?venue=<slug>.
 * Returns null for anything else (links never carry tokens or other data we would trust).
 */
export function venueFromLink(link: string): string | null {
  let url: URL
  try {
    url = new URL(link)
  } catch {
    return null
  }
  // Custom schemes put "t" into the host: myapp://t/demo
  const parts = [url.host, ...url.pathname.split('/')].filter(Boolean)
  const i = parts.indexOf('t')
  const candidate = (i >= 0 ? parts[i + 1] : url.searchParams.get('venue'))?.toLowerCase() ?? ''
  return isVenueSlug(candidate) ? candidate : null
}

/** Code typed by a user: a slug or a pasted link. */
export function venueFromInput(input: string): string | null {
  const value = input.trim()
  if (!value) {
    return null
  }
  const lower = value.toLowerCase()
  return isVenueSlug(lower) ? lower : venueFromLink(value)
}

export function rememberVenue(list: SavedVenue[], venue: SavedVenue): SavedVenue[] {
  return [venue, ...list.filter((v) => v.slug !== venue.slug)].slice(0, MAX_VENUES)
}

export function forgetVenue(list: SavedVenue[], slug: string): SavedVenue[] {
  return list.filter((v) => v.slug !== slug)
}

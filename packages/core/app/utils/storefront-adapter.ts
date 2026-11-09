/**
 * Adapter from the platform API (OpenAPI types, ADR-0003) to the storefront view models in
 * @nextorders/food-schema, so existing components keep working. Pure functions: no Nuxt globals.
 *
 * Money: the API sends integer minor units; view models carry rubles **for display only** (ADR-0008).
 * Nothing produced here is ever sent back to the server.
 */
import type { Branch, Cart, Menu, ModifierGroup, Storefront } from '@delivery/api-client'
import type {
  Channel,
  DaySchedule,
  Locale,
  LocaleValue,
  MenuCategory,
  OpeningStatus,
  Options,
  OrderItem,
  PaymentMethod,
  Schedule,
  TimeZone,
  WeekDay,
  WeightUnit,
} from '@nextorders/food-schema'

const WEEKDAYS: WeekDay[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] // API weekday 0 = Monday
const SUPPORTED_LOCALES: Locale[] = ['ru', 'en']
const GMT_OFFSET_RE = /GMT([+-]\d{2}):?(\d{2})?/
const WEIGHT_UNITS = new Set<WeightUnit>(['g', 'kg', 'ml', 'l', 'oz', 'lb'])

const PAYMENT_TITLES: Record<string, Record<'ru' | 'en', string>> = {
  cash: { ru: 'Наличными', en: 'Cash' },
  card_on_delivery: { ru: 'Картой при получении', en: 'Card on receipt' },
  online: { ru: 'Онлайн', en: 'Online' },
}

/** Display-only conversion. Never use the result for arithmetic sent to the server. */
export function minorToDisplay(minor: number): number {
  return minor / 100
}

export function localeValue(value: string | null | undefined, locale: string): LocaleValue[] {
  return value ? [{ locale: asLocale(locale), value }] : []
}

function asLocale(locale: string): Locale {
  return (SUPPORTED_LOCALES as string[]).includes(locale) ? locale as Locale : 'ru'
}

export function paymentMethodView(id: string): PaymentMethod {
  const titles = PAYMENT_TITLES[id] ?? { ru: id, en: id }
  return {
    id,
    type: id === 'cash' ? 'cash' : id === 'card_on_delivery' ? 'card' : 'custom',
    title: [{ locale: 'ru', value: titles.ru }, { locale: 'en', value: titles.en }],
  }
}

// ---- time ---------------------------------------------------------------------------------------

interface LocalParts { weekday: WeekDay, time: string, date: string }

export function localParts(iso: string | Date, timeZone: string): LocalParts {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    weekday: 'short',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso))
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return {
    weekday: get('weekday').toLowerCase().slice(0, 3) as WeekDay,
    time: `${get('hour')}:${get('minute')}`,
    date: `${get('year')}-${get('month')}-${get('day')}`,
  }
}

/** '+03:00' for food-schema; the API works with IANA zones. */
export function utcOffset(timeZone: string, at: Date = new Date()): TimeZone {
  const name = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'longOffset' })
    .formatToParts(at)
    .find((p) => p.type === 'timeZoneName')
    ?.value ?? 'GMT'
  const match = GMT_OFFSET_RE.exec(name)
  return (match ? `${match[1]}:${match[2] ?? '00'}` : '+00:00') as TimeZone
}

function hhmm(time: string): string {
  return time.slice(0, 5)
}

export function scheduleView(branch: Branch): Schedule {
  return WEEKDAYS.map((day, index): DaySchedule => {
    const hours = branch.hours.filter((h) => h.weekday === index)
    return {
      day,
      isClosed: hours.length === 0,
      hours: hours.map((h) => ({ start: hhmm(h.opens_at), end: hhmm(h.closes_at) })),
    }
  })
}

function daysBetween(fromDate: string, toDate: string): number {
  return Math.round((Date.parse(`${toDate}T00:00:00Z`) - Date.parse(`${fromDate}T00:00:00Z`)) / 86_400_000)
}

export function openingStatusView(branch: Branch, serverTime: string): OpeningStatus {
  const now = localParts(serverTime, branch.timezone)
  const todayIndex = WEEKDAYS.indexOf(now.weekday)
  const today = branch.hours.filter((h) => h.weekday === todayIndex)
  const closes = branch.closes_at ? localParts(branch.closes_at, branch.timezone) : null
  const next = branch.next_opening_at ? localParts(branch.next_opening_at, branch.timezone) : null
  return {
    isClosed: !branch.is_open_now,
    timeZone: utcOffset(branch.timezone, new Date(serverTime)),
    currentTime: now.time,
    currentDay: now.weekday,
    todayHours: today.length ? today.map((h) => ({ start: hhmm(h.opens_at), end: hhmm(h.closes_at) })) : null,
    todayEndAt: closes?.time ?? null,
    todayEndInMinutes: branch.closes_at
      ? Math.max(0, Math.floor((Date.parse(branch.closes_at) - Date.parse(serverTime)) / 60_000))
      : null,
    nextOpening: next ? { day: next.weekday, time: next.time, relativeDays: daysBetween(now.date, next.date) } : null,
  }
}

// ---- storefront ---------------------------------------------------------------------------------

export function deliveryBranches(sf: Storefront): Branch[] {
  // Delivery needs coordinates from address suggestions; without them only pickup is offered.
  return sf.address_suggest_enabled ? sf.branches.filter((b) => b.delivery_enabled) : []
}

export function pickupBranches(sf: Storefront): Branch[] {
  return sf.branches.filter((b) => b.pickup_enabled)
}

function uniqueMethods(branches: Branch[]): PaymentMethod[] {
  return Array.from(new Set(branches.flatMap((b) => b.payment_methods)), paymentMethodView)
}

export function channelView(sf: Storefront): Channel {
  const locale = sf.locale
  const delivery = deliveryBranches(sf)
  const pickup = pickupBranches(sf)
  const main = sf.branches[0]
  const branding = sf.branding as { description?: string, copyright?: string }
  return {
    id: sf.slug,
    selectorTitle: localeValue(sf.name, locale),
    title: localeValue(sf.name, locale),
    description: localeValue(branding.description, locale),
    url: '',
    timeZone: main ? utcOffset(main.timezone, new Date(sf.server_time)) : '+03:00',
    isActive: sf.branches.length > 0,
    deliveryByCourier: {
      isAvailable: delivery.length > 0,
      paymentMethods: uniqueMethods(delivery),
      schedule: delivery[0] ? scheduleView(delivery[0]) : undefined,
    },
    selfPickup: {
      isAvailable: pickup.length > 0,
      paymentMethods: uniqueMethods(pickup),
      schedule: pickup[0] ? scheduleView(pickup[0]) : undefined,
      warehouses: pickup.map((b) => ({
        id: b.id,
        title: localeValue(b.name, locale),
        address: { street: localeValue(b.address, locale) },
      })),
    },
    copyright: localeValue(branding.copyright ?? sf.name, locale),
  }
}

export function optionsView(sf: Storefront): Options {
  const branding = sf.branding as { logo_url?: string, description?: string }
  return {
    selectorTitle: localeValue(sf.name, sf.locale),
    selectorDescription: localeValue(branding.description, sf.locale),
    logoUrl: branding.logo_url,
    availableLocales: SUPPORTED_LOCALES,
    defaultLocale: asLocale(sf.locale),
    countryCode: sf.country as Options['countryCode'],
    currencyCode: sf.currency as Options['currencyCode'],
    addressSuggestEnabled: sf.address_suggest_enabled,
    deliveryZonesEnabled: sf.address_suggest_enabled,
  }
}

// ---- menu ---------------------------------------------------------------------------------------

export function menuView(menu: Menu, locale: string): MenuCategory[] {
  return menu.categories.map((c) => ({
    id: c.id,
    slug: c.slug,
    title: localeValue(c.name, locale),
    products: c.products.map((p) => ({
      id: p.id,
      slug: p.slug,
      title: localeValue(p.name, locale),
      description: p.description ? localeValue(p.description, locale) : undefined,
      isAvailableForPurchase: p.available,
      isShownInCatalog: true,
      variants: p.variants.map((v) => ({
        id: v.id,
        title: localeValue(v.name, locale),
        images: p.image_url ? [{ id: p.id, url: p.image_url, size: 'md' as const, format: 'jpeg' as const }] : [],
        weightUnit: v.weight_unit && WEIGHT_UNITS.has(v.weight_unit as WeightUnit) ? v.weight_unit as WeightUnit : 'g',
        weightValue: v.weight_value ?? 0,
        price: minorToDisplay(v.price_minor),
        sku: null,
        nutritionFacts: null,
      })),
    })),
  }))
}

export function modifierGroupsByProduct(menu: Menu): Record<string, ModifierGroup[]> {
  const result: Record<string, ModifierGroup[]> = {}
  for (const c of menu.categories) {
    for (const p of c.products) {
      result[p.id] = p.modifier_groups
    }
  }
  return result
}

// ---- cart ---------------------------------------------------------------------------------------

export interface CartLineView extends OrderItem {
  productName: string
  variantName: string
  modifiers: { id: string, name: string, quantity: number }[]
  problems: { code: string, detail: string }[]
}

export function cartLinesView(cart: Cart): CartLineView[] {
  return cart.items.map((line) => ({
    id: line.id,
    orderId: cart.id,
    productId: line.product_id ?? '',
    productSlug: '',
    categoryId: '',
    categorySlug: '',
    variantId: line.variant_id,
    quantity: Math.max(line.quantity, 1),
    unitPrice: minorToDisplay(line.unit_price_minor),
    totalPrice: minorToDisplay(line.line_total_minor),
    productName: line.product_name,
    variantName: line.variant_name,
    modifiers: line.modifiers.map((m) => ({ id: m.modifier_id, name: m.name, quantity: m.quantity })),
    problems: line.problems,
  }))
}

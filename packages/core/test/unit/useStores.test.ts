import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, reactive, ref } from 'vue'
import * as adapter from '../../app/utils/storefront-adapter'
import { storefront } from '../fixtures/storefront'

const setups: Record<string, () => any> = {}
vi.stubGlobal('defineStore', (name: string, setup: () => any) => {
  setups[name] = setup
  return () => setup()
})
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('useI18n', () => ({ locale: ref('ru'), locales: ref([{ code: 'ru', language: 'ru-RU' }]) }))
for (const [name, fn] of Object.entries(adapter)) {
  vi.stubGlobal(name, fn) // Nuxt auto-imports utils
}

const data = ref<typeof storefront | null>(null)
const update = vi.fn()
vi.stubGlobal('useStorefrontStore', () => reactive({ data, update }))
const apiGet = vi.fn()
vi.stubGlobal('useNuxtApp', () => ({ $api: { get: apiGet } }))

await import('../../app/composables/useChannelStore')
await import('../../app/composables/useOptionsStore')

describe('channel and options stores are views over /v1/storefront', () => {
  beforeEach(() => {
    data.value = null
    vi.clearAllMocks()
  })

  it('show nothing and no maintenance banner before the first load', () => {
    const channel = setups.channel!()
    expect(channel.isActive.value).toBe(false)
    expect(channel.isOnMaintenance.value).toBe(false)
  })

  it('expose the tenant once loaded', () => {
    data.value = storefront
    const channel = setups.channel!()
    const options = setups.options!()
    expect(channel.isActive.value).toBe(true)
    expect(channel.selfPickup.value?.warehouses).toHaveLength(2)
    expect(channel.deliveryOpeningStatus.value?.isClosed).toBe(false)
    expect(options.countryCode.value).toBe('RU')
    expect(options.getLocaleValue(channel.title.value)).toBe('Демо-кафе')
  })

  it('a tenant without branches is in maintenance', () => {
    data.value = { ...storefront, branches: [] }
    expect(setups.channel!().isOnMaintenance.value).toBe(true)
  })

  it('loads time slots labelled in the branch time zone', async () => {
    data.value = storefront
    apiGet.mockResolvedValue(['2026-11-10T10:30:00Z'])
    const channel = setups.channel!()
    await channel.updateTimeSlots('b1', 'delivery')
    expect(apiGet).toHaveBeenCalledWith('/v1/storefront/time-slots', { query: { branch_id: 'b1', fulfillment: 'delivery' } })
    expect(channel.timeSlots.value).toEqual([{ value: '2026-11-10T10:30:00Z', label: '13:30' }])
  })

  it('formats display amounts in the app locale', () => {
    data.value = storefront
    const options = setups.options!()
    expect(options.formatCurrency(390.5).replace(/\s/g, ' ')).toBe('390,5')
  })
})

import { describe, expect, it } from 'vitest'
import {
  cartLinesView,
  channelView,
  localParts,
  menuView,
  minorToDisplay,
  modifierGroupsByProduct,
  openingStatusView,
  optionsView,
  paymentMethodView,
  scheduleView,
  utcOffset,
} from '../../app/utils/storefront-adapter'
import { cart, menu, SERVER_TIME, storefront } from '../fixtures/storefront'

describe('storefront adapter', () => {
  it('maps the tenant to a channel with branches as pickup points', () => {
    const channel = channelView(storefront)
    expect(channel.title).toEqual([{ locale: 'ru', value: 'Демо-кафе' }])
    expect(channel.isActive).toBe(true)
    expect(channel.deliveryByCourier.isAvailable).toBe(true)
    expect(channel.selfPickup.warehouses?.map((w) => w.id)).toEqual(['b1', 'b2'])
    expect(channel.selfPickup.paymentMethods.map((p) => p.id)).toEqual(['cash', 'card_on_delivery'])
    expect(channel.timeZone).toBe('+03:00')
  })

  it('offers no delivery without address suggestions (no coordinates, no zone pricing)', () => {
    const channel = channelView({ ...storefront, address_suggest_enabled: false })
    expect(channel.deliveryByCourier.isAvailable).toBe(false)
    expect(channel.selfPickup.isAvailable).toBe(true)
  })

  it('maps options', () => {
    const options = optionsView(storefront)
    expect(options.defaultLocale).toBe('ru')
    expect(options.currencyCode).toBe('RUB')
    expect(options.logoUrl).toBe('/logo.png')
  })

  it('builds the opening status in the branch time zone', () => {
    const status = openingStatusView(storefront.branches[0]!, SERVER_TIME)
    expect(status.isClosed).toBe(false)
    expect(status.currentDay).toBe('tue')
    expect(status.currentTime).toBe('12:00')
    expect(status.todayHours).toEqual([{ start: '10:00', end: '23:00' }])
    expect(status.todayEndAt).toBe('23:00')
    expect(status.todayEndInMinutes).toBe(660)
    expect(status.nextOpening).toEqual({ day: 'wed', time: '10:00', relativeDays: 1 })
  })

  it('builds a 7-day schedule with closed days', () => {
    const schedule = scheduleView(storefront.branches[0]!)
    expect(schedule).toHaveLength(7)
    expect(schedule[0]).toEqual({ day: 'mon', isClosed: false, hours: [{ start: '10:00', end: '23:00' }] })
    expect(schedule[6]).toEqual({ day: 'sun', isClosed: true, hours: [] })
  })

  it('maps the menu with display prices and keeps modifier groups aside', () => {
    const [category] = menuView(menu, 'ru')
    const variant = category!.products[0]!.variants[0]!
    expect(variant.price).toBe(390.5)
    expect(variant.images[0]).toMatchObject({ url: 'https://cdn.test/p1.jpg', format: 'jpeg' })
    expect(modifierGroupsByProduct(menu).p1?.[0]?.name).toBe('Соус')
  })

  it('maps cart lines with modifiers and unit prices', () => {
    const [line] = cartLinesView(cart)
    expect(line).toMatchObject({ id: 'i1', productId: 'p1', quantity: 2, unitPrice: 430.5, totalPrice: 861 })
    expect(line!.modifiers).toEqual([{ id: 'm1', name: 'Сырный', quantity: 1 }])
  })

  it('has helpers for display only', () => {
    expect(minorToDisplay(12_345)).toBe(123.45)
    expect(paymentMethodView('cash').type).toBe('cash')
    expect(paymentMethodView('card_on_delivery').title[0]).toEqual({ locale: 'ru', value: 'Картой при получении' })
    expect(utcOffset('Asia/Kamchatka', new Date(SERVER_TIME))).toBe('+12:00')
    expect(localParts('2026-11-10T21:30:00Z', 'Europe/Moscow')).toEqual({ weekday: 'wed', time: '00:30', date: '2026-11-11' })
  })
})

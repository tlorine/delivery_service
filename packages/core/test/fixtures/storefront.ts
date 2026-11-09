import type { Cart, Menu, Storefront } from '@delivery/api-client'

// Tuesday 2026-11-10 12:00 in Sochi (UTC+3)
export const SERVER_TIME = '2026-11-10T09:00:00Z'

export const storefront: Storefront = {
  slug: 'demo',
  name: 'Демо-кафе',
  currency: 'RUB',
  country: 'RU',
  locale: 'ru',
  branding: { logo_url: '/logo.png' },
  server_time: SERVER_TIME,
  address_suggest_enabled: true,
  branches: [
    {
      id: 'b1',
      name: 'Курортный',
      address: 'Сочи, Курортный проспект, 18',
      lat: 43.58,
      lon: 39.72,
      phone: null,
      timezone: 'Europe/Moscow',
      delivery_enabled: true,
      pickup_enabled: true,
      payment_methods: ['cash', 'card_on_delivery'],
      prep_time_min: 20,
      delivery_time_min: 40,
      is_open_now: true,
      closes_at: '2026-11-10T20:00:00Z',
      next_opening_at: '2026-11-11T07:00:00Z',
      hours: [0, 1, 2, 3, 4, 5].map((weekday) => ({ weekday, opens_at: '10:00:00', closes_at: '23:00:00' })),
    },
    {
      id: 'b2',
      name: 'Только самовывоз',
      address: 'Сочи, Навагинская, 9',
      lat: null,
      lon: null,
      phone: null,
      timezone: 'Europe/Moscow',
      delivery_enabled: false,
      pickup_enabled: true,
      payment_methods: ['cash'],
      prep_time_min: 15,
      delivery_time_min: 0,
      is_open_now: false,
      closes_at: null,
      next_opening_at: null,
      hours: [],
    },
  ],
}

export const menu: Menu = {
  currency: 'RUB',
  branch_id: null,
  categories: [{
    id: 'c1',
    slug: 'burgers',
    name: 'Бургеры',
    products: [{
      id: 'p1',
      slug: 'cheeseburger',
      name: 'Чизбургер',
      description: null,
      image_url: 'https://cdn.test/p1.jpg',
      available: true,
      variants: [{ id: 'v1', name: 'Стандарт', price_minor: 39_050, weight_value: 280, weight_unit: 'g', available: true }],
      modifier_groups: [{
        id: 'g1',
        name: 'Соус',
        min_selected: 1,
        max_selected: 1,
        modifiers: [{ id: 'm1', name: 'Сырный', price_minor: 4_000, max_quantity: 1, available: true }],
      }],
    }],
  }],
}

export const cart: Cart = {
  id: 'cart1',
  currency: 'RUB',
  item_count: 2,
  subtotal_minor: 86_100,
  has_problems: false,
  items: [{
    id: 'i1',
    variant_id: 'v1',
    product_id: 'p1',
    product_name: 'Чизбургер',
    variant_name: 'Стандарт',
    quantity: 2,
    unit_price_minor: 43_050,
    line_total_minor: 86_100,
    modifiers: [{ modifier_id: 'm1', group_name: 'Соус', name: 'Сырный', unit_price_minor: 4_000, quantity: 1 }],
    problems: [],
  }],
}

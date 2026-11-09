import type { APIRequestContext, Page } from '@playwright/test'
import process from 'node:process'
import { expect } from '@playwright/test'

export const API = `http://localhost:${process.env.E2E_API_PORT ?? 8078}`
// The storefront API resolves the demo cafe by Host.
const SHOP = { Host: 'localhost' }

const ORDERS_URL = /\/orders/

export const USERS = {
  owner: { email: 'owner@demo.local', password: 'e2e-owner-pass' },
  manager: { email: 'manager@demo.local', password: 'e2e-staff-pass' },
  operator: { email: 'operator@demo.local', password: 'e2e-staff-pass' },
}

export async function login(page: Page, who: keyof typeof USERS) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(USERS[who].email)
  await page.getByLabel('Пароль').fill(USERS[who].password)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page).toHaveURL(ORDERS_URL)
}

/** A buyer places a pickup order through the public API (fast setup for staff scenarios). */
export async function placeOrder(request: APIRequestContext, comment = 'E2E'): Promise<{ id: string, number: number, token: string }> {
  const sf = await (await request.get(`${API}/v1/storefront`, { headers: SHOP })).json()
  const menu = await (await request.get(`${API}/v1/storefront/menu`, { headers: SHOP })).json()
  const burger = menu.categories.flatMap((c: any) => c.products).find((p: any) => p.slug === 'double-burger')
  const cart = await (await request.post(`${API}/v1/carts`, { headers: SHOP })).json()
  const headers = { ...SHOP, 'X-Cart-Token': cart.cart_token }
  await request.post(`${API}/v1/cart/items`, { headers, data: { variant_id: burger.variants[0].id, quantity: 1 } })
  const r = await request.post(`${API}/v1/orders`, {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
    data: {
      fulfillment: 'pickup',
      branch_id: sf.branches[0].id,
      payment_method: 'cash',
      comment,
      customer: { name: 'Покупатель E2E', phone: '+7 918 555 44 33' },
      personal_data_consent: true,
    },
  })
  expect(r.status()).toBe(201)
  const body = await r.json()
  return { id: body.order.id, number: body.order.number, token: body.order_token }
}

export async function buyerSees(request: APIRequestContext, token: string): Promise<string> {
  return (await (await request.get(`${API}/v1/orders/${token}`, { headers: SHOP })).json()).status
}

export async function openNav(page: Page, isMobile: boolean) {
  if (isMobile) {
    await page.getByRole('button', { name: 'Открыть меню' }).click()
  }
}

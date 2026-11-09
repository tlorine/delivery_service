import type { APIRequestContext, Page } from '@playwright/test'
import process from 'node:process'
import { expect, test } from '@playwright/test'

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8078}`
const nbsp = (s: string | null) => (s ?? '').replace(/\s/g, ' ')

async function addCheeseburger(page: Page) {
  await page.goto('/burgers/cheeseburger')
  await expect(page.getByRole('heading', { name: 'Чизбургер' })).toBeVisible()
  await page.getByTestId('modifiers').getByText('Чесночный').click()
  await page.getByTestId('modifiers').getByText('Бекон').click()
  // 390 ₽ + bacon 80 ₽, computed for display; the server prices the line again.
  await expect(page.getByTestId('product-price')).toHaveText(/470/)
  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items') && r.request().method() === 'POST')
  await page.getByTestId('add-to-cart').click()
  expect((await added).status()).toBe(200)
}

async function confirmAsStaff(request: APIRequestContext, orderId: string) {
  const login = await request.post(`${API}/v1/admin/auth/login`, {
    data: { email: 'owner@demo.local', password: 'e2e-owner-pass' },
  })
  expect(login.ok()).toBeTruthy()
  const { token } = await login.json()
  const r = await request.post(`${API}/v1/admin/orders/${orderId}/transitions`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { to_status: 'confirmed' },
  })
  expect(r.status()).toBe(200)
}

test('guest orders delivery with modifiers and sees the cafe confirm it', async ({ page, request }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/Демо-кафе/)

  await addCheeseburger(page)
  await addCheeseburger(page) // same configuration merges into one line of 2

  await page.goto('/checkout')
  await expect(page.getByRole('heading', { name: 'Оформление заказа' })).toBeVisible()
  await expect(page.getByTestId('line-modifiers').first()).toContainText('Бекон')

  await page.getByLabel('Ваше имя').fill('Анна')
  await page.getByLabel('Ваш телефон').fill('9181234567')

  const street = page.getByLabel('Улица и дом')
  await street.fill('Курортный')
  await page.getByRole('option', { name: /Курортный пр-кт, д 18/ }).click()
  await page.getByLabel('Кв./офис').fill('12')

  // Zone "Центр": 150 ₽ delivery for 2 × 470 ₽ = 940 ₽ (min 700 ₽, free from 1500 ₽).
  await expect(page.getByText('Центр')).toBeVisible()
  await expect(page.getByTestId('delivery-fee')).toHaveText(/150/)

  await page.getByRole('combobox', { name: 'Метод оплаты' }).click()
  await page.getByRole('option', { name: 'Наличными' }).click()
  await page.getByTestId('pd-consent').click()

  await expect(page.getByTestId('grand-total')).toHaveText(/1\s?090/)
  await page.getByRole('button', { name: 'Создать заказ' }).click()

  await expect(page).toHaveURL(/\/finish\?id=/)
  await expect(page.getByTestId('order-status')).toHaveText('Ожидает подтверждения')
  expect(nbsp(await page.getByTestId('order-total').textContent())).toContain('1 090')

  const orderId = new URL(page.url()).searchParams.get('id')!
  expect(page.url()).not.toContain('.') // the access token never appears in the URL

  await confirmAsStaff(request, orderId)
  await page.reload()
  await expect(page.getByTestId('order-status')).toHaveText('Подтверждён')
})

test('address outside the delivery zone is refused before ordering', async ({ page }) => {
  await addCheeseburger(page)
  await page.goto('/checkout')
  await page.getByLabel('Улица и дом').fill('Адлерский')
  await page.getByRole('option', { name: /Адлерский/ }).click()
  await expect(page.getByText('Доставка по этому адресу недоступна')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Создать заказ' })).toBeDisabled()
})

test('client-side tampering cannot change the price', async ({ request }) => {
  // The browser never sends prices; a crafted request with a total is rejected by the schema.
  const cart = await (await request.post(`${API}/v1/carts`, { headers: { 'X-Tenant': 'demo', 'Host': 'localhost' } })).json()
  const r = await request.post(`${API}/v1/orders`, {
    headers: { 'Host': 'localhost', 'X-Cart-Token': cart.cart_token, 'Idempotency-Key': crypto.randomUUID() },
    data: { fulfillment: 'pickup', payment_method: 'cash', total_minor: 1, customer: { name: 'x', phone: '+79180000000' }, personal_data_consent: true },
  })
  expect(r.status()).toBe(422)
  expect((await r.json()).code).toBe('validation_error')
})

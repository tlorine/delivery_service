/**
 * Mobile app (Capacitor shell + storefront SPA, ADR-0005 A, decision D2): no public catalogue of cafes,
 * a cafe is opened by code/link; "Мои заведения" lists only opened cafes; one cart per cafe.
 * Runs the same SPA bundle the native shell loads, against the real API via the platform API host + X-Tenant.
 */
import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'

async function openByCode(page: Page, code: string) {
  await page.getByTestId('venue-code').fill(code)
  await page.getByTestId('venue-open').click()
}

test('first launch: no catalogue of cafes, only a code or link', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/venues/)
  await expect(page.getByRole('heading', { name: 'Мои заведения' })).toBeVisible()
  await expect(page.getByTestId('venues-empty')).toBeVisible()
  await expect(page.getByTestId('my-venues')).toHaveCount(0) // nothing listed that the user did not open

  await openByCode(page, 'not a code!')
  await expect(page.getByRole('alert')).toHaveText('Код — латинские буквы, цифры и дефис')
  await openByCode(page, 'no-such-cafe')
  await expect(page.getByRole('alert')).toHaveText('Заведение не найдено. Проверьте код.')
})

test('open a cafe by code, order, and find it again in "Мои заведения"', async ({ page }) => {
  const tenantHeaders: string[] = []
  page.on('request', (r) => {
    if (r.url().includes('/v1/')) {
      tenantHeaders.push(r.headers()['x-tenant'] ?? '')
    }
  })
  await page.goto('/venues')
  await openByCode(page, 'demo')
  await expect(page.getByTestId('store-hero')).toContainText('Демо-кафе «У моря»')
  // Every API call carries the chosen cafe; the server decides what it means (platform API host only).
  expect(tenantHeaders.filter((h) => h).every((h) => h === 'demo')).toBeTruthy()

  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items') && r.request().method() === 'POST')
  await page.getByTestId('card-double-burger').getByTestId('quick-add').click()
  expect((await added).status()).toBe(200)
  await page.getByTestId('card-double-burger').getByRole('button', { name: 'Увеличить' }).click()
  await page.getByTestId('cart-bar').click()
  await page.getByTestId('to-checkout').click()

  await page.getByRole('tab', { name: 'Самовывоз' }).click()
  await page.getByRole('combobox', { name: /Улица и дом/ }).click()
  await page.getByRole('option', { name: /Курортный/ }).click()
  await page.getByLabel('Ваш телефон').fill('9181234567')
  await page.getByLabel('Ваше имя').fill('Анна')
  await page.getByRole('combobox', { name: 'Метод оплаты' }).click()
  await page.getByRole('option', { name: 'Наличными' }).click()
  await page.getByTestId('pd-consent').click()
  const placed = page.waitForResponse((r) => r.url().endsWith('/v1/orders'))
  await page.getByRole('button', { name: /Создать заказ/ }).click()
  expect((await placed).status()).toBe(201)
  await expect(page.getByTestId('order-status')).toHaveText('Ожидает подтверждения')

  // Restart of the app: state survives (durable storage), the cafe is remembered.
  await page.goto('/')
  await expect(page.getByTestId('store-hero')).toBeVisible()
  await page.getByTestId('my-venues-button').click()
  await expect(page.getByTestId('my-venues')).toContainText('Демо-кафе «У моря»')
})

test('a link /t/<slug> (QR code, Telegram) opens the cafe directly', async ({ page }) => {
  await page.goto('/t/second')
  await expect(page.getByTestId('store-hero')).toContainText('Кофейня «Второе»')
})

test('each cafe has its own cart', async ({ page }) => {
  await page.goto('/t/demo')
  await expect(page.getByTestId('store-hero')).toBeVisible()
  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items') && r.request().method() === 'POST')
  await page.getByTestId('card-cola').getByTestId('quick-add').click()
  await added
  await expect(page.getByTestId('cart-bar')).toContainText('120')

  await page.goto('/t/second')
  await expect(page.getByTestId('store-hero')).toContainText('Кофейня «Второе»')
  await expect(page.getByTestId('cart-bar')).toHaveCount(0) // empty cart in the other cafe

  await page.getByTestId('my-venues-button').click()
  await page.getByTestId('my-venues').getByText('Демо-кафе «У моря»').click()
  await expect(page.getByTestId('cart-bar')).toContainText('120') // and the first cafe's cart is still there
})

test('no horizontal scroll on a small phone', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  await page.goto('/venues')
  const { sw, w } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: window.innerWidth }))
  expect(sw).toBeLessThanOrEqual(w)
})

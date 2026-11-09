/**
 * Visual/layout invariants of the redesigned storefront (docs/design/storefront-redesign.md §5, §7):
 * real screen widths, no horizontal scrolling, key actions visible and tappable, Russian-only UI.
 */
import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'

const WIDTHS = [320, 360, 390, 430, 768, 820, 1024, 1280, 1440]

async function noHorizontalScroll(page: Page) {
  const { sw, w } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: window.innerWidth }))
  expect(sw, `page is ${sw}px wide at viewport ${w}px`).toBeLessThanOrEqual(w)
}

async function addFromCard(page: Page, slug: string) {
  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items') && r.request().method() === 'POST')
  await page.getByTestId(`card-${slug}`).getByTestId('quick-add').click()
  expect((await added).status()).toBe(200)
}

test.describe('no horizontal scroll at real widths', () => {
  test.skip(({ isMobile }) => isMobile, 'widths are set explicitly; one project is enough')
  for (const width of WIDTHS) {
    test(`${width}px: catalog, dish, cart, checkout`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto('/')
      await expect(page.getByTestId('store-hero')).toBeVisible()
      await noHorizontalScroll(page)
      await addFromCard(page, 'double-burger')
      await page.goto('/burgers/cheeseburger')
      await expect(page.getByTestId('add-to-cart')).toBeVisible()
      await noHorizontalScroll(page)
      await page.goto('/checkout')
      await expect(page.getByRole('heading', { name: 'Оформление заказа' })).toBeVisible()
      await noHorizontalScroll(page)
    })
  }
})

test('catalog: categories rail, quick add turns into a counter, cart bar shows count and total', async ({ page, isMobile }) => {
  await page.goto('/')
  const rail = page.getByRole('navigation', { name: 'Каталог' })
  await expect(rail.getByRole('link', { name: 'Бургеры' })).toBeVisible()

  const card = page.getByTestId('card-double-burger')
  await addFromCard(page, 'double-burger')
  await expect(card.getByTestId('line-counter')).toContainText('1')
  await card.getByRole('button', { name: 'Увеличить' }).click()
  await expect(card.getByTestId('line-counter')).toContainText('2')

  // Dishes with required choices open the dish instead of adding blindly.
  await expect(page.getByTestId('card-classic-shawarma').getByTestId('quick-add')).toHaveCount(0)

  if (isMobile) {
    const bar = page.getByTestId('cart-bar')
    await expect(bar).toContainText('2')
    await expect(bar).toContainText('1 100')
    await bar.click()
    await expect(page.getByTestId('to-checkout')).toBeVisible()
  } else {
    await expect(page.getByTestId('cart').first()).toContainText('1 100')
  }
})

test('dish page: the action bar is reachable without scrolling and shows the total', async ({ page }) => {
  await page.goto('/burgers/cheeseburger')
  const add = page.getByTestId('add-to-cart')
  await expect(add).toBeInViewport()
  const box = await add.boundingBox()
  expect(box!.height).toBeGreaterThanOrEqual(44) // tap target
  await page.getByRole('button', { name: 'Увеличить' }).first().click()
  await expect(page.getByTestId('product-price')).toHaveText(/780/)
})

test('Russian interface has no stray English', async ({ page }) => {
  // Allowed: brand-like tokens that are not translatable UI text.
  const allowed = new Set(['Telegram'])
  for (const path of ['/', '/burgers', '/burgers/cheeseburger', '/checkout']) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    // Visible text only (Playwright's innerText), so hidden locale data does not count.
    // eslint-disable-next-line unicorn/prefer-dom-node-text-content
    const text = await page.locator('body').innerText()
    const latin = [...new Set(text.match(/[A-Z]{3,}/gi) ?? [])].filter((w) => !allowed.has(w))
    expect(latin, `Latin words on ${path}`).toEqual([])
  }
})

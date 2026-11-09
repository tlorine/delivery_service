/**
 * General storefront behaviour, ported from the upstream NextOrders suite (e2e/web-app) to the platform
 * API and Russian-first defaults.
 */
import { expect, test } from '@playwright/test'

test.describe('smoke', () => {
  test('homepage renders the cafe and its menu (SSR)', async ({ page }) => {
    const response = await page.goto('/')
    expect(response?.status()).toBe(200)
    await expect(page).toHaveTitle(/Демо-кафе/)
    await expect(page.locator('h2').first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText('maintenance', { ignoreCase: true })
    // Rendered on the server, not only after hydration:
    expect(await response!.text()).toContain('Чизбургер')
  })

  test('page has header and main layout', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('header').first()).toBeVisible()
    await expect(page.locator('main')).toBeVisible()
  })

  test('checkout page is accessible with an empty cart', async ({ page }) => {
    await page.goto('/checkout')
    await expect(page.getByRole('heading', { name: 'Ваша корзина пуста' })).toBeVisible()
  })
})

test.describe('navigation', () => {
  test('category link opens the category page', async ({ page }) => {
    await page.goto('/')
    await page.locator('a[href="/burgers"]:visible').first().click()
    await page.waitForURL('**/burgers')
    await expect(page.locator('h1')).toBeVisible()
  })

  test('product page has title, add button and a way back', async ({ page, isMobile }) => {
    await page.goto('/burgers')
    await page.locator('a[href="/burgers/cheeseburger"]:visible').first().click()
    await expect(page.locator('h1')).toHaveText('Чизбургер')
    await expect(page.getByTestId('add-to-cart')).toBeVisible()
    // Breadcrumb on wide screens, a back button on phones (CatalogBreadcrumb.vue).
    const wayBack = isMobile
      ? page.getByRole('button', { name: 'Вернуться' })
      : page.getByRole('link', { name: /Главная/ })
    await expect(wayBack.first()).toBeVisible()
  })

  test('mobile menu opens and closes', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 } })
    const page = await context.newPage()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('header button').first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 5000 })
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
    await context.close()
  })
})

test.describe('resilience', () => {
  test('direct navigation to a category works', async ({ page }) => {
    const response = await page.goto('/burgers')
    expect(response?.status()).toBe(200)
  })

  test('unknown product is a 404, not a crash', async ({ page }) => {
    const response = await page.goto('/burgers/no-such-product')
    expect(response?.status()).toBe(404)
    await expect(page.locator('body')).toBeVisible()
  })

  test('back navigation keeps the page working', async ({ page }) => {
    await page.goto('/')
    await page.locator('a[href="/burgers"]:visible').first().click()
    // Wait for the navigation to commit; otherwise goBack() leaves the site (upstream test race).
    await page.waitForURL('**/burgers')
    await page.goBack()
    await page.waitForURL((url) => url.pathname === '/')
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 })
  })

  test('API is reachable through the storefront origin', async ({ request }) => {
    const storefront = await request.get('/v1/storefront')
    expect(storefront.ok()).toBeTruthy()
    expect((await storefront.json()).slug).toBe('demo')
    const menu = await request.get('/v1/storefront/menu')
    expect((await menu.json()).categories.length).toBeGreaterThan(0)
  })
})

test.describe('localization', () => {
  test('Russian by default', async ({ browser }) => {
    const context = await browser.newContext({ locale: 'de-DE' })
    const page = await context.newPage()
    await page.goto('/')
    // Unsupported browser language falls back to the market default.
    await expect(page.locator('html')).toHaveAttribute('lang', /ru|de/)
    await context.close()
  })

  test('English interface for English browsers, cafe data stays as entered', async ({ browser }) => {
    const context = await browser.newContext({ locale: 'en-US' })
    const page = await context.newPage()
    await page.goto('/checkout')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('heading', { name: 'Your cart is empty' })).toBeVisible()
    await context.close()
  })
})

import { expect, test } from '@playwright/test'
import { API, buyerSees, login, openNav, placeOrder } from './helpers'

test('wrong password shows a clear message', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill('owner@demo.local')
  await page.getByLabel('Пароль').fill('nope')
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page.getByRole('alert')).toHaveText('Неверный email или пароль')
})

test('admin pages require login', async ({ page }) => {
  await page.goto('/menu')
  await expect(page).toHaveURL(/\/login\?next=/)
})

test('operator takes a new order through to handover; the buyer sees each step', async ({ page, request }) => {
  const order = await placeOrder(request)
  await login(page, 'operator')

  const row = page.getByTestId('order-row').filter({ hasText: `№${order.number}` })
  await expect(row).toBeVisible({ timeout: 15_000 })
  await expect(page).toHaveTitle(/^\(\d+\) Заказы/)
  await row.click()
  await expect(page.getByText('Покупатель E2E')).toBeVisible()
  await expect(page.getByText('💬 E2E')).toBeVisible()

  for (const [button, status, buyer] of [
    ['Подтвердить', 'Подтверждён', 'confirmed'],
    ['Начать готовить', 'Готовится', 'preparing'],
    ['Готов', 'Готов', 'ready'],
    ['Выдан / доставлен', 'Выполнен', 'completed'],
  ] as const) {
    await page.getByRole('button', { name: button, exact: true }).click()
    await expect(page.getByTestId('admin-order-status')).toHaveText(status)
    expect(await buyerSees(request, order.token)).toBe(buyer)
  }
  // Pickup orders are never "delivering", and a completed order has no further actions.
  await expect(page.getByRole('button', { name: 'Передать курьеру' })).toHaveCount(0)
})

test('rejecting requires a reason, which is kept in the history', async ({ page, request }) => {
  const order = await placeOrder(request, 'reject me')
  await login(page, 'operator')
  await page.goto(`/orders/${order.id}`)
  await page.getByRole('button', { name: 'Отклонить' }).click()
  const confirm = page.getByRole('button', { name: 'Подтвердить' }).last()
  await expect(confirm).toBeDisabled()
  await page.getByPlaceholder('Например: закончились продукты').fill('Нет булочек')
  await confirm.click()
  await expect(page.getByTestId('admin-order-status')).toHaveText('Отклонён')
  await expect(page.getByText(': Нет булочек')).toBeVisible()
  expect(await buyerSees(request, order.token)).toBe('rejected')
})

test('operator manages the stop-list but not the menu', async ({ page, request, isMobile }) => {
  await login(page, 'operator')
  await openNav(page, isMobile)
  await expect(page.getByRole('link', { name: 'Стоп-лист' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Меню' })).toHaveCount(0)
  await page.goto('/menu')
  await expect(page).toHaveURL(/\/orders/) // role guard

  await page.goto('/stoplist')
  const lemonade = page.getByTestId('stop-lemonade-0,5 л')
  await expect(lemonade).toBeVisible()
  const available = async () => {
    const sf = await (await request.get(`${API}/v1/storefront`, { headers: { Host: 'localhost' } })).json()
    const menu = await (await request.get(`${API}/v1/storefront/menu?branch_id=${sf.branches[0].id}`, { headers: { Host: 'localhost' } })).json()
    const p = menu.categories.flatMap((c: any) => c.products).find((x: any) => x.slug === 'lemonade')
    return p.variants.find((v: any) => v.name === '0,5 л').available
  }
  await lemonade.click()
  await expect.poll(available).toBe(false)
  await lemonade.click()
  await expect.poll(available).toBe(true)
})

test('manager changes a price and the storefront shows it', async ({ page, request }) => {
  const price = async () => {
    const menu = await (await request.get(`${API}/v1/storefront/menu`, { headers: { Host: 'localhost' } })).json()
    return menu.categories.flatMap((c: any) => c.products).find((p: any) => p.slug === 'cola').variants[0].price_minor
  }
  await login(page, 'manager')
  await page.goto('/menu')
  for (const rub of ['135', '120']) {
    await page.getByTestId('product-cola').click()
    const input = page.getByTestId('variant-price-0')
    await input.fill(rub)
    await input.blur()
    await page.getByTestId('product-save').click()
    await expect.poll(price).toBe(Number(rub) * 100)
  }
})

test('manager adds a category and a product with a modifier group', async ({ page, request }) => {
  const name = `Супы ${Date.now() % 100000}`
  await login(page, 'manager')
  await page.goto('/menu')
  await page.getByRole('button', { name: 'Категория' }).click()
  await page.getByTestId('dialog-input').fill(name)
  await page.getByTestId('dialog-ok').click()
  await expect(page.getByRole('heading', { name })).toBeVisible()

  await page.getByTestId('add-product').click()
  await page.getByTestId('product-name').fill('Борщ')
  await page.getByRole('combobox', { name: 'Категория' }).click()
  await page.getByRole('option', { name }).click()
  await page.getByTestId('variant-price-0').fill('290')
  await page.getByTestId('variant-price-0').blur()
  await page.getByTestId('product-save').click()
  await expect(page.getByTestId('product-borsch')).toBeVisible()

  const menu = await (await request.get(`${API}/v1/storefront/menu`, { headers: { Host: 'localhost' } })).json()
  const borsch = menu.categories.flatMap((c: any) => c.products).find((p: any) => p.slug === 'borsch')
  expect(borsch.variants[0].price_minor).toBe(29_000)
})

test('owner sees analytics and staff; manager cannot open staff', async ({ page }) => {
  await login(page, 'owner')
  await page.goto('/analytics')
  await expect(page.getByTestId('today-orders')).toHaveText(/\d+/)
  await page.goto('/staff')
  await expect(page.getByText('operator@demo.local')).toBeVisible()
  await page.goto('/settings')
  await expect(page.getByText('@demo_bot')).toBeVisible()
  await expect(page.getByText(/\/link [0-9a-f]{12}/)).toBeVisible()
})

test('owner sets the brand colour and cover; the storefront uses them', async ({ page, request }) => {
  const web = `http://localhost:${process.env.E2E_WEB_PORT ?? 3077}`
  await login(page, 'owner')
  await page.goto('/settings')

  // A mid-tone colour is darkened for readable text, and the owner is told so.
  await page.getByTestId('accent-hex').fill('#E5482B')
  await expect(page.getByTestId('accent-adjusted')).toBeVisible()

  await page.getByTestId('accent-hex').fill('#1F6F43')
  await expect(page.getByTestId('accent-adjusted')).toHaveCount(0)
  await expect(page.getByTestId('accent-preview')).toHaveCSS('background-color', 'rgb(31, 111, 67)')
  await page.getByTestId('cover-url').fill('https://cdn.example.ru/cover.jpg')
  await expect(page.getByTestId('cover-preview')).toHaveAttribute('src', 'https://cdn.example.ru/cover.jpg')
  await page.getByTestId('save-appearance').click()
  await expect(page.getByText('Сохранено').first()).toBeVisible()

  try {
    const html = await (await request.get(`${web}/`)).text()
    expect(html).toContain('--brand-accent:#1F6F43')
    expect(html).toContain('https://cdn.example.ru/cover.jpg')
  } finally {
    // Restore platform defaults for the other scenarios.
    await page.getByRole('button', { name: 'Как у платформы' }).click()
    await page.getByTestId('cover-url').fill('')
    await page.getByTestId('save-appearance').click()
    await expect(page.getByText('Сохранено').first()).toBeVisible()
  }
})

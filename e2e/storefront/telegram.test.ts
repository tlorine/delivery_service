/**
 * Telegram Mini App: the storefront inside Telegram's WebView. Telegram.WebApp is replaced by a recording
 * mock whose initData is signed with the demo bot token, so the server performs the real verification.
 */
import type { Page } from '@playwright/test'
import { createHmac } from 'node:crypto'
import process from 'node:process'
import { expect, test } from '@playwright/test'

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8078}`
const BOT_TOKEN = process.env.E2E_BOT_TOKEN ?? '123456:E2E-TOKEN'

function signedInitData(userId: number, firstName: string): string {
  const fields: Record<string, string> = {
    auth_date: String(Math.floor(Date.now() / 1000)),
    query_id: 'AAE2E',
    user: JSON.stringify({ id: userId, first_name: firstName, language_code: 'ru' }),
  }
  const check = Object.keys(fields).sort().map((k) => `${k}=${fields[k]}`).join('\n')
  const secret = createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest()
  const hash = createHmac('sha256', secret).update(check).digest('hex')
  return new URLSearchParams({ ...fields, hash }).toString()
}

async function openInTelegram(page: Page, initData: string) {
  await page.addInitScript((data) => {
    const rec = { calls: [] as string[], main: null as null | (() => void), params: {} as Record<string, unknown> }
    ;(window as any).__tg = rec
    const push = (c: string) => rec.calls.push(c)
    ;(window as any).Telegram = {
      WebApp: {
        initData: data,
        initDataUnsafe: { user: { first_name: 'Анна' } },
        colorScheme: 'light',
        themeParams: { bg_color: '#ffffff' },
        viewportStableHeight: 700,
        ready: () => push('ready'),
        expand: () => push('expand'),
        close: () => push('close'),
        onEvent: () => {},
        setHeaderColor: () => {},
        setBackgroundColor: () => {},
        enableClosingConfirmation: () => push('closing:on'),
        disableClosingConfirmation: () => push('closing:off'),
        BackButton: { show: () => push('back:show'), hide: () => push('back:hide'), onClick: () => {}, offClick: () => {} },
        MainButton: {
          setParams: (p: Record<string, unknown>) => Object.assign(rec.params, p),
          onClick: (cb: () => void) => {
            rec.main = cb
          },
          // Like Telegram: removes only the given handler.
          offClick: (cb: () => void) => {
            if (rec.main === cb) {
              rec.main = null
            }
          },
          showProgress: () => {},
          hideProgress: () => {},
        },
        HapticFeedback: { impactOccurred: (s: string) => push(`impact:${s}`), notificationOccurred: (t: string) => push(`notify:${t}`) },
      },
    }
  }, initData)
}

const calls = (page: Page) => page.evaluate(() => (window as any).__tg.calls as string[])

test('order placed from the Mini App is linked to the Telegram user', async ({ page, request }) => {
  await openInTelegram(page, signedInitData(9001, 'Анна'))

  await page.goto('/burgers/cheeseburger')
  await expect.poll(() => calls(page)).toEqual(expect.arrayContaining(['ready', 'expand', 'back:show']))

  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items') && r.request().method() === 'POST')
  await page.getByTestId('add-to-cart').click()
  expect((await added).status()).toBe(200)
  await expect.poll(() => calls(page)).toContain('impact:light')

  await page.goto('/checkout')
  // Name prefilled from Telegram (display data only); the in-page submit button gives way to MainButton.
  await expect(page.getByLabel('Ваше имя')).toHaveValue('Анна')
  await expect(page.getByRole('button', { name: 'Создать заказ' })).toHaveCount(0)
  await expect.poll(() => calls(page)).toContain('closing:on')

  await page.getByLabel('Ваш телефон').fill('9181234567')
  await page.getByRole('tab', { name: 'Самовывоз' }).click()
  await page.getByRole('combobox', { name: /Улица и дом/ }).click()
  await page.getByRole('option', { name: /Курортный/ }).click()
  await page.getByRole('combobox', { name: 'Метод оплаты' }).click()
  await page.getByRole('option', { name: 'Наличными' }).click()
  await page.getByTestId('pd-consent').click()

  await expect.poll(() => page.evaluate(() => (window as any).__tg.params.is_active)).toBe(true)
  await page.evaluate(() => (window as any).__tg.main())

  await expect(page).toHaveURL(/\/finish\?id=/)
  await expect(page.getByTestId('order-status')).toHaveText('Ожидает подтверждения')
  await page.getByRole('button', { name: 'Закрыть' }).click()
  await expect.poll(() => calls(page)).toEqual(expect.arrayContaining(['notify:success', 'close']))

  // Staff see where the order came from.
  const orderId = new URL(page.url()).searchParams.get('id')!
  const login = await request.post(`${API}/v1/admin/auth/login`, { data: { email: 'owner@demo.local', password: 'e2e-owner-pass' } })
  const { token } = await login.json()
  const order = await (await request.get(`${API}/v1/admin/orders/${orderId}`, { headers: { Authorization: `Bearer ${token}` } })).json()
  expect(order.channel).toBe('telegram')
})

test('forged initData does not let an order through as someone else', async ({ page }) => {
  const forged = signedInitData(9002, 'Анна').replace('9002', '9003') // signature no longer matches
  await openInTelegram(page, forged)
  await page.goto('/burgers/cheeseburger')
  const added = page.waitForResponse((r) => r.url().endsWith('/v1/cart/items'))
  await page.getByTestId('add-to-cart').click()
  await added
  await page.goto('/checkout')
  await page.getByLabel('Ваш телефон').fill('9181234567')
  await page.getByRole('tab', { name: 'Самовывоз' }).click()
  await page.getByRole('combobox', { name: /Улица и дом/ }).click()
  await page.getByRole('option', { name: /Курортный/ }).click()
  await page.getByRole('combobox', { name: 'Метод оплаты' }).click()
  await page.getByRole('option', { name: 'Наличными' }).click()
  await page.getByTestId('pd-consent').click()
  const placed = page.waitForResponse((r) => r.url().endsWith('/v1/orders'))
  await page.evaluate(() => (window as any).__tg.main())
  expect((await placed).status()).toBe(401)
  await expect.poll(() => calls(page)).toContain('notify:error')
  await expect(page).toHaveURL(/\/checkout/)
})

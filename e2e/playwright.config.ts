import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

/**
 * Storefront and admin against the real FastAPI backend and PostgreSQL, on production builds
 * (not `nuxt dev`: on-demand compilation made the upstream suite flaky, audit P13).
 * Build first: `pnpm --filter @nextorders/web-app build && pnpm --filter @delivery/admin build` and the mobile SPA:
 * `NUXT_PUBLIC_API_BASE_URL=http://api.localhost:8078 pnpm --filter @nextorders/web-app generate:mobile`.
 */
const CI = !!process.env.CI
const API_PORT = Number(process.env.E2E_API_PORT ?? 8078)
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3077)
const APP_PORT = Number(process.env.E2E_APP_PORT ?? 3080)
export const ADMIN_PORT = Number(process.env.E2E_ADMIN_PORT ?? 3079)

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: 1,
  reporter: CI ? 'github' : 'list',
  use: {
    trace: 'retain-on-failure',
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
  },
  projects: [
    { name: 'storefront-mobile', testDir: './storefront', use: { ...devices['Pixel 7'], baseURL: `http://localhost:${WEB_PORT}` } },
    { name: 'storefront-desktop', testDir: './storefront', use: { ...devices['Desktop Chrome'], baseURL: `http://localhost:${WEB_PORT}` } },
    { name: 'admin-desktop', testDir: './admin', use: { ...devices['Desktop Chrome'], baseURL: `http://localhost:${ADMIN_PORT}` } },
    { name: 'admin-mobile', testDir: './admin', use: { ...devices['Pixel 7'], baseURL: `http://localhost:${ADMIN_PORT}` } },
    // The SPA build loaded by the Capacitor shell (apps/mobile), on a phone viewport.
    { name: 'mobile-app', testDir: './mobile', use: { ...devices['Pixel 7'], baseURL: `http://localhost:${APP_PORT}` } },
  ],
  webServer: [
    {
      command: `sh e2e/start-backend.sh`,
      url: `http://localhost:${API_PORT}/health/ready`,
      env: { E2E_API_PORT: String(API_PORT) },
      cwd: '..',
      timeout: 120_000,
      reuseExistingServer: !CI,
    },
    {
      command: `node apps/web-app/.output/server/index.mjs`,
      url: `http://localhost:${WEB_PORT}`,
      env: { PORT: String(WEB_PORT), NUXT_API_INTERNAL_URL: `http://localhost:${API_PORT}` },
      cwd: '..',
      timeout: 60_000,
      reuseExistingServer: !CI,
    },
    {
      command: `node apps/admin/.output/server/index.mjs`,
      url: `http://localhost:${ADMIN_PORT}/login`,
      env: { PORT: String(ADMIN_PORT), NUXT_API_INTERNAL_URL: `http://localhost:${API_PORT}` },
      cwd: '..',
      timeout: 60_000,
      reuseExistingServer: !CI,
    },
    {
      command: `node e2e/serve-spa.mjs apps/web-app/.output-mobile/public ${APP_PORT}`,
      url: `http://localhost:${APP_PORT}/`,
      cwd: '..',
      timeout: 30_000,
      reuseExistingServer: !CI,
    },
  ],
})

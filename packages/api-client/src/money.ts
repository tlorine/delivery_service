/**
 * Display-only formatting of integer minor units (ADR-0008). Never send the result back to the server
 * and never do arithmetic on it.
 */
export function formatMoney(minor: number, currency = 'RUB', locale = 'ru-RU'): string {
  if (!Number.isInteger(minor)) {
    throw new TypeError(`amount must be an integer number of minor units, got ${minor}`)
  }
  const fractionDigits = minor % 100 === 0 ? 0 : 2
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(minor / 100)
}

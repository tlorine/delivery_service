import type { ApiError } from '@delivery/api-client'

const KNOWN = new Set([
  'price_changed', 'outside_delivery_zone', 'below_min_order', 'branch_closed', 'invalid_requested_time',
  'item_unavailable', 'invalid_modifiers', 'invalid_phone', 'cart_already_checked_out', 'cart_not_found',
  'payment_method_unavailable', 'invalid_change', 'rate_limited', 'network_error',
])

/** Localized text for a stable API error code (docs/architecture/api-contract.md). */
export function useApiErrorMessage() {
  const { dict } = useDictionary()

  function messageFor(code: string | undefined | null): string {
    const key = code && KNOWN.has(code) ? code.replaceAll('_', '-') : 'generic'
    return dict(`web-app.errors.${key}` as DictionaryKey)
  }

  function messageOf(error: ApiError | null | undefined): string | undefined {
    return error ? messageFor(error.code) : undefined
  }

  return { messageFor, messageOf }
}

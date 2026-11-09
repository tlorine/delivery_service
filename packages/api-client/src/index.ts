import type { components } from './schema'

export { brandTokens, contrastRatio, DEFAULT_ACCENT, normalizeHex, textOn } from './brand'
export { createApiClient } from './client'
export type { ApiClient, ApiClientOptions, ClientChannel, RequestOptions } from './client'
export { ApiError } from './errors'
export type { Problem } from './errors'
export { formatMoney } from './money'

type S = components['schemas']
export type Storefront = S['StorefrontOut']
export type Branch = S['BranchOut']
export type Menu = S['MenuOut']
export type MenuCategory = S['CategoryOut']
export type MenuProduct = S['ProductOut']
export type MenuVariant = S['VariantOut']
export type ModifierGroup = S['ModifierGroupOut']
export type Cart = S['CartOut']
export type CartLine = S['CartLineOut']
export type Quote = S['QuoteOut']
export type OrderInput = S['OrderIn']
export type Order = S['OrderOut']
export type OrderCreated = S['OrderCreatedOut']
export type AdminOrder = S['AdminOrderOut']
export type OrderStatus = S['OrderStatus']
export type { components, paths } from './schema'

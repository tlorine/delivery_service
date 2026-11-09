import type { ApiError, Order as ApiOrder, Cart, OrderCreated, Quote } from '@delivery/api-client'
import type { Order, OrderItemChange } from '@nextorders/food-schema'

const NON_DIGIT_RE = /\D/g
const CONTACTS_KEY = 'checkout-contacts'
const ORDERS_KEY = 'order-tokens'

type Fulfillment = 'delivery' | 'pickup'
type PaymentMethodId = 'cash' | 'card_on_delivery' | 'online'

interface SavedContacts {
  name?: string
  phone?: string
  address?: Order['address']
  note?: string
}

function readLocal<T>(key: string): T | undefined {
  if (!import.meta.client) {
    return
  }
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : undefined
  } catch {
    return undefined
  }
}

function writeLocal(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private mode or quota: the data is a convenience only.
  }
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/**
 * Cart and checkout. The cart lives on the server (ADR-0004); prices, delivery fee and all checks come
 * from the API. Contact details stay on the device until the order is placed (152-FZ: no personal
 * data on the server before consent).
 */
export const useOrderStore = defineStore('order', () => {
  const cartToken = useCartToken()
  const telegram = useTelegram()
  const channelStore = useChannelStore()
  const optionsStore = useOptionsStore()

  const cart = ref<Cart | null>(null)
  const quote = ref<Quote | null>(null)
  const lastError = ref<ApiError | null>(null)

  // Food-schema shaped fields consumed by the existing components.
  const id = computed(() => cart.value?.id)
  const status = ref<Order['status']>()
  const items = computed<CartLineView[]>(() => cart.value ? cartLinesView(cart.value) : [])
  const totalPrice = computed(() => minorToDisplay(cart.value?.subtotal_minor ?? 0))
  const deliveryFee = computed(() => minorToDisplay(quote.value?.delivery_fee_minor ?? 0))
  const grandTotal = computed(() => minorToDisplay(quote.value?.total_minor ?? cart.value?.subtotal_minor ?? 0))

  const name = ref<string>()
  const phone = ref<string>()
  const deliveryMethod = ref<Order['deliveryMethod']>()
  const paymentMethodId = ref<string>()
  const changeFrom = ref<number>() // rubles typed by the buyer
  const readyBy = ref<string>()
  const readyType = ref<Order['readyType']>()
  const address = ref<Order['address']>()
  const note = ref<string>()
  const personalDataConsent = ref(false)

  const updatedAt = ref<number>()
  const isValidPhone = ref(false)
  const deliveryZoneRequired = ref(false)
  const deliveryZoneValid = ref(false)
  const isLoading = ref<boolean>(true)
  const isSaved = ref<boolean>(true)

  let idempotencyKey: string | null = null

  const fulfillment = computed<Fulfillment | undefined>(() =>
    deliveryMethod.value === 'deliveryByCourier' ? 'delivery' : deliveryMethod.value === 'selfPickup' ? 'pickup' : undefined)

  const problems = computed(() => quote.value?.problems.filter((p) =>
    // Not chosen yet is not an error to show.
    !(p.code === 'payment_method_unavailable' && !paymentMethodId.value)) ?? [])
  const hasProblem = (code: string) => problems.value.some((p) => p.code === code)

  const isEmpty = computed<boolean>(() => items.value.length === 0)
  const isValidTotalPrice = computed<boolean>(() => !hasProblem('below_min_order'))
  const isValidDeliveryAddress = computed<boolean>(() => fulfillment.value === 'delivery'
    ? address.value?.type === 'deliveryAddress' && !!address.value.street && address.value.lat != null
    : true)
  const isValidPickupAddress = computed<boolean>(() => fulfillment.value === 'pickup'
    ? address.value?.type === 'warehouseAddress' && !!address.value.id
    : true)
  const isValidAddress = computed<boolean>(() => isValidDeliveryAddress.value && isValidPickupAddress.value
    && (fulfillment.value !== 'delivery' || deliveryZoneValid.value))
  const isValidCheckoutData = computed<boolean>(() => !!name.value
    && !!phone.value
    && isValidPhone.value
    && !!fulfillment.value
    && isValidAddress.value
    && !!paymentMethodId.value
    && personalDataConsent.value)
  const isReadyToCheckout = computed<boolean>(() => isValidCheckoutData.value
    && isValidTotalPrice.value
    && !cart.value?.has_problems
    && problems.value.length === 0)

  // ---- persistence on the device -------------------------------------------------------------

  function restoreContacts() {
    applyDefaults()
    const saved = readLocal<SavedContacts>(CONTACTS_KEY)
    if (!saved) {
      name.value ||= telegram.firstName() // display-only prefill from Telegram
      return
    }
    name.value = saved.name
    address.value = saved.address
    note.value = saved.note
    if (saved.phone) {
      validateAndSetPhone(formatPhone(saved.phone))
    }
  }

  function saveContacts() {
    writeLocal(CONTACTS_KEY, { name: name.value, phone: phone.value, address: address.value } satisfies SavedContacts)
  }

  // Components set isSaved=false after edits: refresh the quote (debounced) instead of a server draft.
  watch(isSaved, useDebounceFn(async () => {
    if (!isSaved.value) {
      saveContacts()
      await refreshQuote()
      isSaved.value = true
    }
  }, 400))

  // ---- phone ---------------------------------------------------------------------------------

  function formatPhone(phoneAsString: string): string {
    if (!phoneAsString) {
      return ''
    }
    getPhoneNumberFormatter(optionsStore.countryCode).input(phoneAsString)
    return formatPhoneNumber(phoneAsString, optionsStore.countryCode)
  }

  function validateAndSetPhone(formattedPhone: string): void {
    if (!formattedPhone || formattedPhone?.length > 17) {
      isValidPhone.value = false
      return
    }
    getPhoneNumberFormatter(optionsStore.countryCode).input(formattedPhone)
    isValidPhone.value = checkPhoneNumberValidity(formattedPhone, optionsStore.countryCode)
    phone.value = isValidPhone.value ? formattedPhone.replace(NON_DIGIT_RE, '') : undefined
  }

  // ---- API -----------------------------------------------------------------------------------

  const api = () => useNuxtApp().$api

  function branchForMenu(): string | undefined {
    return fulfillment.value === 'pickup' && address.value?.type === 'warehouseAddress'
      ? address.value.id || undefined
      : quote.value?.branch_id ?? undefined
  }

  async function update() {
    if (!cartToken.value) {
      clear()
      return
    }
    try {
      cart.value = await api().get('/v1/cart', { query: { branch_id: branchForMenu() } })
      updatedAt.value = Date.now()
    } catch (e) {
      if ((e as ApiError).status === 404) {
        clear() // expired or already checked out
      }
    } finally {
      isLoading.value = false
    }
  }

  function clear() {
    cart.value = null
    quote.value = null
    cartToken.value = null
    isLoading.value = false
  }

  async function ensureCart(): Promise<void> {
    if (cartToken.value && !cart.value) {
      // After a reload the token is known before the cart is loaded: never replace a live cart.
      await update()
    }
    if (cartToken.value && cart.value) {
      return
    }
    const created = await api().post('/v1/carts')
    cartToken.value = created.cart_token
    cart.value = created.cart
  }

  async function add(variantId: string, modifiers: { modifierId: string, quantity: number }[] = [], quantity = 1): Promise<boolean> {
    isLoading.value = true
    lastError.value = null
    try {
      await ensureCart()
      const body = {
        variant_id: variantId,
        quantity,
        modifiers: modifiers.map((m) => ({ modifier_id: m.modifierId, quantity: m.quantity })),
      }
      try {
        cart.value = await api().post('/v1/cart/items', { body })
      } catch (e) {
        if ((e as ApiError).code !== 'cart_not_found') {
          throw e
        }
        // The stored cart expired or was checked out elsewhere: start a new one once.
        cart.value = null
        cartToken.value = null
        await ensureCart()
        cart.value = await api().post('/v1/cart/items', { body })
      }
      await refreshQuote()
      return true
    } catch (e) {
      lastError.value = e as ApiError
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function changeItem(data: Pick<OrderItemChange, 'itemId' | 'method'>) {
    const line = items.value.find((l) => l.id === data.itemId)
    if (!line) {
      return
    }
    const quantity = line.quantity + (data.method === 'increment' ? 1 : -1)
    try {
      cart.value = await api().patch('/v1/cart/items/{item_id}', {
        path: { item_id: data.itemId },
        body: { quantity },
      })
      await refreshQuote()
    } catch (e) {
      lastError.value = e as ApiError
    }
  }

  /** Local checkout fields; kept for component compatibility (no server draft any more). */
  async function change(order: Partial<Order>) {
    if (order.deliveryMethod !== undefined) {
      deliveryMethod.value = order.deliveryMethod
    }
    if (order.paymentMethodId !== undefined) {
      paymentMethodId.value = order.paymentMethodId || undefined
    }
    isSaved.value = false
  }

  function checkoutBody() {
    const delivery = fulfillment.value === 'delivery'
    const a = address.value
    const method = (paymentMethodId.value || 'cash') as PaymentMethodId
    return {
      fulfillment: fulfillment.value ?? 'pickup',
      branch_id: !delivery && a?.type === 'warehouseAddress' && a.id ? a.id : null,
      address: delivery && a?.type === 'deliveryAddress' && a.lat != null && a.lon != null
        ? {
            street: a.street,
            flat: a.flat || null,
            entrance: a.entrance || null,
            floor: a.floor || null,
            intercom: a.intercom || null,
            comment: a.addressNote || null,
            lat: a.lat,
            lon: a.lon,
          }
        : null,
      payment_method: method,
      // The one place where a typed amount becomes minor units: integer kopecks.
      change_from_minor: method === 'cash' && changeFrom.value ? Math.round(changeFrom.value * 100) : null,
      requested_at: readyType.value === 'scheduled' && readyBy.value ? readyBy.value : null,
      comment: note.value || null,
    }
  }

  async function refreshQuote() {
    if (!cartToken.value || !fulfillment.value || isEmpty.value) {
      quote.value = null
      return
    }
    const body = checkoutBody()
    if (body.fulfillment === 'delivery' && !body.address) {
      quote.value = null
      deliveryZoneValid.value = false
      return
    }
    try {
      quote.value = await api().post('/v1/checkout/quote', { body })
      deliveryZoneValid.value = !quote.value.problems.some((p) => p.code === 'outside_delivery_zone')
      deliveryZoneRequired.value = body.fulfillment === 'delivery'
    } catch (e) {
      lastError.value = e as ApiError
    }
  }

  async function complete(): Promise<OrderCreated | undefined> {
    lastError.value = null
    idempotencyKey ??= newIdempotencyKey()
    try {
      const initData = telegram.initData()
      const created = await api().post('/v1/orders', {
        // Inside Telegram the signed initData links the order to the buyer (verified by the server).
        headers: { 'Idempotency-Key': idempotencyKey, ...(initData ? { 'X-Telegram-Init-Data': initData } : {}) },
        body: {
          ...checkoutBody(),
          customer: { name: name.value ?? '', phone: phone.value ?? '' },
          personal_data_consent: true,
          expected_total_minor: quote.value?.total_minor ?? null,
        },
      })
      idempotencyKey = null
      rememberOrder(created.order.id, created.order_token)
      saveContacts()
      clear()
      note.value = undefined
      return created
    } catch (e) {
      const error = e as ApiError
      lastError.value = error
      // Same key only for blind retries after a network failure; a refused request changes the body.
      if (error.status !== 0) {
        idempotencyKey = null
      }
      if (error.code === 'price_changed') {
        quote.value = (error.problem.extra?.quote as Quote | undefined) ?? quote.value
        await update()
      }
    }
  }

  function rememberOrder(orderId: string, token: string) {
    const tokens = readLocal<Record<string, string>>(ORDERS_KEY) ?? {}
    tokens[orderId] = token
    writeLocal(ORDERS_KEY, tokens)
  }

  function orderToken(orderId: string): string | undefined {
    return readLocal<Record<string, string>>(ORDERS_KEY)?.[orderId]
  }

  async function get(orderId: string): Promise<ApiOrder | undefined> {
    const token = orderToken(orderId)
    if (!token) {
      return
    }
    try {
      return await api().get('/v1/orders/{order_token}', { path: { order_token: token } })
    } catch {
      return undefined
    }
  }

  async function cancel(orderId: string): Promise<ApiOrder | undefined> {
    const token = orderToken(orderId)
    if (!token) {
      return
    }
    try {
      return await api().post('/v1/orders/{order_token}/cancel', { path: { order_token: token } })
    } catch (e) {
      lastError.value = e as ApiError
    }
  }

  /** Default fulfillment. Called on the client after hydration (SSR state would overwrite a watcher's value). */
  function applyDefaults() {
    if (!deliveryMethod.value && channelStore.isActive) {
      deliveryMethod.value = channelStore.deliveryByCourier?.isAvailable ? 'deliveryByCourier' : 'selfPickup'
    }
  }

  watch(() => channelStore.isActive, applyDefaults)

  // In Telegram, ask before closing the Mini App with a filled cart.
  watch(isEmpty, (empty) => telegram.setClosingConfirmation(!empty))

  return {
    id,
    name,
    phone,
    status,
    totalPrice,
    deliveryFee,
    grandTotal,
    deliveryMethod,
    fulfillment,
    paymentMethodId,
    changeFrom,
    readyBy,
    readyType,
    address,
    note,
    items,
    quote,
    problems,
    lastError,
    personalDataConsent,

    updatedAt,

    isEmpty,
    isValidPhone,
    isValidTotalPrice,
    isValidPickupAddress,
    isValidCheckoutData,
    isReadyToCheckout,
    isLoading,
    isSaved,
    deliveryZoneRequired,
    deliveryZoneValid,

    update,
    restoreContacts,
    refreshQuote,
    add,
    change,
    changeItem,
    complete,
    get,
    cancel,
    formatPhone,
    validateAndSetPhone,
  }
})

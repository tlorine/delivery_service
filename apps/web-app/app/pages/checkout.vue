<template>
  <div v-if="orderStore.isLoading && orderStore.isEmpty" class="flex min-h-[50dvh] items-center justify-center">
    <UIcon name="lucide:loader-circle" class="size-10 animate-spin text-dimmed" />
  </div>

  <template v-else-if="!orderStore.isEmpty && !channelStore.isOnMaintenance">
    <h1 class="mb-4 text-[28px]/8 md:text-[34px]/10 font-bold text-highlighted">
      {{ $dict('web-app.checkout.title') }}
    </h1>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start lg:gap-8">
      <!-- Steps in the order decisions are made -->
      <div class="flex min-w-0 flex-col gap-4">
        <CheckoutBlock>
          <CartDeliveryMethodSwitch />
          <FormOrderDeliveryAddress v-if="orderStore.deliveryMethod === 'deliveryByCourier'" />
          <FormOrderWarehouseAddress v-if="orderStore.deliveryMethod === 'selfPickup'" />
        </CheckoutBlock>
        <CheckoutBlock>
          <FormOrderTime />
        </CheckoutBlock>
        <CheckoutBlock>
          <FormOrderContacts />
        </CheckoutBlock>
        <CheckoutBlock>
          <FormOrderPayment />
        </CheckoutBlock>
      </div>

      <!-- Summary: what you order and what you pay -->
      <aside class="flex min-w-0 flex-col gap-4 lg:sticky lg:top-[calc(var(--header-h)+1.25rem)]">
        <CheckoutBlock>
          <FormOrderList />

          <dl class="flex flex-col gap-1.5 border-t border-default pt-3 text-[15px]">
            <div class="flex justify-between">
              <dt class="text-muted">
                {{ $dict('web-app.checkout.cost.products') }}
              </dt>
              <dd class="tabular">
                {{ optionsStore.formatCurrency(orderStore.totalPrice) }} {{ optionsStore.currencySign }}
              </dd>
            </div>
            <div v-if="orderStore.fulfillment === 'delivery'" class="flex justify-between">
              <dt class="text-muted">
                {{ $dict('web-app.checkout.cost.delivery') }}
              </dt>
              <dd class="tabular" data-testid="delivery-fee">
                <template v-if="orderStore.quote">
                  {{ orderStore.deliveryFee ? `${optionsStore.formatCurrency(orderStore.deliveryFee)} ${optionsStore.currencySign}` : $dict('web-app.checkout.free') }}
                </template>
                <template v-else>
                  <span class="text-muted">{{ $dict('web-app.checkout.by-address') }}</span>
                </template>
              </dd>
            </div>
            <div class="flex justify-between pt-1 text-[17px] font-bold">
              <dt>{{ $dict('web-app.checkout.grand-total') }}</dt>
              <dd class="tabular" data-testid="grand-total">
                {{ optionsStore.formatCurrency(orderStore.grandTotal) }} {{ optionsStore.currencySign }}
              </dd>
            </div>
          </dl>

          <div v-if="visibleProblems.length || !orderStore.isValidCheckoutData" class="flex flex-col gap-2">
            <CheckoutInfoMessage
              v-for="problem in visibleProblems"
              :key="problem"
              icon="alert"
              :message="problem"
            />
            <CheckoutInfoMessage
              v-if="!orderStore.isValidCheckoutData && !visibleProblems.length"
              icon="info"
              :message="$dict('web-app.checkout.warning-data')"
            />
          </div>

          <UCheckbox
            v-model="orderStore.personalDataConsent"
            :label="$dict('web-app.checkout.consent')"
            size="lg"
            data-testid="pd-consent"
          />
        </CheckoutBlock>

        <!-- Pinned on phones; in Telegram the native MainButton replaces it. -->
        <div
          v-if="!telegramMain.isActive.value"
          class="fixed inset-x-0 bottom-0 z-40 border-t border-default bg-default/95 px-4 pt-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] backdrop-blur lg:static lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
        >
          <button
            type="button"
            class="btn-accent mx-auto flex h-14 w-full max-w-xl items-center justify-between rounded-[16px] px-5 text-[16px] font-semibold transition active:scale-[.99]"
            :disabled="!orderStore.isReadyToCheckout || orderStore.isLoading"
            @click="createOrder()"
          >
            <span class="flex items-center gap-2">
              <UIcon
                v-if="orderStore.isLoading"
                name="lucide:loader-circle"
                class="size-5 animate-spin"
              />
              {{ $dict('web-app.checkout.create-order') }}
            </span>
            <span class="tabular">{{ optionsStore.formatCurrency(orderStore.grandTotal) }} {{ optionsStore.currencySign }}</span>
          </button>
        </div>
      </aside>
    </div>
    <div class="h-24 lg:hidden" />
  </template>

  <template v-else>
    <div class="py-16 text-center">
      <h1 class="mb-6 text-[26px] font-bold">
        {{ $dict('web-app.cart.empty-label') }}
      </h1>
      <UButton
        to="/"
        size="xl"
        color="neutral"
        variant="soft"
        :label="$dict('common.to-home')"
      />
    </div>
  </template>
</template>

<script setup lang="ts">
definePageMeta({
  layout: 'checkout',
})

const { dict } = useDictionary()

const channelStore = useChannelStore()
const orderStore = useOrderStore()
const optionsStore = useOptionsStore()

const { messageFor, messageOf } = useApiErrorMessage()
const toast = useToast()

// Server-side checks (zone, minimum, opening hours, stop-list) shown before the buyer presses the button.
const visibleProblems = computed(() => [...new Set(orderStore.problems.map((p) => messageFor(p.code)))])

// Inside Telegram the native MainButton replaces the in-page button.
const telegramMain = useTelegramMainButton({
  text: () => `${dict('web-app.checkout.create-order')} · ${optionsStore.formatCurrency(orderStore.grandTotal)} ${optionsStore.currencySign}`,
  enabled: () => orderStore.isReadyToCheckout && !orderStore.isLoading,
  loading: () => orderStore.isLoading,
  onClick: () => createOrder(),
})
const { notify } = useTelegram()

async function createOrder() {
  orderStore.isLoading = true
  try {
    const created = await orderStore.complete()
    if (created) {
      notify('success')
      await navigateTo(`/finish?id=${created.order.id}`)
      return
    }
    notify('error')
    toast.add({ title: messageOf(orderStore.lastError), color: 'error', icon: 'lucide:circle-alert', duration: 6000 })
  } finally {
    orderStore.isLoading = false
  }
}

useHead({
  title: `${dict('web-app.checkout.title')} | ${optionsStore.getLocaleValue(channelStore.title)}`,
})
</script>

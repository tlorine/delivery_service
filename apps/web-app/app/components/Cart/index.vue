<template>
  <div class="flex flex-col" data-testid="cart">
    <div class="flex items-center justify-between px-4 pt-2 pb-1">
      <h2 class="text-[22px] font-bold text-highlighted">
        {{ $dict('web-app.cart.title') }}
      </h2>
      <button
        type="button"
        class="inline-flex items-center gap-1 text-sm text-muted hover:text-toned"
        @click="modalDeliveryInfo.open()"
      >
        <UIcon name="lucide:info" class="size-4" />{{ $dict('web-app.cart.conditions') }}
      </button>
    </div>

    <CartEmpty v-if="orderStore.isEmpty" />

    <template v-else>
      <ul class="flex flex-col divide-y divide-default px-4 xl:max-h-[calc(100dvh-var(--header-h)-16rem)] xl:overflow-y-auto">
        <li
          v-for="item in orderStore.items"
          :key="item.id"
          class="py-3"
        >
          <CartLine :line="item" />
        </li>
      </ul>

      <div class="mx-4 mt-1 flex items-center justify-between border-t border-default pt-3 text-[15px]">
        <span class="text-muted">{{ $dict('web-app.checkout.cost.products') }}</span>
        <span class="tabular font-semibold">{{ optionsStore.formatCurrency(orderStore.totalPrice) }} {{ optionsStore.currencySign }}</span>
      </div>
      <p v-if="orderStore.fulfillment === 'delivery'" class="mx-4 mt-1 text-xs text-muted">
        {{ $dict('web-app.checkout.info-shipping-price') }}
      </p>

      <div class="p-4 pt-3">
        <NuxtLink
          to="/checkout"
          class="btn-accent flex h-14 w-full items-center justify-between rounded-[16px] px-5 text-[16px] font-semibold transition active:scale-[.99]"
          data-testid="to-checkout"
        >
          <span>{{ $dict('web-app.cart.to-checkout') }}</span>
          <span class="tabular">{{ optionsStore.formatCurrency(orderStore.totalPrice) }} {{ optionsStore.currencySign }}</span>
        </NuxtLink>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ModalDeliveryInfo } from '#components'

const overlay = useOverlay()
const modalDeliveryInfo = overlay.create(ModalDeliveryInfo)
const optionsStore = useOptionsStore()
const orderStore = useOrderStore()
</script>

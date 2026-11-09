<template>
  <!-- Phone/tablet: bottom cart bar. In Telegram the native MainButton plays this role. -->
  <div v-if="!orderStore.isEmpty && !telegram.isActive.value && !route.params.productSlug" class="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)] xl:hidden">
    <button
      type="button"
      class="btn-accent shadow-float pointer-events-auto mx-auto flex h-14 w-full max-w-xl items-center justify-between rounded-[16px] px-4 text-[16px] font-semibold active:scale-[.99]"
      data-testid="cart-bar"
      @click="isCartDrawerOpened = true"
    >
      <span class="flex items-center gap-2">
        <span class="tabular rounded-full bg-black/15 px-2 py-0.5 text-sm">{{ count }}</span>
        {{ $dict('web-app.cart.title') }}
      </span>
      <span class="tabular">{{ optionsStore.formatCurrency(orderStore.totalPrice) }} {{ optionsStore.currencySign }}</span>
    </button>
  </div>
  <UDrawer
    v-model:open="isCartDrawerOpened"
    direction="bottom"
    class="xl:hidden"
  >
    <template #content>
      <div class="max-h-[85dvh] overflow-y-auto py-2">
        <Cart />
      </div>
    </template>
  </UDrawer>
</template>

<script setup lang="ts">
const { isCartDrawerOpened } = useApp()
const route = useRoute()
const orderStore = useOrderStore()
const optionsStore = useOptionsStore()
const telegram = useTelegram()
const { dict } = useDictionary()
const count = computed(() => orderStore.items.reduce((n, l) => n + l.quantity, 0))

useTelegramMainButton({
  text: () => `${dict('web-app.cart.title')} · ${optionsStore.formatCurrency(orderStore.totalPrice)} ${optionsStore.currencySign}`,
  enabled: () => !orderStore.isEmpty,
  // The dish page has its own pinned "Add" bar; one MainButton owner per screen.
  visible: () => !orderStore.isEmpty && !route.params.productSlug,
  onClick: () => {
    isCartDrawerOpened.value = true
  },
})
</script>

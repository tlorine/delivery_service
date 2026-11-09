<template>
  <div
    class="flex h-10 shrink-0 items-center justify-between gap-1 rounded-[12px] bg-elevated px-1"
    :class="$attrs.class ? '' : 'w-[6.75rem]'"
    data-testid="line-counter"
  >
    <button
      type="button"
      class="grid size-8 place-items-center rounded-lg text-toned transition hover:bg-accented active:scale-95"
      :aria-label="line.quantity > 1 ? $dict('web-app.cart.decrease') : $dict('web-app.cart.remove')"
      @click="orderStore.changeItem({ itemId: line.id, method: 'decrement' })"
    >
      <UIcon :name="line.quantity > 1 ? 'lucide:minus' : 'lucide:trash-2'" class="size-4" />
    </button>
    <span class="tabular min-w-5 text-center text-[15px] font-semibold">{{ line.quantity }}</span>
    <button
      type="button"
      class="grid size-8 place-items-center rounded-lg text-toned transition hover:bg-accented active:scale-95"
      :aria-label="$dict('web-app.cart.increase')"
      @click="orderStore.changeItem({ itemId: line.id, method: 'increment' })"
    >
      <UIcon name="lucide:plus" class="size-4" />
    </button>
  </div>
</template>

<script setup lang="ts">
import type { OrderItem } from '@nextorders/food-schema'

defineProps<{ line: OrderItem }>()
const orderStore = useOrderStore()
</script>

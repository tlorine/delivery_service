<template>
  <div class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1.5">
    <NuxtLink :to="productUrl" class="flex min-w-0 gap-3">
      <div v-if="images.length" class="relative size-14 shrink-0 overflow-hidden rounded-[12px] bg-elevated">
        <ProductImage :images="images" size="xs" />
      </div>
      <div class="min-w-0">
        <p class="text-[15px]/5 font-medium text-highlighted">
          {{ line.productName || optionsStore.getLocaleValue(product?.title) }}<span v-if="showVariant" class="text-muted"> · {{ line.variantName }}</span>
        </p>
        <p
          v-if="line.modifiers?.length"
          class="mt-0.5 text-[13px]/4 text-muted"
          data-testid="line-modifiers"
        >
          + {{ line.modifiers.map((m) => m.quantity > 1 ? `${m.name} ×${m.quantity}` : m.name).join(', ') }}
        </p>
        <p v-if="line.problems?.length" class="mt-0.5 text-[13px]/4 text-error">
          {{ line.problems[0]?.detail }}
        </p>
      </div>
    </NuxtLink>

    <p class="tabular text-right text-[15px] font-semibold text-highlighted">
      {{ optionsStore.formatCurrency(line.totalPrice) }} {{ optionsStore.currencySign }}
    </p>

    <p class="tabular text-[13px] text-dimmed" :class="{ 'pl-[4.25rem]': images.length > 0 }">
      <template v-if="line.quantity > 1">
        {{ optionsStore.formatCurrency(line.unitPrice) }} {{ optionsStore.currencySign }} × {{ line.quantity }}
      </template>
    </p>
    <div v-if="canBeChanged" class="justify-self-end">
      <CartLineCounter :line="line" />
    </div>
    <p v-else class="justify-self-end text-sm text-muted">
      ×{{ line.quantity }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { OrderItem } from '@nextorders/food-schema'

type Line = OrderItem & {
  productName?: string
  variantName?: string
  modifiers?: { id: string, name: string, quantity: number }[]
  problems?: { code: string, detail: string }[]
}

const { line, canBeChanged = true } = defineProps<{ line: Line, canBeChanged?: boolean }>()

const optionsStore = useOptionsStore()
const menuStore = useMenuStore()

const product = computed(() => menuStore.getProduct(line.productId))
const variant = computed(() => menuStore.getProductVariant(line.variantId))
const images = computed(() => variant.value?.images ?? [])
const productUrl = computed(() => menuStore.getProductUrl(line.productId))
// Variant name only when the dish has several (avoids "Стандарт" noise).
const showVariant = computed(() => (product.value?.variants.length ?? 1) > 1 && !!line.variantName)
</script>

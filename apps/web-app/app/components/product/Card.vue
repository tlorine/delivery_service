<template>
  <article
    class="group relative flex h-full flex-col overflow-hidden rounded-[20px] bg-default ring-1 ring-default transition hover:shadow-float"
    :data-testid="`card-${product.slug}`"
  >
    <NuxtLink :to="productUrl" class="flex flex-1 flex-col">
      <div v-if="hasImage" class="relative aspect-[4/3] overflow-hidden bg-elevated">
        <ProductImage
          :images="variant?.images ?? []"
          :lazy="lazy"
          size="sm"
        />
      </div>
      <div class="flex flex-1 flex-col gap-1 p-3 md:p-3.5" :class="!hasImage && 'bg-elevated/40'">
        <p class="tabular text-[17px] font-bold text-highlighted">
          <span v-if="!single" class="font-medium text-muted">{{ $dict('web-app.cart.from') }}&nbsp;</span>{{ price }}
        </p>
        <h3 class="text-[14px]/5 md:text-[15px]/5 font-medium text-toned" :class="hasImage ? 'line-clamp-2' : 'line-clamp-3'">
          {{ title }}
        </h3>
        <p
          v-if="description"
          class="text-[13px]/4 text-muted"
          :class="hasImage ? 'line-clamp-2' : 'line-clamp-4'"
        >
          {{ description }}
        </p>
        <p v-if="weight" class="mt-auto pt-1 text-[13px] text-dimmed">
          {{ weight }}
        </p>
      </div>
    </NuxtLink>

    <div class="p-2.5 pt-0 md:p-3 md:pt-0" :class="!hasImage && 'bg-elevated/40'">
      <CartLineCounter
        v-if="lineInCart"
        :line="lineInCart"
        class="w-full"
      />
      <button
        v-else-if="canQuickAdd"
        type="button"
        class="btn-accent flex h-10 w-full items-center justify-center gap-1.5 rounded-[12px] text-[15px] font-semibold transition active:scale-98 disabled:opacity-50"
        :disabled="adding || !interactive"
        :aria-label="`${$dict('web-app.cart.add')}: ${title}`"
        data-testid="quick-add"
        @click="quickAdd()"
      >
        <UIcon
          :name="adding ? 'lucide:loader-circle' : 'lucide:plus'"
          class="size-4"
          :class="adding && 'animate-spin'"
        />
        {{ $dict('web-app.cart.add') }}
      </button>
      <NuxtLink
        v-else
        :to="productUrl"
        class="flex h-10 w-full items-center justify-center rounded-[12px] bg-elevated text-[15px] font-semibold text-highlighted transition hover:bg-accented active:scale-98"
      >
        {{ $dict('web-app.product.choose') }}
      </NuxtLink>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { Product } from '@nextorders/food-schema'

const { product } = defineProps<{
  product: Product
  lazy?: boolean
}>()

const optionsStore = useOptionsStore()
const orderStore = useOrderStore()
const menuStore = useMenuStore()
const { impact, notify } = useTelegram()
const toast = useToast()
const { messageOf } = useApiErrorMessage()

const single = computed(() => product.variants.length === 1)
const variant = computed(() => product.variants[0])
const hasImage = computed(() => !!variant.value?.images?.length)
const title = computed(() => optionsStore.getLocaleValue(product.title))
const description = computed(() => optionsStore.getLocaleValue(product.description))
const price = computed(() => `${optionsStore.formatCurrency(variant.value?.price ?? 0)} ${optionsStore.currencySign}`)
const weight = computed(() => {
  const v = variant.value
  return v?.weightValue ? `${single.value ? '' : `${useDictionary().dict('web-app.cart.from')} `}${v.weightValue} ${getWeightLocalizedUnit(v.weightUnit)}` : ''
})
const productUrl = computed(() => menuStore.getProductUrl(product.id))

// Quick add only when nothing must be chosen: one variant and no required modifier group.
const canQuickAdd = computed(() => single.value
  && !menuStore.getModifierGroups(product.id).some((g) => g.min_selected > 0)
  && variant.value?.id)
// The counter controls the plain configuration (without modifiers) of this dish.
const lineInCart = computed(() => canQuickAdd.value
  ? orderStore.items.find((l) => l.variantId === variant.value?.id && !l.modifiers.length)
  : undefined)

const adding = ref(false)
// Server-rendered buttons are inert until hydration: keep them disabled so a tap is never silently lost.
const interactive = ref(false)
onMounted(() => {
  interactive.value = true
})
async function quickAdd() {
  if (!variant.value) {
    return
  }
  adding.value = true
  const ok = await orderStore.add(variant.value.id)
  adding.value = false
  if (ok) {
    impact('light')
  } else {
    notify('error')
    toast.add({ title: messageOf(orderStore.lastError), icon: 'lucide:circle-alert', color: 'error' })
  }
}
</script>

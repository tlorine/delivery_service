<template>
  <div class="pt-1">
    <nav class="mb-3 flex items-center gap-1 text-sm text-muted" aria-label="breadcrumb">
      <button
        type="button"
        class="inline-flex items-center gap-1 rounded-full py-1 pr-2 hover:text-toned"
        :aria-label="$dict('common.return')"
        @click="goBack()"
      >
        <UIcon name="lucide:chevron-left" class="size-5" />
        <span class="hidden sm:inline">{{ $dict('common.return') }}</span>
      </button>
      <NuxtLink to="/" class="hidden md:inline hover:text-toned">
        {{ $dict('common.home') }}
      </NuxtLink>
      <span class="hidden md:inline">/</span>
      <NuxtLink :to="`/${category?.slug}`" class="hover:text-toned">
        {{ optionsStore.getLocaleValue(category?.title) }}
      </NuxtLink>
    </nav>

    <div class="lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-10" :class="!hasImage && 'lg:!grid-cols-1 max-w-2xl'">
      <div v-if="hasImage" class="-mx-4 md:mx-0 lg:sticky lg:top-[calc(var(--header-h)+1.25rem)] lg:self-start">
        <div class="relative aspect-[4/3] max-h-[45vh] w-full overflow-hidden bg-elevated md:rounded-[24px] lg:max-h-none">
          <ProductImage
            :images="selectedVariant?.images ?? []"
            :lazy="false"
            size="md"
          />
        </div>
      </div>

      <div class="mt-4 lg:mt-0 pb-6 lg:pb-0">
        <h1 class="text-[26px]/8 md:text-[32px]/10 font-bold text-highlighted">
          {{ optionsStore.getLocaleValue(product.title) }}
        </h1>
        <p v-if="weightValue" class="mt-1 text-muted">
          {{ weightValue }} {{ weightUnit }}
        </p>
        <p v-if="product.description" class="mt-3 text-[15px]/6 text-toned">
          {{ optionsStore.getLocaleValue(product.description) }}
        </p>

        <div
          v-if="!withSingleVariant"
          class="mt-5 flex flex-wrap gap-2"
          role="radiogroup"
          :aria-label="$dict('web-app.product.size')"
        >
          <button
            v-for="v in product.variants"
            :key="v.id"
            type="button"
            role="radio"
            :aria-checked="v.id === selectedVariantId"
            class="rounded-full px-4 py-2 text-[15px] font-medium ring-1 transition active:scale-98"
            :class="v.id === selectedVariantId ? 'bg-inverted text-inverted ring-inverted' : 'bg-default text-toned ring-default hover:bg-elevated'"
            @click="selectedVariantId = v.id"
          >
            {{ optionsStore.getLocaleValue(v.title) }}<span v-if="v.weightValue" class="opacity-70"> · {{ v.weightValue }} {{ getWeightLocalizedUnit(v.weightUnit) }}</span>
          </button>
        </div>

        <ProductModifiers
          v-if="modifierGroups.length"
          v-model="selection"
          :groups="modifierGroups"
          :currency="optionsStore.currencyCode"
          class="mt-6"
        />

        <ProductCompositionBlock
          v-if="product.composition"
          :composition="product.composition"
          class="mt-6"
        />

        <!-- One action bar: pinned to the bottom on phones/tablets, inline on desktop. -->
        <div class="fixed inset-x-0 bottom-0 z-40 border-t border-default bg-default/95 px-4 pt-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] backdrop-blur lg:static lg:mt-8 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
          <p
            v-if="!selectionComplete"
            class="mb-2 text-center text-sm text-muted lg:text-left"
            data-testid="selection-hint"
          >
            {{ $dict('web-app.product.choose-required') }}
          </p>
          <div class="mx-auto flex max-w-xl items-center gap-3 lg:mx-0">
            <div class="flex h-14 shrink-0 items-center gap-1 rounded-[16px] bg-elevated px-1.5">
              <button
                type="button"
                class="grid size-10 place-items-center rounded-[12px] hover:bg-accented disabled:opacity-40"
                :disabled="quantity <= 1"
                :aria-label="$dict('web-app.cart.decrease')"
                @click="quantity--"
              >
                <UIcon name="lucide:minus" class="size-4" />
              </button>
              <span class="tabular w-6 text-center text-[17px] font-semibold" data-testid="product-quantity">{{ quantity }}</span>
              <button
                type="button"
                class="grid size-10 place-items-center rounded-[12px] hover:bg-accented"
                :aria-label="$dict('web-app.cart.increase')"
                @click="quantity++"
              >
                <UIcon name="lucide:plus" class="size-4" />
              </button>
            </div>
            <button
              type="button"
              class="btn-accent flex h-14 flex-1 items-center justify-between rounded-[16px] px-5 text-[16px] font-semibold transition active:scale-[.99]"
              :disabled="!selectionComplete || !product.isAvailableForPurchase || adding || !interactive"
              data-testid="add-to-cart"
              @click="addToCart()"
            >
              <span>{{ $dict('web-app.cart.add') }}</span>
              <span class="tabular" data-testid="product-price">{{ optionsStore.formatCurrency(unitPrice * quantity) }} {{ optionsStore.currencySign }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="product.recommendedProducts?.length" class="mt-12">
      <h2 class="mb-3 text-[22px] font-bold">
        {{ $dict('web-app.most-often-added') }}
      </h2>
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <ProductRecommendedCard
          v-for="p in product.recommendedProducts"
          :key="p.productVariantId"
          :product="p"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { dict } = useDictionary()
const { params } = useRoute()
const router = useRouter()

const orderStore = useOrderStore()
const channelStore = useChannelStore()
const optionsStore = useOptionsStore()
const menuStore = useMenuStore()

const product = menuStore.getProductBySlug(String(params.productSlug))
if (!product) {
  throw createError({
    statusCode: 404,
    statusMessage: 'Product not found',
  })
}

useHead({
  title: `${optionsStore.getLocaleValue(product.title)} | ${optionsStore.getLocaleValue(channelStore.title)}`,
  meta: [{ name: 'description', content: optionsStore.getLocaleValue(product.description) }],
})

const withSingleVariant = computed<boolean>(() => product.variants.length === 1)
const selectedVariantId = ref(product.variants[0]?.id)
const selectedVariant = computed(() => product.variants.find(({ id }) => id === selectedVariantId.value))
const hasImage = computed(() => product.variants.some((v) => v.images.length))

const weightValue = computed(() => selectedVariant.value?.weightValue)
const weightUnit = computed(() => getWeightLocalizedUnit(selectedVariant.value?.weightUnit))

const category = menuStore.getCategoryByProductId(product.id)

const modifierGroups = computed(() => menuStore.getModifierGroups(product.id))
const selection = ref<Record<string, number>>({})
const extraMinor = computed(() => selectionExtraMinor(modifierGroups.value, selection.value))
const selectionComplete = computed(() => selectionIsComplete(modifierGroups.value, selection.value))
const quantity = ref(1)
// Display only: the server prices the line again (ADR-0004).
const unitPrice = computed(() => (selectedVariant.value?.price ?? 0) + minorToDisplay(extraMinor.value))

const toast = useToast()
const { messageOf } = useApiErrorMessage()
const { impact, notify } = useTelegram()
const adding = ref(false)
const interactive = ref(false)
onMounted(() => {
  interactive.value = true
})

function goBack() {
  if (window.history.state?.back) {
    router.back()
  } else {
    navigateTo(`/${category?.slug ?? ''}`)
  }
}

async function addToCart() {
  if (!selectedVariantId.value) {
    return
  }
  adding.value = true
  const modifiers = Object.entries(selection.value).map(([modifierId, q]) => ({ modifierId, quantity: q }))
  const ok = await orderStore.add(selectedVariantId.value, modifiers, quantity.value)
  adding.value = false
  if (ok) {
    impact('light')
    toast.add({ title: dict('web-app.product.added'), icon: 'lucide:check', color: 'success', duration: 1500 })
    selection.value = {}
    quantity.value = 1
  } else {
    notify('error')
    toast.add({ title: messageOf(orderStore.lastError), icon: 'lucide:circle-alert', color: 'error' })
  }
}
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-default bg-default/90 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-default/75">
    <div class="mx-auto flex h-[var(--header-h)] w-full max-w-7xl items-center gap-3 px-4 md:px-6 lg:px-8">
      <NuxtLink
        to="/"
        class="flex min-w-0 items-center gap-2.5"
        :aria-label="$dict('common.home')"
      >
        <StoreLogo size="sm" />
        <span class="truncate font-semibold text-[15px] md:text-base">{{ title }}</span>
      </NuxtLink>

      <div class="ml-auto flex items-center gap-2">
        <UButton
          v-if="isMobileApp"
          to="/venues"
          icon="lucide:store"
          color="neutral"
          variant="soft"
          size="lg"
          class="rounded-full"
          :aria-label="$dict('web-app.venues.title')"
          data-testid="my-venues-button"
        />
        <UModal v-if="products.length" v-model:open="isSearchOpened">
          <UButton
            icon="lucide:search"
            color="neutral"
            variant="soft"
            size="lg"
            class="rounded-full"
            :aria-label="$dict('web-app.search.placeholder')"
            :ui="{ label: 'hidden md:inline' }"
            :label="$dict('web-app.search.placeholder')"
          />
          <template #content>
            <UCommandPalette
              v-model="value"
              :groups="groups"
              :placeholder="$dict('web-app.search.placeholder')"
              class="h-96"
            />
          </template>
        </UModal>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()
const menuStore = useMenuStore()

const title = computed(() => optionsStore.getLocaleValue(channelStore.title))
const isSearchOpened = ref(false)
const isMobileApp = usePlatform() === 'mobile'
const products = computed(() => menuStore.getProductsForSearch())

const groups = computed(() => [
  {
    id: 'products',
    items: products.value.map((product) => ({
      label: optionsStore.getLocaleValue(product.title),
      suffix: optionsStore.getLocaleValue(product.category.title),
      onSelect: () => {
        isSearchOpened.value = false
        navigateTo(`/${product.category.slug}/${product.slug}`)
      },
    })),
  },
])
const value = ref({})
</script>

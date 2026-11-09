<template>
  <MaintenanceMessage v-if="channelStore.isOnMaintenance" />

  <StoreHero class="mb-2" />
  <CategoryNav mode="anchors" />

  <CategoryBlock
    v-for="(category, index) in categories"
    :key="category.id"
    :category="category"
    :is-first="index === 0"
  />
</template>

<script setup lang="ts">
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()
const menuStore = useMenuStore()

const categories = computed(() => menuStore.categories.filter((c) => c.products.some((p) => p.isAvailableForPurchase && p.variants.length)))

useHead({
  title: optionsStore.getLocaleValue(channelStore.title),
  meta: [
    {
      name: 'description',
      content: optionsStore.getLocaleValue(channelStore.description),
    },
  ],
})
</script>

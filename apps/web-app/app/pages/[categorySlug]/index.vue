<template>
  <CategoryNav mode="links" :current="category?.slug" />
  <h1 class="mt-3 mb-4 text-[28px]/8 md:text-[34px]/10 font-bold text-highlighted">
    {{ optionsStore.getLocaleValue(category?.title) }}
  </h1>
  <ProductGrid :products="products" />
</template>

<script setup lang="ts">
const { params } = useRoute()
const channelStore = useChannelStore()
const optionsStore = useOptionsStore()
const menuStore = useMenuStore()

const category = menuStore.getCategoryBySlug(String(params.categorySlug))
if (!category) {
  throw createError({
    statusCode: 404,
    statusMessage: 'Category not found',
  })
}

const products = menuStore.getProductsInCategory(category.id).filter((p) => p.isAvailableForPurchase && p.variants.length)

useHead({
  title: `${optionsStore.getLocaleValue(category?.title)} | ${optionsStore.getLocaleValue(channelStore.title)}`,
})
</script>

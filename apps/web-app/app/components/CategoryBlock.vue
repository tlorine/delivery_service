<template>
  <section :id="category.slug" class="scroll-mt-32 pt-6 first:pt-2">
    <h2 class="mb-3 text-[22px]/7 md:text-[26px]/8 font-bold text-highlighted">
      <NuxtLink :to="`/${category.slug}`" class="hover:underline underline-offset-4 decoration-2">
        {{ optionsStore.getLocaleValue(category.title) }}
      </NuxtLink>
    </h2>
    <ProductGrid :products="products" :lazy="!isFirst" />
  </section>
</template>

<script setup lang="ts">
import type { MenuCategory } from '@nextorders/food-schema'

const { category } = defineProps<{
  category: MenuCategory
  isFirst?: boolean
}>()

const optionsStore = useOptionsStore()
const products = computed(() => category.products.filter((p) => p.isAvailableForPurchase && p.variants?.length))
</script>

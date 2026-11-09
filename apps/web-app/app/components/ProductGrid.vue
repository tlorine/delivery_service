<template>
  <!-- 2 columns on phones, 3 on tablets, 4 on wide screens (3 next to the desktop cart). -->
  <div class="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-3 2xl:grid-cols-4 md:gap-4">
    <ProductCard
      v-for="product in products"
      :key="product.id"
      :product="product"
      :lazy="lazy"
    />
  </div>
</template>

<script setup lang="ts">
import type { Product } from '@nextorders/food-schema'

defineProps<{ products: Product[], lazy?: boolean }>()
</script>

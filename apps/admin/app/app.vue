<template>
  <UApp :locale="ru" :toaster="{ position: 'top-right' }">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>

<script setup lang="ts">
import { ru } from '@nuxt/ui/locale'
</script>

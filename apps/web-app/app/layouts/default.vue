<template>
  <!-- The document scrolls (no inner scroll container): native address-bar collapse, tap-to-top, Telegram gestures. -->
  <Header />

  <div class="mx-auto w-full max-w-7xl px-4 md:px-6 lg:px-8 xl:grid xl:grid-cols-[minmax(0,1fr)_22rem] xl:gap-8">
    <main class="min-w-0 pt-3 md:pt-5 pb-28 xl:pb-12">
      <slot />
    </main>

    <!-- Mounted only on wide screens: one cart in the DOM / accessibility tree per layout. -->
    <aside
      v-if="isWide"
      class="hidden xl:block pt-5"
      :aria-label="$dict('web-app.cart.title')"
    >
      <div class="sticky top-[calc(var(--header-h)+1.25rem)]">
        <div class="rounded-[24px] bg-default ring-1 ring-default py-2">
          <Cart />
        </div>
      </div>
    </aside>
  </div>

  <Footer />
  <CartBar />
</template>

<script setup lang="ts">
import { useMediaQuery } from '@vueuse/core'

const isWide = useMediaQuery('(min-width: 1280px)')
</script>

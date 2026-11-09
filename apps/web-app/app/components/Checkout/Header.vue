<template>
  <div class="mx-auto flex h-[var(--header-h)] w-full max-w-6xl items-center gap-3 px-4 md:px-6 lg:px-8">
    <UButton
      to="/"
      icon="lucide:chevron-left"
      variant="ghost"
      color="neutral"
      size="lg"
      class="-ml-2"
      :label="$dict('web-app.checkout.back-to-menu')"
    />
    <span class="ml-auto truncate text-sm text-muted">{{ optionsStore.getLocaleValue(channelStore.title) }}</span>
  </div>
</template>

<script setup lang="ts">
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()
</script>

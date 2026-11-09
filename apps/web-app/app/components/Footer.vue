<template>
  <footer class="mt-8 border-t border-default bg-default">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-8 pb-32 md:px-6 lg:px-8 xl:pb-10">
      <div class="flex flex-col gap-1">
        <p class="font-semibold">
          {{ optionsStore.getLocaleValue(channelStore.title) }}
        </p>
        <p
          v-for="b in channelStore.branches"
          :key="b.id"
          class="text-sm text-muted"
        >
          {{ b.address }}<template v-if="b.phone">
            · <a :href="`tel:${b.phone}`" class="underline-offset-2 hover:underline">{{ b.phone }}</a>
          </template>
        </p>
      </div>

      <UNavigationMenu
        v-if="footerMenuItems?.length"
        variant="link"
        orientation="vertical"
        :items="footerMenuItems"
        class="-ml-2.5 w-full"
      />

      <div class="flex flex-wrap items-center justify-between gap-3">
        <p v-if="copyright" class="whitespace-pre-wrap text-xs text-muted">
          {{ copyright }}
        </p>
        <div class="flex items-center gap-2">
          <UColorModeButton variant="ghost" color="neutral" />
          <LanguageSelect :available-locales="optionsStore.availableLocales" />
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()

// Hide a copyright that only repeats the cafe name shown above.
const copyright = computed(() => {
  const text = optionsStore.getLocaleValue(channelStore.copyright)
  return text && text !== optionsStore.getLocaleValue(channelStore.title) ? text : ''
})

const footerMenuItems = computed(() => channelStore.links?.footer.map((link) => ({
  label: optionsStore.getLocaleValue(link.label),
  to: link.to,
  icon: link.icon,
  target: link.target,
})))
</script>

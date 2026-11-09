<template>
  <UApp :locale="locales[locale]" :tooltip="{ delayDuration: 200 }">
    <NuxtLoadingIndicator :color="false" class="bg-primary h-0.5" />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>

<script setup lang="ts">
import * as locales from '@nuxt/ui/locale'

const { locale } = useI18n()

const lang = computed(() => locales[locale.value].code)
const dir = computed(() => locales[locale.value].dir)

const brand = useBranding()

// Init Stores: storefront first (tenant locale), then menu.
const storefrontStore = useStorefrontStore()
const optionsStore = useOptionsStore()
const orderStore = useOrderStore()
const channelStore = useChannelStore()
const menuStore = useMenuStore()

// Mobile app without a chosen cafe shows "Мои заведения" (middleware): nothing to load yet.
const hasTenant = usePlatform() !== 'mobile' || !!useVenues().current.value
if (hasTenant) {
  await storefrontStore.update()
  await menuStore.update()
}

let interval: ReturnType<typeof setInterval>

onMounted(() => {
  // Only on client: the cart token and saved contacts live on the device.
  if (!hasTenant) {
    return
  }
  orderStore.restoreContacts()
  orderStore.update()

  // Opening status and stop-list change during the day.
  interval = setInterval(() => {
    Promise.all([channelStore.update(), menuStore.update()]).catch(() => {})
  }, 60_000)
})

onBeforeUnmount(() => {
  clearInterval(interval)
})

useHead({
  htmlAttrs: {
    lang,
    dir,
    // Tenant accent from data, already validated and contrast-checked (utils/brandColor.ts).
    style: computed(() => `--brand-accent:${brand.tokens.value.accent};--brand-on-accent:${brand.tokens.value.onAccent}`),
  },
  link: optionsStore.headLinks,
  style: optionsStore.headStyles,
  script: optionsStore.headScripts,
})
</script>

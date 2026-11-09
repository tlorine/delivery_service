<template>
  <img
    v-if="logoUrl"
    :src="logoUrl"
    alt=""
    class="shrink-0 rounded-full object-cover bg-elevated"
    :class="sizeClass"
  >
  <span
    v-else
    aria-hidden="true"
    class="btn-accent shrink-0 grid place-items-center rounded-full font-bold"
    :class="sizeClass"
  >{{ initial }}</span>
</template>

<script setup lang="ts">
const { size = 'sm' } = defineProps<{ size?: 'sm' | 'lg' }>()

const NON_ALNUM_RE = /[^\p{L}\p{N}]/gu
const { logoUrl } = useBranding()
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()

// First letter of the name without quotes/«»: "Кафе «У моря»" -> "К".
const initial = computed(() => optionsStore.getLocaleValue(channelStore.title).replace(NON_ALNUM_RE, '').charAt(0).toUpperCase())
const sizeClass = computed(() => size === 'lg' ? 'size-14 text-2xl' : 'size-8 text-sm')
</script>

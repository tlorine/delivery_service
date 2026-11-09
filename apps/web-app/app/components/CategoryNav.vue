<template>
  <!-- Sticky horizontal category rail; on the catalog page it follows scrolling (scroll-spy). -->
  <nav
    class="sticky top-[var(--header-h)] z-30 -mx-4 md:-mx-6 lg:-mx-8 xl:mx-0 bg-muted/95 backdrop-blur supports-[backdrop-filter]:bg-muted/80"
    :aria-label="$dict('web-app.catalog')"
  >
    <ul ref="rail" class="no-scrollbar flex gap-2 overflow-x-auto px-4 md:px-6 lg:px-8 xl:px-0 py-2.5">
      <li
        v-for="c in categories"
        :key="c.id"
        class="shrink-0"
      >
        <NuxtLink
          :to="mode === 'anchors' ? `#${c.slug}` : `/${c.slug}`"
          :data-slug="c.slug"
          class="block rounded-full px-4 py-2 text-[15px] font-medium transition active:scale-98"
          :class="isActive(c.slug) ? 'bg-inverted text-inverted' : 'bg-default text-toned ring-1 ring-default hover:bg-elevated'"
          :aria-current="isActive(c.slug) ? 'true' : undefined"
          @click="mode === 'anchors' && scrollTo($event, c.slug)"
        >
          {{ optionsStore.getLocaleValue(c.title) }}
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
const { mode = 'anchors', current } = defineProps<{ mode?: 'anchors' | 'links', current?: string }>()

const optionsStore = useOptionsStore()
const menuStore = useMenuStore()
const categories = computed(() => menuStore.categories.filter((c) => c.products.some((p) => p.isAvailableForPurchase && p.variants.length)))
const active = ref<string | undefined>(current)
const rail = useTemplateRef<HTMLUListElement>('rail')

const isActive = (slug: string) => active.value === slug

function offset(): number {
  // header + this rail
  return (document.querySelector('header')?.clientHeight ?? 56) + (rail.value?.clientHeight ?? 52) + 8
}

function scrollTo(event: MouseEvent, slug: string) {
  const target = document.getElementById(slug)
  if (!target) {
    return
  }
  event.preventDefault()
  active.value = slug
  window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - offset() + 1, behavior: 'smooth' })
  history.replaceState(history.state, '', `#${slug}`)
}

// Keep the active chip visible in the rail.
watch(active, (slug) => {
  rail.value?.querySelector<HTMLElement>(`[data-slug="${slug}"]`)?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
})

let observer: IntersectionObserver | undefined
onMounted(() => {
  if (mode !== 'anchors') {
    return
  }
  active.value ??= categories.value[0]?.slug
  observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
    if (visible[0]) {
      active.value = visible[0].target.id
    }
  }, { rootMargin: `-${offset()}px 0px -60% 0px` })
  for (const c of categories.value) {
    const el = document.getElementById(c.slug)
    if (el) {
      observer.observe(el)
    }
  }
})
onBeforeUnmount(() => observer?.disconnect())
</script>

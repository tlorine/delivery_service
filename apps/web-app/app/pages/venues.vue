<template>
  <div class="mx-auto flex max-w-xl flex-col gap-6 px-4 pb-10 pt-[max(env(safe-area-inset-top),1.5rem)]">
    <div>
      <h1 class="text-[28px]/8 font-bold text-highlighted">
        {{ $dict('web-app.venues.title') }}
      </h1>
      <p class="mt-1 text-muted">
        {{ $dict('web-app.venues.subtitle') }}
      </p>
    </div>

    <ul
      v-if="venues.list.value.length"
      class="flex flex-col gap-2"
      data-testid="my-venues"
    >
      <li
        v-for="v in venues.list.value"
        :key="v.slug"
        class="flex items-center gap-3 rounded-[16px] bg-default p-3 ring-1 ring-default"
      >
        <button
          type="button"
          class="flex min-w-0 flex-1 items-center gap-3 text-left"
          @click="select(v.slug)"
        >
          <img
            v-if="v.logoUrl"
            :src="v.logoUrl"
            alt=""
            class="size-11 rounded-full object-cover"
          >
          <span v-else class="btn-accent grid size-11 shrink-0 place-items-center rounded-full font-bold">{{ v.name.replace(NON_ALNUM_RE, '').charAt(0).toUpperCase() }}</span>
          <span class="min-w-0">
            <span class="block truncate font-semibold text-highlighted">{{ v.name }}</span>
            <span v-if="v.slug === venues.current.value" class="text-sm text-success">{{ $dict('web-app.venues.current') }}</span>
          </span>
        </button>
        <UButton
          icon="lucide:x"
          variant="ghost"
          color="neutral"
          :aria-label="`${$dict('web-app.venues.forget')}: ${v.name}`"
          @click="venues.forget(v.slug)"
        />
      </li>
    </ul>
    <p
      v-else
      class="rounded-[16px] bg-elevated p-4 text-[15px] text-toned"
      data-testid="venues-empty"
    >
      {{ $dict('web-app.venues.empty') }}
    </p>

    <form class="flex flex-col gap-2" @submit.prevent="submit">
      <label for="venue-code" class="font-semibold">{{ $dict('web-app.venues.code-label') }}</label>
      <div class="flex gap-2">
        <UInput
          id="venue-code"
          v-model="code"
          size="xl"
          class="flex-1"
          autocapitalize="none"
          autocomplete="off"
          :placeholder="$dict('web-app.venues.code-placeholder')"
          data-testid="venue-code"
        />
        <button
          type="submit"
          class="btn-accent h-12 rounded-[12px] px-5 font-semibold disabled:opacity-50"
          :disabled="!code.trim() || loading"
          data-testid="venue-open"
        >
          {{ $dict('web-app.venues.open') }}
        </button>
      </div>
      <p
        v-if="error"
        class="text-sm text-error"
        role="alert"
      >
        {{ error }}
      </p>
      <p class="text-sm text-muted">
        {{ $dict('web-app.venues.hint') }}
      </p>
    </form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'empty' })

if (usePlatform() !== 'mobile') {
  // The web storefront always belongs to one cafe (its domain); there is no cafe list on the web.
  throw createError({ statusCode: 404, statusMessage: 'Not found' })
}

const NON_ALNUM_RE = /[^\p{L}\p{N}]/gu
const { dict } = useDictionary()
const route = useRoute()
const venues = useVenues()
const code = ref('')
const loading = ref(false)
const error = ref(route.query.error === 'not-found' ? dict('web-app.venues.not-found') : '')

async function select(slug: string) {
  loading.value = true
  const venue = await venues.open(slug)
  loading.value = false
  if (venue) {
    reloadNuxtApp({ path: '/', force: true }) // fresh stores for the chosen cafe
  } else {
    error.value = dict('web-app.venues.not-found')
  }
}

async function submit() {
  error.value = ''
  const slug = venueFromInput(code.value)
  if (!slug) {
    error.value = dict('web-app.venues.invalid')
    return
  }
  await select(slug)
}
</script>

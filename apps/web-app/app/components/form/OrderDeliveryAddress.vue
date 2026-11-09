<template>
  <div class="flex flex-col gap-2">
    <h2 class="text-[19px] font-bold text-highlighted">
      {{ $dict('web-app.checkout.delivery-address') }}
    </h2>

    <UFormField
      :label="$dict('web-app.checkout.address.street')"
      :ui="{
        label: 'after:text-secondary',
      }"
      required
    >
      <UInputMenu
        v-if="optionsStore.addressSuggestEnabled"
        v-model="selectedValue"
        v-model:search-term="searchTerm"
        :items="suggestionItems"
        ignore-filter
        size="xl"
        class="w-full"
        :placeholder="$dict('web-app.checkout.street-placeholder')"
        trailing-icon=""
      />
      <UInput
        v-else
        v-model="state.street"
        :placeholder="$dict('web-app.checkout.street-placeholder')"
        size="xl"
        class="w-full"
      />
    </UFormField>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 items-end">
      <UFormField
        :label="$dict('web-app.checkout.address.flat')"
        :ui="{
          label: 'leading-4 line-clamp-2',
        }"
      >
        <UInput v-model="state.flat" size="xl" />
      </UFormField>

      <UFormField
        :label="$dict('web-app.checkout.address.intercom')"
        :ui="{
          label: 'leading-4 line-clamp-2',
        }"
      >
        <UInput v-model="state.intercom" size="xl" />
      </UFormField>

      <UFormField
        :label="$dict('web-app.checkout.address.entrance')"
        :ui="{
          label: 'leading-4 line-clamp-2',
        }"
      >
        <UInput v-model="state.entrance" size="xl" />
      </UFormField>

      <UFormField
        :label="$dict('web-app.checkout.address.floor')"
        :ui="{
          label: 'leading-4 line-clamp-2',
        }"
      >
        <UInput v-model="state.floor" size="xl" />
      </UFormField>
    </div>

    <!-- Delivery zone: computed by the server quote -->
    <div v-if="zoneOk" class="rounded-lg bg-default p-4 my-2 text-base text-secondary flex items-center gap-3">
      <UIcon name="i-lucide-map-pin-check" class="size-8 shrink-0" />
      <div>
        <p class="font-medium">
          {{ orderStore.quote?.delivery_zone_name }}
        </p>
        <p class="text-muted">
          {{ $dict('web-app.checkout.delivery-cost') }}: {{ optionsStore.formatCurrency(orderStore.deliveryFee) }}
          {{ optionsStore.currencySign }}
        </p>
      </div>
    </div>
    <div v-else-if="zoneNotFound" class="rounded-lg bg-default p-4 my-2 flex items-center gap-3">
      <UIcon name="i-lucide-map-pin-off" class="size-8 shrink-0 text-secondary" />
      <p class="text-base">
        {{ $dict('web-app.checkout.delivery-zone-not-found') }}
      </p>
    </div>
    <p v-else-if="state.street && state.lat == null" class="text-sm text-muted my-1">
      {{ $dict('web-app.checkout.choose-address') }}
    </p>

    <UFormField :label="$dict('web-app.checkout.address.note')">
      <UTextarea
        v-model="state.addressNote"
        size="xl"
        class="w-full"
        :placeholder="$dict('web-app.checkout.address.note-placeholder')"
      />
    </UFormField>
  </div>
</template>

<script setup lang="ts">
import type { OrderDeliveryAddress } from '@nextorders/food-schema'
import { refDebounced } from '@vueuse/core'

interface Suggestion { value: string, lat: number | null, lon: number | null, has_house: boolean }

const optionsStore = useOptionsStore()
const orderStore = useOrderStore()
const { $api } = useNuxtApp()

const savedAddress = orderStore.address?.type === 'deliveryAddress' ? orderStore.address : null

const state = ref<OrderDeliveryAddress>({
  type: 'deliveryAddress',
  street: savedAddress?.street ?? '',
  flat: savedAddress?.flat ?? '',
  intercom: savedAddress?.intercom ?? '',
  entrance: savedAddress?.entrance ?? '',
  floor: savedAddress?.floor ?? '',
  addressNote: savedAddress?.addressNote ?? '',
  lat: savedAddress?.lat ?? null,
  lon: savedAddress?.lon ?? null,
})

const zoneNotFound = computed(() => orderStore.problems.some((p) => p.code === 'outside_delivery_zone'))
const zoneOk = computed(() => !!orderStore.quote?.delivery_zone_name && !zoneNotFound.value)

// Address suggestions come with coordinates; the server prices delivery by zone.
const searchTerm = ref(state.value.street)
const selectedValue = ref(state.value.street)
const searchTermDebounced = refDebounced(searchTerm, 300)
const suggestions = ref<Suggestion[]>([])
const suggestionItems = computed(() => suggestions.value.map((s) => s.value))
const suppressNextSearch = ref(false)

watch(selectedValue, (value) => {
  if (!value) {
    return
  }
  const suggestion = suggestions.value.find((s) => s.value === value)
  state.value.street = value
  state.value.lat = suggestion?.lat ?? null
  state.value.lon = suggestion?.lon ?? null
  suppressNextSearch.value = true
  searchTerm.value = value
  suggestions.value = []
})

watch(searchTermDebounced, async (query) => {
  if (suppressNextSearch.value) {
    suppressNextSearch.value = false
    return
  }
  if (!query || query.length < 3) {
    suggestions.value = []
    return
  }
  try {
    suggestions.value = await $api.get('/v1/address/suggest', { query: { q: query, limit: 5 } })
  } catch {
    suggestions.value = []
  }
})

watch(state, () => {
  orderStore.address = state.value
  orderStore.isSaved = false
}, { deep: true, immediate: true })
</script>

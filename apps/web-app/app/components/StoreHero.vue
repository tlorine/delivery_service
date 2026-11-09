<template>
  <section class="flex flex-col gap-4" data-testid="store-hero">
    <div v-if="coverUrl" class="overflow-hidden rounded-[24px] bg-elevated aspect-[21/9] md:aspect-[3/1]">
      <img
        :src="coverUrl"
        alt=""
        class="size-full object-cover"
        fetchpriority="high"
      >
    </div>

    <div class="flex items-start gap-3.5">
      <StoreLogo size="lg" class="hidden sm:grid sm:block" />
      <div class="min-w-0 flex-1">
        <h1 class="text-[28px]/8 md:text-[34px]/10 font-bold text-highlighted">
          {{ title }}
        </h1>
        <p v-if="description" class="mt-1 text-muted text-[15px]/5">
          {{ description }}
        </p>

        <div class="mt-3 flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition active:scale-98"
            :class="status?.isClosed ? 'bg-elevated text-toned' : 'bg-success/10 text-success'"
            data-testid="store-status"
            @click="modalSchedule.open()"
          >
            <span class="size-2 rounded-full" :class="status?.isClosed ? 'bg-dimmed' : 'bg-success'" />
            {{ statusText }}
          </button>
          <span v-if="deliveryText" class="inline-flex items-center gap-1.5 rounded-full bg-elevated px-3 py-1.5 text-toned">
            <UIcon name="lucide:bike" class="size-4" />{{ deliveryText }}
          </span>
          <span v-if="pickupText" class="inline-flex items-center gap-1.5 rounded-full bg-elevated px-3 py-1.5 text-toned">
            <UIcon name="lucide:shopping-bag" class="size-4" />{{ pickupText }}
          </span>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-toned underline-offset-2 hover:underline"
            @click="modalInfo.open()"
          >
            <UIcon name="lucide:info" class="size-4" />{{ $dict('web-app.cart.conditions') }}
          </button>
        </div>
      </div>
    </div>

    <CartDeliveryMethodSwitch class="sm:max-w-sm" />
  </section>
</template>

<script setup lang="ts">
import { ModalDeliveryInfo, ModalDeliverySchedule } from '#components'

const SPACES_RE = /\s+/g
const { dict } = useDictionary()
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()
const orderStore = useOrderStore()
const { coverUrl } = useBranding()

const overlay = useOverlay()
const modalInfo = overlay.create(ModalDeliveryInfo)
const modalSchedule = overlay.create(ModalDeliverySchedule)

const title = computed(() => optionsStore.getLocaleValue(channelStore.title))
const description = computed(() => optionsStore.getLocaleValue(channelStore.description))

const status = computed(() => orderStore.deliveryMethod === 'selfPickup' ? channelStore.selfPickupOpeningStatus : channelStore.deliveryOpeningStatus)
const statusText = computed(() => {
  const s = status.value
  if (!s) {
    return ''
  }
  if (!s.isClosed) {
    return s.todayEndAt ? `${dict('web-app.store.open-until')} ${s.todayEndAt}` : dict('web-app.store.open')
  }
  if (!s.nextOpening) {
    return dict('web-app.store.closed')
  }
  const when = s.nextOpening.relativeDays === 0
    ? dict('web-app.store.today')
    : s.nextOpening.relativeDays === 1 ? dict('web-app.store.tomorrow') : ''
  return `${dict('web-app.store.closed')} · ${dict('web-app.store.opens')} ${when} ${s.nextOpening.time}`.replace(SPACES_RE, ' ')
})

const branch = computed(() => channelStore.branches[0])
const deliveryText = computed(() => {
  const b = branch.value
  if (!b || !channelStore.deliveryByCourier?.isAvailable) {
    return ''
  }
  const from = b.prep_time_min + b.delivery_time_min
  return `${dict('web-app.cart.delivery')} ${from}–${from + 20} ${dict('common.abbreviation.min')}`
})
const pickupText = computed(() => {
  const b = branch.value
  if (!b || !channelStore.selfPickup?.isAvailable) {
    return ''
  }
  return `${dict('web-app.cart.pickup')} ${dict('web-app.store.in')} ${b.prep_time_min} ${dict('common.abbreviation.min')}`
})
</script>

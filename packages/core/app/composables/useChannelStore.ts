import type { Channel, OpeningStatus } from '@nextorders/food-schema'

export interface TimeSlot {
  /** ISO datetime sent to the API as requested_at */
  value: string
  /** Local time of the branch, HH:MM */
  label: string
}

/**
 * The cafe as the storefront components know it (food-schema `Channel`), adapted from /v1/storefront.
 * One storefront = one tenant; branches appear as pickup points.
 */
export const useChannelStore = defineStore('channel', () => {
  const storefront = useStorefrontStore()

  const channel = computed<Channel | null>(() => storefront.data ? channelView(storefront.data) : null)

  const id = computed(() => channel.value?.id)
  const isActive = computed(() => channel.value?.isActive ?? false)
  const title = computed(() => channel.value?.title)
  const description = computed(() => channel.value?.description)
  const copyright = computed(() => channel.value?.copyright)
  const deliveryByCourier = computed(() => channel.value?.deliveryByCourier)
  const selfPickup = computed(() => channel.value?.selfPickup)
  const links = computed<Channel['links']>(() => undefined)
  const branches = computed(() => storefront.data?.branches ?? [])

  const deliveryOpeningStatus = computed<OpeningStatus | undefined>(() => {
    const sf = storefront.data
    const branch = sf ? deliveryBranches(sf)[0] : undefined
    return sf && branch ? openingStatusView(branch, sf.server_time) : undefined
  })
  const selfPickupOpeningStatus = computed<OpeningStatus | undefined>(() => {
    const sf = storefront.data
    const branch = sf ? pickupBranches(sf)[0] : undefined
    return sf && branch ? openingStatusView(branch, sf.server_time) : undefined
  })

  const timeSlots = ref<TimeSlot[]>([])
  const isOnMaintenance = computed(() => storefront.data !== null && !isActive.value)

  /** Refreshes opening status (server time) for all consumers. */
  async function update() {
    await storefront.update()
  }

  async function updateTimeSlots(branchId: string | undefined, fulfillment: 'delivery' | 'pickup') {
    const branch = branches.value.find((b) => b.id === branchId) ?? branches.value[0]
    if (!branch) {
      timeSlots.value = []
      return
    }
    try {
      const slots = await useNuxtApp().$api.get('/v1/storefront/time-slots', {
        query: { branch_id: branch.id, fulfillment },
      })
      timeSlots.value = slots.map((value) => ({ value, label: localParts(value, branch.timezone).time }))
    } catch {
      timeSlots.value = []
    }
  }

  return {
    id,
    isActive,
    title,
    description,
    copyright,
    deliveryByCourier,
    selfPickup,
    links,
    branches,

    deliveryOpeningStatus,
    selfPickupOpeningStatus,
    timeSlots,

    isOnMaintenance,

    update,
    updateTimeSlots,
  }
})

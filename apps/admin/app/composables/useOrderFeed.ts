import type { AdminOrder, OrderStatus } from '@delivery/api-client'

export const ACTIVE: OrderStatus[] = ['confirmed', 'preparing', 'ready', 'delivering']
export const DONE: OrderStatus[] = ['completed', 'cancelled', 'rejected']

function beep() {
  try {
    const ctx = new AudioContext()
    for (const [i, freq] of [880, 1320].entries()) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.2, ctx.currentTime + i * 0.25)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.25 + 0.22)
      osc.connect(gain).connect(ctx.destination)
      osc.start(ctx.currentTime + i * 0.25)
      osc.stop(ctx.currentTime + i * 0.25 + 0.25)
    }
  } catch {
    // Audio may be blocked until the first interaction; the badge still shows new orders.
  }
}

/** Live list of orders: polls the API, rings on new pending orders, shows the count in the tab title. */
export function useOrderFeed(statuses: Ref<OrderStatus[]>) {
  const api = useAdminApi()
  const orders = ref<AdminOrder[]>([])
  const pendingCount = ref(0)
  const loaded = ref(false)
  const known = new Set<string>()
  let timer: ReturnType<typeof setInterval> | undefined

  async function refresh() {
    try {
      const [list, pending] = await Promise.all([
        api.get('/v1/admin/orders', { query: { status: statuses.value, limit: 100 } }),
        api.get('/v1/admin/orders', { query: { status: ['pending'], limit: 100 } }),
      ])
      const fresh = pending.items.filter((o) => !known.has(o.id))
      if (loaded.value && fresh.length) {
        beep()
      }
      for (const o of pending.items) {
        known.add(o.id)
      }
      orders.value = list.items
      pendingCount.value = pending.items.length
      loaded.value = true
    } catch {
      // Keep the last list on a transient failure; the next poll retries.
    }
  }

  watch(statuses, refresh)
  onMounted(() => {
    refresh()
    timer = setInterval(refresh, 10_000)
  })
  onBeforeUnmount(() => clearInterval(timer))
  useHead({ title: () => pendingCount.value ? `(${pendingCount.value}) Заказы` : 'Заказы' })

  return { orders, pendingCount, loaded, refresh }
}

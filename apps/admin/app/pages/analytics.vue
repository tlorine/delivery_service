<template>
  <div v-if="s" class="flex flex-col gap-5 max-w-4xl">
    <h1 class="text-2xl font-semibold">
      Аналитика
    </h1>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <UCard v-for="tile in tiles" :key="tile.label">
        <p class="text-sm text-muted">
          {{ tile.label }}
        </p>
        <p class="text-2xl font-semibold tracking-tight" :data-testid="tile.id">
          {{ tile.value }}
        </p>
      </UCard>
    </div>

    <UCard>
      <p class="font-medium mb-3">
        Выручка по дням
      </p>
      <div class="flex flex-col gap-1.5">
        <div
          v-for="d in s.days"
          :key="d.date"
          class="grid grid-cols-[4.5rem_1fr_6.5rem] items-center gap-2 text-sm"
        >
          <span class="text-muted">{{ new Date(`${d.date}T12:00:00`).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' }) }}</span>
          <div class="h-4 rounded bg-elevated overflow-hidden">
            <div class="h-full bg-primary" :style="{ width: `${max ? (d.revenue_minor / max) * 100 : 0}%` }" />
          </div>
          <span class="text-right tracking-tight">{{ formatMoney(d.revenue_minor, s.currency) }} · {{ d.orders }}</span>
        </div>
      </div>
    </UCard>

    <UCard v-if="s.top_products.length">
      <p class="font-medium mb-2">
        Популярное за {{ s.days.length }} дн.
      </p>
      <div
        v-for="p in s.top_products"
        :key="p.name"
        class="flex justify-between text-sm py-1"
      >
        <span>{{ p.name }}</span><span class="text-muted">{{ p.quantity }} шт · {{ formatMoney(p.revenue_minor, s.currency) }}</span>
      </div>
    </UCard>
    <p class="text-xs text-muted">
      Выручка — заказы без отменённых и отклонённых, по времени заведения ({{ s.timezone }}).
    </p>
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'

definePageMeta({ role: 'manager' })

const api = useAdminApi()
const s = ref<components['schemas']['SummaryOut']>()
const max = computed(() => Math.max(0, ...(s.value?.days.map((d) => d.revenue_minor) ?? [])))
const tiles = computed(() => s.value
  ? [
      { id: 'today-orders', label: 'Заказов сегодня', value: String(s.value.today_orders) },
      { id: 'today-revenue', label: 'Выручка сегодня', value: formatMoney(s.value.today_revenue_minor, s.value.currency) },
      { id: 'today-average', label: 'Средний чек', value: formatMoney(s.value.today_average_minor, s.value.currency) },
      { id: 'pending-now', label: 'Ждут подтверждения', value: String(s.value.pending_now) },
    ]
  : [])

onMounted(async () => {
  s.value = await api.get('/v1/admin/analytics/summary', { query: { days: 7 } })
})
</script>

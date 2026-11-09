<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">
        Заказы
      </h1>
      <UTabs
        v-model="tab"
        :items="tabs"
        :content="false"
        size="md"
      />
    </div>

    <p v-if="feed.loaded.value && !feed.orders.value.length" class="text-muted py-10 text-center">
      {{ tab === 'new' ? 'Новых заказов нет — мы позвоним, когда появятся' : 'Пусто' }}
    </p>

    <div class="grid gap-3">
      <NuxtLink
        v-for="o in feed.orders.value"
        :key="o.id"
        :to="`/orders/${o.id}`"
        class="block rounded-lg border border-default p-4 hover:bg-elevated/50 transition"
        data-testid="order-row"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-3">
            <span class="text-lg font-semibold">№{{ o.number }}</span>
            <OrderStatusBadge :status="o.status" />
            <UBadge
              v-if="o.channel === 'telegram'"
              color="info"
              variant="outline"
              label="Telegram"
            />
          </div>
          <span class="font-semibold tracking-tight">{{ formatMoney(o.total_minor, o.currency) }}</span>
        </div>
        <div class="mt-1 text-sm text-muted flex flex-wrap gap-x-4">
          <span>{{ time(o.created_at) }}</span>
          <span>{{ o.fulfillment === 'delivery' ? 'Доставка' : 'Самовывоз' }}</span>
          <span v-if="o.requested_at">ко времени {{ time(o.requested_at) }}</span>
          <span>{{ o.customer_name }}</span>
          <span>{{ o.items.reduce((n, i) => n + i.quantity, 0) }} поз.</span>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrderStatus } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'
import { ACTIVE, DONE, useOrderFeed } from '~/composables/useOrderFeed'

definePageMeta({ role: 'operator' })

const tab = ref<'new' | 'active' | 'done'>('new')
const statuses = computed<OrderStatus[]>(() => tab.value === 'new' ? ['pending'] : tab.value === 'active' ? ACTIVE : DONE)
const feed = useOrderFeed(statuses)

const tabs = computed(() => [
  { label: feed.pendingCount.value ? `Новые · ${feed.pendingCount.value}` : 'Новые', value: 'new' },
  { label: 'В работе', value: 'active' },
  { label: 'Завершённые', value: 'done' },
])

function time(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
}
</script>

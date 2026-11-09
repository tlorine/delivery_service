<template>
  <div v-if="order" class="flex flex-col gap-5 max-w-3xl">
    <div class="flex flex-wrap items-center gap-3">
      <UButton
        to="/orders"
        icon="lucide:arrow-left"
        variant="ghost"
        color="neutral"
        aria-label="К заказам"
      />
      <h1 class="text-2xl font-semibold">
        Заказ №{{ order.number }}
      </h1>
      <OrderStatusBadge :status="order.status" data-testid="admin-order-status" />
      <UBadge
        v-if="order.channel === 'telegram'"
        color="info"
        variant="outline"
        label="Telegram"
      />
    </div>

    <div v-if="order.next_statuses.length" class="flex flex-wrap gap-2">
      <UButton
        v-for="s in order.next_statuses"
        :key="s"
        :label="ACTION_LABEL[s]"
        :color="s === 'cancelled' || s === 'rejected' ? 'error' : 'primary'"
        :variant="s === 'cancelled' || s === 'rejected' ? 'outline' : 'solid'"
        size="lg"
        :loading="busy === s"
        @click="act(s)"
      />
    </div>

    <UCard>
      <div class="grid sm:grid-cols-2 gap-4 text-sm">
        <div>
          <p class="text-muted">
            Покупатель
          </p>
          <p class="font-medium">
            {{ order.customer_name }}
          </p>
          <a :href="`tel:${order.customer_phone}`" class="text-primary font-medium">{{ order.customer_phone }}</a>
        </div>
        <div>
          <p class="text-muted">
            {{ order.fulfillment === 'delivery' ? 'Доставка' : 'Самовывоз' }}
          </p>
          <template v-if="order.address">
            <p class="font-medium">
              {{ order.address.street }}
            </p>
            <p>{{ [order.address.flat && `кв. ${order.address.flat}`, order.address.entrance && `подъезд ${order.address.entrance}`, order.address.floor && `этаж ${order.address.floor}`, order.address.intercom && `домофон ${order.address.intercom}`].filter(Boolean).join(', ') }}</p>
            <p v-if="order.address.comment" class="text-muted">
              {{ order.address.comment }}
            </p>
          </template>
        </div>
        <div>
          <p class="text-muted">
            Время
          </p>
          <p>Создан {{ time(order.created_at) }}</p>
          <p v-if="order.requested_at" class="font-medium">
            Ко времени {{ time(order.requested_at) }}
          </p>
          <p v-else-if="order.promised_at">
            Ориентир {{ time(order.promised_at) }}
          </p>
        </div>
        <div>
          <p class="text-muted">
            Оплата
          </p>
          <p>{{ PAYMENT_LABEL[order.payment_method] }}</p>
          <p v-if="order.change_from_minor">
            Сдача с {{ formatMoney(order.change_from_minor, order.currency) }}
          </p>
        </div>
      </div>
      <p v-if="order.comment" class="mt-4 rounded-md bg-warning/10 p-3 text-sm">
        💬 {{ order.comment }}
      </p>
    </UCard>

    <UCard>
      <div class="flex flex-col divide-y divide-default">
        <div
          v-for="item in order.items"
          :key="item.id"
          class="py-2 flex justify-between gap-3"
        >
          <div>
            <p class="font-medium">
              {{ item.product_name }} <span v-if="item.variant_name !== item.product_name" class="text-muted">· {{ item.variant_name }}</span>
            </p>
            <p
              v-for="m in item.modifiers"
              :key="m.modifier_id"
              class="text-sm text-muted"
            >
              + {{ m.name }}<span v-if="m.quantity > 1"> ×{{ m.quantity }}</span>
            </p>
          </div>
          <div class="text-right shrink-0">
            <p>×{{ item.quantity }}</p>
            <p class="tracking-tight">
              {{ formatMoney(item.line_total_minor, order.currency) }}
            </p>
          </div>
        </div>
        <div v-if="order.delivery_fee_minor" class="py-2 flex justify-between">
          <span>Доставка</span><span>{{ formatMoney(order.delivery_fee_minor, order.currency) }}</span>
        </div>
        <div class="py-2 flex justify-between font-semibold text-lg">
          <span>Итого</span><span>{{ formatMoney(order.total_minor, order.currency) }}</span>
        </div>
      </div>
    </UCard>

    <UCard>
      <p class="text-muted text-sm mb-2">
        История
      </p>
      <ul class="text-sm flex flex-col gap-1">
        <li v-for="(h, i) in order.history" :key="i">
          {{ time(h.created_at) }} — {{ STATUS_LABEL[h.to_status] }}
          <span class="text-muted">({{ h.actor_type === 'customer' ? 'покупатель' : h.actor_type === 'staff' ? 'сотрудник' : 'система' }})</span>
          <span v-if="h.reason">: {{ h.reason }}</span>
        </li>
      </ul>
    </UCard>

    <UModal v-model:open="reasonOpen" :title="pending === 'rejected' ? 'Отклонить заказ' : 'Отменить заказ'">
      <template #body>
        <form class="flex flex-col gap-3" @submit.prevent="confirmReason">
          <UFormField label="Причина (увидит покупатель в истории)" required>
            <UTextarea
              v-model="reason"
              autofocus
              class="w-full"
              :rows="3"
              placeholder="Например: закончились продукты"
            />
          </UFormField>
          <UButton
            type="submit"
            color="error"
            :disabled="!reason.trim()"
            label="Подтвердить"
            block
          />
        </form>
      </template>
    </UModal>
  </div>
  <div v-else-if="notFound" class="text-muted py-10 text-center">
    Заказ не найден
  </div>
</template>

<script setup lang="ts">
import type { AdminOrder, OrderStatus } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'

definePageMeta({ role: 'operator' })

const route = useRoute()
const api = useAdminApi()
const { run } = useAdminAction()

const order = ref<AdminOrder>()
const notFound = ref(false)
const busy = ref<OrderStatus | null>(null)
const reasonOpen = ref(false)
const reason = ref('')
const pending = ref<OrderStatus | null>(null)

async function load() {
  try {
    order.value = await api.get('/v1/admin/orders/{order_id}', { path: { order_id: String(route.params.id) } })
  } catch {
    notFound.value = true
  }
}

async function transition(to: OrderStatus, why?: string) {
  busy.value = to
  const updated = await run(() => api.post('/v1/admin/orders/{order_id}/transitions', {
    path: { order_id: String(route.params.id) },
    body: { to_status: to, reason: why ?? null },
  }), STATUS_LABEL[to])
  busy.value = null
  if (updated) {
    order.value = updated
  } else {
    await load() // someone else may have changed it (e.g. the customer cancelled)
  }
}

function act(to: OrderStatus) {
  if (to === 'cancelled' || to === 'rejected') {
    pending.value = to
    reason.value = ''
    reasonOpen.value = true
    return
  }
  transition(to)
}

async function confirmReason() {
  reasonOpen.value = false
  if (pending.value) {
    await transition(pending.value, reason.value.trim())
  }
}

function time(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'long' })
}

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  load()
  timer = setInterval(load, 15_000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

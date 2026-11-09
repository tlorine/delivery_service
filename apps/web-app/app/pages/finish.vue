<template>
  <Confetti />

  <h1 class="pt-8 mb-4 md:mb-8 text-3xl md:text-4xl font-medium text-center motion-preset-pop">
    {{ $dict('web-app.finish.title') }}
  </h1>

  <ClientOnly>
    <div v-if="loading" class="flex flex-col items-center justify-center min-h-64">
      <UIcon name="i-lucide-shopping-basket" class="mx-auto my-auto size-24 text-dimmed/25 self-center motion-preset-pulse-sm" />
    </div>

    <div v-else-if="!order" class="text-center pb-16">
      <p class="mb-6 text-muted">
        {{ $dict('web-app.order.not-found') }}
      </p>
      <UButton
        to="/"
        variant="solid"
        color="secondary"
        size="xl"
        :label="$dict('common.to-home')"
      />
    </div>

    <div v-else class="mx-auto flex max-w-lg flex-col gap-6 rounded-[24px] bg-default p-4 ring-1 ring-default md:p-6">
      <div class="text-center">
        <p class="text-muted">
          {{ $dict('web-app.order.number') }}{{ order.number }}
        </p>
        <p class="text-2xl font-semibold" data-testid="order-status">
          {{ statusLabel }}
        </p>
        <p v-if="order.status === 'pending'" class="mt-2 text-muted">
          {{ $dict('web-app.finish.success-message') }} {{ $dict('web-app.finish.expect-call') }}
        </p>
        <p v-if="promisedAt && !isFinal" class="mt-1 text-sm text-muted">
          {{ $dict('web-app.order.promised-at') }}: {{ promisedAt }}
        </p>
      </div>

      <ol
        v-if="!failed"
        class="grid gap-1"
        :style="{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }"
        data-testid="order-steps"
      >
        <li
          v-for="(step, i) in steps"
          :key="step"
          class="flex flex-col gap-1.5"
        >
          <span class="h-1.5 rounded-full" :class="i <= currentStep ? 'bg-primary' : 'bg-accented'" />
          <span class="text-[11px]/3 sm:text-xs" :class="i === currentStep ? 'font-semibold text-highlighted' : 'text-muted'">{{ $dict(`web-app.status.${step}` as DictionaryKey) }}</span>
        </li>
      </ol>

      <div>
        <h3 class="mb-2 text-lg font-medium text-muted">
          {{ order.fulfillment === 'pickup' ? $dict('web-app.cart.pickup') : $dict('web-app.cart.delivery') }}
        </h3>
        <p>{{ $dict('web-app.checkout.your-name') }}: <span class="font-medium">{{ order.customer_name }}</span></p>
        <p class="mb-2">
          {{ $dict('web-app.checkout.your-phone') }}: <span class="font-medium">{{ order.customer_phone }}</span>
        </p>
        <p>
          {{ $dict('web-app.checkout.address.title') }}:
          <span class="font-medium">{{ addressLine }}</span>
        </p>
        <p>
          {{ $dict('web-app.checkout.payment-title') }}:
          <span class="font-medium">{{ optionsStore.getLocaleValue(paymentMethodView(order.payment_method).title) }}</span>
        </p>
        <p v-if="order.change_from_minor">
          {{ $dict('web-app.checkout.change-label') }}:
          <span class="font-medium">{{ formatMoney(order.change_from_minor, order.currency) }}</span>
        </p>
        <p v-if="order.comment">
          {{ $dict('web-app.checkout.order-note') }}: <span class="font-medium">{{ order.comment }}</span>
        </p>
      </div>

      <div class="flex flex-col gap-3">
        <h3 class="text-lg font-medium text-muted">
          {{ $dict('web-app.finish.ordered-title') }}
        </h3>
        <div
          v-for="item in order.items"
          :key="item.id"
          class="flex flex-row justify-between gap-3"
        >
          <div>
            <p class="font-medium">
              {{ item.product_name }}<span v-if="item.variant_name !== item.product_name" class="text-muted"> · {{ item.variant_name }}</span>
            </p>
            <p
              v-for="m in item.modifiers"
              :key="m.modifier_id"
              class="text-sm text-muted"
            >
              + {{ m.name }}<span v-if="m.quantity > 1"> ×{{ m.quantity }}</span>
            </p>
          </div>
          <div class="shrink-0 text-right">
            <p>×{{ item.quantity }}</p>
            <p class="tracking-tight">
              {{ formatMoney(item.line_total_minor, order.currency) }}
            </p>
          </div>
        </div>
      </div>

      <div class="flex flex-col gap-1">
        <div v-if="order.delivery_fee_minor" class="flex flex-row justify-between">
          <div>{{ $dict('web-app.order.delivery-fee') }}</div>
          <div class="tracking-tight">
            {{ formatMoney(order.delivery_fee_minor, order.currency) }}
          </div>
        </div>
        <div class="flex flex-row justify-between text-lg font-medium">
          <div>{{ $dict('web-app.checkout.grand-total') }}</div>
          <div class="tracking-tight" data-testid="order-total">
            {{ formatMoney(order.total_minor, order.currency) }}
          </div>
        </div>
      </div>

      <UButton
        v-if="order.can_cancel"
        variant="outline"
        color="error"
        size="lg"
        block
        :loading="cancelling"
        :label="$dict('web-app.order.cancel')"
        @click="cancel()"
      />
      <UButton
        v-if="telegram.isActive.value"
        variant="solid"
        color="secondary"
        size="xl"
        block
        :label="$dict('common.close')"
        @click="telegram.close()"
      />
      <UButton
        v-else
        to="/"
        variant="solid"
        color="secondary"
        size="xl"
        block
        :label="$dict('common.to-home')"
      />
    </div>
  </ClientOnly>
</template>

<script setup lang="ts">
import type { Order } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'

definePageMeta({
  layout: 'finish',
})

const { dict } = useDictionary()
const route = useRoute()
const orderStore = useOrderStore()
const optionsStore = useOptionsStore()
const channelStore = useChannelStore()
const telegram = useTelegram()

const order = ref<Order>()
const loading = ref(true)
const cancelling = ref(false)

const orderId = String(route.query.id ?? '')
const failed = computed(() => ['cancelled', 'rejected'].includes(order.value?.status ?? ''))
const steps = computed(() => order.value?.fulfillment === 'delivery'
  ? ['pending', 'confirmed', 'preparing', 'delivering', 'completed']
  : ['pending', 'confirmed', 'preparing', 'ready', 'completed'])
// "ready" of a delivery order shows as still preparing; the courier step comes next.
const currentStep = computed(() => {
  const status = order.value?.status === 'ready' && order.value.fulfillment === 'delivery' ? 'preparing' : order.value?.status
  return Math.max(0, steps.value.indexOf(status ?? 'pending'))
})
const isFinal = computed(() => ['completed', 'cancelled', 'rejected'].includes(order.value?.status ?? ''))
const statusLabel = computed(() => order.value ? dict(`web-app.status.${order.value.status}` as DictionaryKey) : '')

const branch = computed(() => channelStore.branches.find((b) => b.id === order.value?.branch_id))
const promisedAt = computed(() => order.value?.promised_at && branch.value
  ? localParts(order.value.promised_at, branch.value.timezone).time
  : undefined)

const addressLine = computed(() => {
  const o = order.value
  if (!o) {
    return ''
  }
  if (o.fulfillment === 'pickup' || !o.address) {
    return branch.value?.address ?? ''
  }
  const a = o.address
  const parts = [a.street, a.flat && `${dict('web-app.checkout.address.flat')} ${a.flat}`, a.entrance && `${dict('web-app.checkout.address.entrance')} ${a.entrance}`, a.floor && `${dict('web-app.checkout.address.floor')} ${a.floor}`, a.intercom && `${dict('web-app.checkout.address.intercom')} ${a.intercom}`]
  return parts.filter(Boolean).join(', ')
})

async function load() {
  order.value = await orderStore.get(orderId)
  loading.value = false
}

async function cancel() {
  cancelling.value = true
  order.value = (await orderStore.cancel(orderId)) ?? order.value
  cancelling.value = false
}

const { pop } = useConfetti()
let timer: ReturnType<typeof setInterval> | undefined

onMounted(async () => {
  await load()
  if (order.value?.status === 'pending') {
    pop()
  }
  // The cafe moves the order along; refresh until it is final.
  timer = setInterval(() => {
    if (!isFinal.value) {
      load()
    }
  }, 15_000)
})

onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div v-if="branch" class="flex flex-col gap-5 max-w-3xl">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">
        Расписание и филиал
      </h1>
      <USelect
        v-if="b.items.value.length > 1"
        :model-value="b.selectedId.value ?? undefined"
        :items="b.items.value"
        aria-label="Филиал"
        class="w-56"
        @update:model-value="(v) => b.selectedId.value = v"
      />
    </div>

    <UCard>
      <p class="font-medium mb-3">
        Часы работы <span class="text-sm text-muted font-normal">({{ branch.timezone }})</span>
      </p>
      <div
        v-for="(day, d) in week"
        :key="d"
        class="flex flex-wrap items-center gap-2 py-1.5 border-b border-default last:border-0"
      >
        <span class="w-8 font-medium">{{ WEEKDAYS[d] }}</span>
        <template v-if="day.length">
          <div
            v-for="(iv, i) in day"
            :key="i"
            class="flex items-center gap-1"
          >
            <UInput
              v-model="iv.opens"
              type="time"
              class="w-28"
              :aria-label="`${WEEKDAYS[d]} открытие`"
            />
            <span>—</span>
            <UInput
              v-model="iv.closes"
              type="time"
              class="w-28"
              :aria-label="`${WEEKDAYS[d]} закрытие`"
            />
            <UButton
              icon="lucide:x"
              size="xs"
              variant="ghost"
              color="neutral"
              aria-label="Убрать интервал"
              @click="day.splice(i, 1)"
            />
          </div>
        </template>
        <span v-else class="text-muted">выходной</span>
        <UButton
          icon="lucide:plus"
          size="xs"
          variant="ghost"
          aria-label="Добавить интервал"
          @click="day.push({ opens: '10:00', closes: '22:00' })"
        />
        <UButton
          v-if="d > 0"
          size="xs"
          variant="link"
          color="neutral"
          label="как вчера"
          @click="week[d] = week[d - 1]!.map((x) => ({ ...x }))"
        />
      </div>
      <p class="text-xs text-muted mt-2">
        Если закрытие раньше открытия, интервал заканчивается на следующий день (ночной режим). 00:00—00:00 — круглосуточно.
      </p>
      <UButton
        class="mt-3"
        label="Сохранить часы"
        :loading="saving"
        data-testid="save-hours"
        @click="saveHours()"
      />
    </UCard>

    <UCard>
      <p class="font-medium mb-3">
        Приём заказов
      </p>
      <div class="flex flex-col gap-3">
        <USwitch v-model="form.is_active" label="Филиал принимает заказы" />
        <USwitch v-model="form.delivery_enabled" label="Доставка" />
        <USwitch v-model="form.pickup_enabled" label="Самовывоз" />
        <div class="grid grid-cols-2 gap-3">
          <UFormField label="Приготовление, мин">
            <UInputNumber
              v-model="form.prep_time_min"
              :min="0"
              :max="600"
            />
          </UFormField>
          <UFormField label="Доставка в пути, мин">
            <UInputNumber
              v-model="form.delivery_time_min"
              :min="0"
              :max="600"
            />
          </UFormField>
        </div>
        <UFormField label="Способы оплаты">
          <UCheckboxGroup v-model="form.payment_methods" :items="paymentItems" />
        </UFormField>
        <UFormField label="Телефон филиала">
          <UInput v-model="form.phone" class="w-full" />
        </UFormField>
        <UButton
          label="Сохранить"
          :loading="saving"
          @click="saveBranch()"
        />
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ role: 'manager' })

const api = useAdminApi()
const { ok } = useAdminAction()
const b = useBranches()
const branch = computed(() => b.selected.value)
const saving = ref(false)
const week = ref<{ opens: string, closes: string }[][]>([])
const form = reactive({ is_active: true, delivery_enabled: true, pickup_enabled: true, prep_time_min: 20, delivery_time_min: 40, payment_methods: [] as string[], phone: '' })
const paymentItems = [{ label: 'Наличными', value: 'cash' }, { label: 'Картой при получении', value: 'card_on_delivery' }]

watch(branch, (br) => {
  if (!br) {
    return
  }
  week.value = Array.from({ length: 7 }, (_, d) => br.hours.filter((h) => h.weekday === d).map((h) => ({ opens: h.opens_at.slice(0, 5), closes: h.closes_at.slice(0, 5) })))
  Object.assign(form, { is_active: br.is_active, delivery_enabled: br.delivery_enabled, pickup_enabled: br.pickup_enabled, prep_time_min: br.prep_time_min, delivery_time_min: br.delivery_time_min, payment_methods: [...br.payment_methods], phone: br.phone ?? '' })
}, { immediate: true })

async function saveHours() {
  const id = branch.value?.id
  if (!id) {
    return
  }
  saving.value = true
  const intervals = week.value.flatMap((day, weekday) => day.map((iv) => ({ weekday, opens_at: iv.opens, closes_at: iv.closes })))
  if (await ok(() => api.request('put', '/v1/admin/branches/{branch_id}/hours', { path: { branch_id: id }, body: { intervals } }), 'Часы сохранены')) {
    await b.load()
  }
  saving.value = false
}

async function saveBranch() {
  const id = branch.value?.id
  if (!id) {
    return
  }
  saving.value = true
  if (await ok(() => api.patch('/v1/admin/branches/{branch_id}', { path: { branch_id: id }, body: { ...form, phone: form.phone || null } }), 'Сохранено')) {
    await b.load()
  }
  saving.value = false
}

onMounted(() => b.load())
</script>

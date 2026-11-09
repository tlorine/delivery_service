<template>
  <div class="flex flex-col gap-4 max-w-3xl">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">
        Зоны доставки
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
    <p class="text-sm text-muted">
      Стоимость доставки и минимальную сумму можно менять здесь. Границы зоны на карте настраивает поддержка платформы.
    </p>

    <UCard v-for="z in zones" :key="z.id">
      <div class="flex items-center justify-between gap-2 mb-3">
        <p class="font-medium">
          {{ z.name }}
        </p>
        <USwitch
          :model-value="z.is_active"
          label="Активна"
          @update:model-value="(on) => patch(z.id, { is_active: on })"
        />
      </div>
      <div class="grid sm:grid-cols-3 gap-3">
        <UFormField label="Доставка, ₽">
          <UInputNumber
            :model-value="minorToRubles(z.fee_minor)"
            :min="0"
            :step="10"
            :step-snapping="false"
            @update:model-value="(r) => patch(z.id, { fee_minor: rublesToMinor(r ?? 0) })"
          />
        </UFormField>
        <UFormField label="Минимальный заказ, ₽">
          <UInputNumber
            :model-value="minorToRubles(z.min_order_minor)"
            :min="0"
            :step="50"
            :step-snapping="false"
            @update:model-value="(r) => patch(z.id, { min_order_minor: rublesToMinor(r ?? 0) })"
          />
        </UFormField>
        <UFormField label="Бесплатно от, ₽">
          <UInputNumber
            :model-value="z.free_from_minor === null ? undefined : minorToRubles(z.free_from_minor)"
            :min="0"
            :step="100"
            :step-snapping="false"
            placeholder="не бесплатно"
            @update:model-value="(r) => patch(z.id, { free_from_minor: r == null ? null : rublesToMinor(r) })"
          />
        </UFormField>
      </div>
    </UCard>
    <p v-if="loaded && !zones.length" class="text-muted">
      Зон пока нет — доставка недоступна. Обратитесь в поддержку, чтобы задать границы.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'

definePageMeta({ role: 'manager' })

type Zone = components['schemas']['ZoneOut']
const api = useAdminApi()
const { ok } = useAdminAction()
const b = useBranches()
const zones = ref<Zone[]>([])
const loaded = ref(false)

async function load() {
  if (b.selected.value) {
    zones.value = await api.get('/v1/admin/branches/{branch_id}/delivery-zones', { path: { branch_id: b.selected.value.id } })
    loaded.value = true
  }
}

async function patch(id: string, body: components['schemas']['ZonePatch']) {
  if (await ok(() => api.patch('/v1/admin/delivery-zones/{zone_id}', { path: { zone_id: id }, body }), 'Сохранено')) {
    await load()
  }
}

watch(() => b.selected.value?.id, load)
onMounted(async () => {
  await b.load()
  await load()
})
</script>

<template>
  <div class="flex flex-col gap-6" data-testid="modifiers">
    <fieldset
      v-for="group in groups"
      :key="group.id"
      class="flex flex-col"
    >
      <legend class="mb-2 flex w-full items-baseline justify-between gap-2">
        <span class="text-[17px] font-semibold text-highlighted">{{ group.name }}</span>
        <span class="shrink-0 text-[13px]" :class="group.min_selected > 0 && groupCount(group) < group.min_selected ? 'font-semibold text-primary' : 'text-muted'">
          <template v-if="group.min_selected > 0">{{ $dict('web-app.product.required') }}</template>
          <template v-else-if="group.max_selected > 1">{{ $dict('web-app.product.up-to') }} {{ group.max_selected }}</template>
        </span>
      </legend>

      <div class="overflow-hidden rounded-[16px] bg-default ring-1 ring-default divide-y divide-default">
        <div
          v-for="m in group.modifiers"
          :key="m.id"
          class="flex min-h-13 items-center gap-3 px-4 py-2.5 transition"
          :class="[
            !m.available || (!(model[m.id]) && groupCount(group) >= group.max_selected && group.max_selected > 1) ? 'opacity-45' : 'cursor-pointer hover:bg-elevated/60',
          ]"
          @click="toggle(group, m)"
        >
          <span
            aria-hidden="true"
            class="grid size-5 shrink-0 place-items-center border-2 transition"
            :class="[
              group.max_selected === 1 ? 'rounded-full' : 'rounded-md',
              (model[m.id] ?? 0) > 0 ? 'border-primary bg-primary text-[var(--brand-on-accent)]' : 'border-accented',
            ]"
          >
            <UIcon
              v-if="(model[m.id] ?? 0) > 0 && group.max_selected > 1"
              name="lucide:check"
              class="size-3.5"
            />
            <span v-else-if="(model[m.id] ?? 0) > 0" class="size-2 rounded-full bg-[var(--brand-on-accent)]" />
          </span>
          <input
            :type="group.max_selected === 1 ? 'radio' : 'checkbox'"
            class="sr-only"
            :name="group.id"
            :checked="(model[m.id] ?? 0) > 0"
            :disabled="!m.available"
            :aria-label="m.name"
            @click.stop
            @change="toggle(group, m)"
          >
          <span class="flex-1 text-[15px] text-toned">{{ m.name }}<span v-if="!m.available" class="text-muted"> · {{ $dict('web-app.product.unavailable') }}</span></span>

          <div
            v-if="m.max_quantity > 1 && (model[m.id] ?? 0) > 0"
            class="flex items-center gap-1"
            @click.stop
          >
            <button
              type="button"
              class="grid size-8 place-items-center rounded-lg bg-elevated"
              :aria-label="$dict('web-app.cart.decrease')"
              @click="set(group, m.id, (model[m.id] ?? 0) - 1)"
            >
              <UIcon name="lucide:minus" class="size-3.5" />
            </button>
            <span class="tabular w-4 text-center text-sm">{{ model[m.id] }}</span>
            <button
              type="button"
              class="grid size-8 place-items-center rounded-lg bg-elevated disabled:opacity-40"
              :disabled="(model[m.id] ?? 0) >= m.max_quantity || groupCount(group) >= group.max_selected"
              :aria-label="$dict('web-app.cart.increase')"
              @click="set(group, m.id, (model[m.id] ?? 0) + 1)"
            >
              <UIcon name="lucide:plus" class="size-3.5" />
            </button>
          </div>
          <span v-if="m.price_minor" class="tabular shrink-0 text-[14px] text-muted">+{{ formatMoney(m.price_minor, currency) }}</span>
        </div>
      </div>
    </fieldset>
  </div>
</template>

<script setup lang="ts">
import type { ModifierGroup } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'

const { groups, currency = 'RUB' } = defineProps<{
  groups: ModifierGroup[]
  currency?: string
}>()

/** modifierId -> quantity per one item */
const model = defineModel<Record<string, number>>({ required: true })

function groupCount(group: ModifierGroup): number {
  return group.modifiers.reduce((sum, m) => sum + (model.value[m.id] ?? 0), 0)
}

function toggle(group: ModifierGroup, m: ModifierGroup['modifiers'][number]) {
  if (!m.available) {
    return
  }
  const selected = (model.value[m.id] ?? 0) > 0
  if (!selected && group.max_selected > 1 && groupCount(group) >= group.max_selected) {
    return
  }
  // Tapping the chosen option of a required single-choice group keeps it chosen (radio behaviour).
  if (selected && group.max_selected === 1 && group.min_selected > 0) {
    return
  }
  set(group, m.id, selected ? 0 : 1)
}

function set(group: ModifierGroup, modifierId: string, quantity: number) {
  const next = { ...model.value }
  // Single-choice group: picking one replaces the other (radio behaviour).
  if (group.max_selected === 1 && quantity > 0) {
    for (const m of group.modifiers) {
      delete next[m.id]
    }
  }
  if (quantity > 0) {
    next[modifierId] = quantity
  } else {
    delete next[modifierId]
  }
  model.value = next
}
</script>

<template>
  <div class="flex flex-col gap-4 max-w-3xl">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">
        Стоп-лист
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
      Выключенные позиции нельзя заказать в этом филиале, пока вы их не вернёте.
    </p>
    <UInput
      v-model="search"
      icon="lucide:search"
      placeholder="Найти позицию"
      class="w-full"
    />

    <UCard v-for="p in products" :key="p.id">
      <p class="font-medium mb-2">
        {{ p.name }} <span v-if="!p.is_active" class="text-muted text-sm">(скрыт в меню)</span>
      </p>
      <div class="flex flex-col gap-2">
        <USwitch
          v-for="v in p.variants"
          :key="v.id"
          :model-value="!stopped.variants.has(v.id)"
          :label="p.variants.length > 1 ? v.name : 'В наличии'"
          :data-testid="`stop-${p.slug}-${v.name}`"
          @update:model-value="(on) => toggle('variants', v.id, !on)"
        />
      </div>
    </UCard>

    <h2 v-if="groups.length" class="text-lg font-semibold mt-2">
      Добавки
    </h2>
    <UCard v-for="g in groups" :key="g.id">
      <p class="font-medium mb-2">
        {{ g.name }}
      </p>
      <div class="flex flex-col gap-2">
        <USwitch
          v-for="m in g.modifiers"
          :key="m.id"
          :model-value="!stopped.modifiers.has(m.id)"
          :label="m.name"
          @update:model-value="(on) => toggle('modifiers', m.id, !on)"
        />
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'

definePageMeta({ role: 'operator' })

type Catalog = components['schemas']['CatalogAdminOut']
const api = useAdminApi()
const { run } = useAdminAction()
const b = useBranches()

const catalog = ref<Catalog>()
const search = ref('')
const stopped = reactive({ variants: new Set<string>(), modifiers: new Set<string>() })

const q = computed(() => search.value.trim().toLowerCase())
const products = computed(() => (catalog.value?.products ?? []).filter((p) => !q.value || p.name.toLowerCase().includes(q.value)))
const groups = computed(() => (catalog.value?.modifier_groups ?? []).filter((g) => g.modifiers.length && (!q.value || g.modifiers.some((m) => m.name.toLowerCase().includes(q.value)))))

function apply(list: { variant_ids: string[], modifier_ids: string[] }) {
  stopped.variants = new Set(list.variant_ids)
  stopped.modifiers = new Set(list.modifier_ids)
}

async function loadStoplist() {
  if (b.selected.value) {
    apply(await api.get('/v1/admin/branches/{branch_id}/stoplist', { path: { branch_id: b.selected.value.id } }))
  }
}

async function toggle(kind: 'variants' | 'modifiers', id: string, stop: boolean) {
  const branch = b.selected.value
  if (!branch) {
    return
  }
  const result = kind === 'variants'
    ? await run(() => api.request('put', '/v1/admin/branches/{branch_id}/stoplist/variants/{variant_id}', { path: { branch_id: branch.id, variant_id: id }, body: { stopped: stop } }))
    : await run(() => api.request('put', '/v1/admin/branches/{branch_id}/stoplist/modifiers/{modifier_id}', { path: { branch_id: branch.id, modifier_id: id }, body: { stopped: stop } }))
  if (result) {
    apply(result)
  }
}

watch(() => b.selected.value?.id, loadStoplist)
onMounted(async () => {
  await b.load()
  catalog.value = await api.get('/v1/admin/catalog')
  await loadStoplist()
})
</script>

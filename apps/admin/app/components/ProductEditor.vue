<template>
  <UModal
    v-model:open="open"
    :title="draft.id ? 'Товар' : 'Новый товар'"
    :ui="{ content: 'max-w-2xl' }"
  >
    <template #body>
      <form class="flex flex-col gap-4" @submit.prevent="save">
        <UFormField label="Название" required>
          <UInput
            v-model="draft.name"
            class="w-full"
            data-testid="product-name"
          />
        </UFormField>
        <UFormField label="Категория" required>
          <USelect
            v-model="draft.category_id"
            :items="categoryItems"
            class="w-full"
            aria-label="Категория"
          />
        </UFormField>
        <UFormField label="Описание">
          <UTextarea
            v-model="draft.description"
            :rows="2"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Фото (ссылка https://)">
          <UInput
            v-model="draft.image_url"
            placeholder="https://…"
            class="w-full"
          />
        </UFormField>

        <div>
          <p class="text-sm font-medium mb-2">
            Варианты и цены
          </p>
          <div
            v-for="(v, i) in draft.variants"
            :key="v.key"
            class="grid grid-cols-12 gap-2 mb-2 items-end"
          >
            <UFormField label="Вариант" class="col-span-5">
              <UInput
                v-model="v.name"
                class="w-full"
                placeholder="Стандарт"
              />
            </UFormField>
            <UFormField label="Цена, ₽" class="col-span-3">
              <UInputNumber
                v-model="v.price"
                :min="0"
                :step="10"
                :step-snapping="false"
                :format-options="{ maximumFractionDigits: 2 }"
                class="w-full"
                :data-testid="`variant-price-${i}`"
              />
            </UFormField>
            <UFormField label="Вес/объём" class="col-span-3">
              <UInput
                v-model.number="v.weight_value"
                type="number"
                min="0"
                class="w-full"
              />
            </UFormField>
            <UButton
              class="col-span-1"
              icon="lucide:trash-2"
              variant="ghost"
              color="error"
              aria-label="Удалить вариант"
              :disabled="draft.variants.length === 1"
              @click="draft.variants.splice(i, 1)"
            />
          </div>
          <UButton
            icon="lucide:plus"
            variant="soft"
            size="sm"
            label="Добавить вариант"
            @click="addVariant()"
          />
        </div>

        <UFormField label="Группы добавок">
          <USelectMenu
            v-model="draft.group_ids"
            :items="groupItems"
            value-key="value"
            multiple
            class="w-full"
            placeholder="Без добавок"
          />
        </UFormField>

        <USwitch v-model="draft.is_active" label="Показывать в меню" />

        <div class="flex justify-between gap-2">
          <UButton
            v-if="draft.id"
            color="error"
            variant="ghost"
            label="Удалить товар"
            @click="remove()"
          />
          <UButton
            type="submit"
            :loading="saving"
            label="Сохранить"
            class="ml-auto"
            data-testid="product-save"
          />
        </div>
      </form>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'

type Catalog = components['schemas']['CatalogAdminOut']
type Product = components['schemas']['ProductAdminOut']

interface DraftVariant { key: string, id?: string, name: string, price: number, weight_value: number | null, weight_unit: string | null, original?: components['schemas']['VariantAdminOut'] }

const props = defineProps<{ catalog: Catalog }>()
const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const api = useAdminApi()
const { run, ok } = useAdminAction()
const saving = ref(false)
let seq = 0

const blank = () => ({ id: undefined as string | undefined, name: '', category_id: props.catalog.categories[0]?.id ?? '', description: '', image_url: '', is_active: true, group_ids: [] as string[], variants: [] as DraftVariant[] })
const draft = reactive(blank())
let original: Product | undefined

const categoryItems = computed(() => props.catalog.categories.map((c) => ({ label: c.name, value: c.id })))
const groupItems = computed(() => props.catalog.modifier_groups.map((g) => ({ label: g.name, value: g.id })))

function addVariant(v?: components['schemas']['VariantAdminOut']) {
  draft.variants.push({ key: String(seq++), id: v?.id, name: v?.name ?? 'Стандарт', price: v ? minorToRubles(v.price_minor) : 0, weight_value: v?.weight_value ?? null, weight_unit: v?.weight_unit ?? 'g', original: v })
}

function edit(product?: Product) {
  Object.assign(draft, blank())
  original = product
  if (product) {
    Object.assign(draft, { id: product.id, name: product.name, category_id: product.category_id, description: product.description ?? '', image_url: product.image_url ?? '', is_active: product.is_active, group_ids: [...product.modifier_group_ids] })
    product.variants.forEach((v) => addVariant(v))
  } else {
    addVariant()
  }
  open.value = true
}
defineExpose({ edit })

const variantBody = (v: DraftVariant) => ({ name: v.name.trim() || 'Стандарт', price_minor: rublesToMinor(v.price), weight_value: v.weight_value || null, weight_unit: v.weight_value ? (v.weight_unit ?? 'g') : null })

async function save() {
  saving.value = true
  try {
    const fields = { name: draft.name.trim(), category_id: draft.category_id, description: draft.description.trim() || null, image_url: draft.image_url.trim() || null, is_active: draft.is_active }
    if (!draft.id) {
      const created = await run(() => api.post('/v1/admin/products', { body: { ...fields, variants: draft.variants.map(variantBody), modifier_group_ids: draft.group_ids } }), 'Товар добавлен')
      if (!created) {
        return
      }
    } else {
      const id = draft.id
      if (!await ok(() => api.patch('/v1/admin/products/{product_id}', { path: { product_id: id }, body: fields }))) {
        return
      }
      for (const v of draft.variants) {
        const body = variantBody(v)
        if (!v.id) {
          await run(() => api.post('/v1/admin/products/{product_id}/variants', { path: { product_id: id }, body }))
        } else if (v.original && (body.name !== v.original.name || body.price_minor !== v.original.price_minor || body.weight_value !== v.original.weight_value)) {
          await ok(() => api.patch('/v1/admin/variants/{variant_id}', { path: { variant_id: v.id! }, body }))
        }
      }
      for (const old of original?.variants ?? []) {
        if (!draft.variants.some((v) => v.id === old.id)) {
          await ok(() => api.delete('/v1/admin/variants/{variant_id}', { path: { variant_id: old.id } }))
        }
      }
      if (JSON.stringify(draft.group_ids) !== JSON.stringify(original?.modifier_group_ids)) {
        await ok(() => api.request('put', '/v1/admin/products/{product_id}/modifier-groups', { path: { product_id: id }, body: { group_ids: draft.group_ids } }))
      }
    }
    open.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}

async function remove() {
  const id = draft.id
  if (!id || !await useDialog().confirm('Удалить товар?', 'Если его уже заказывали, удалить не получится — скройте его.')) {
    return
  }
  if (await ok(() => api.delete('/v1/admin/products/{product_id}', { path: { product_id: id } }), 'Товар удалён')) {
    open.value = false
    emit('saved')
  }
}
</script>

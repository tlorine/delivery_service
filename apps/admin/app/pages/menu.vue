<template>
  <div class="flex flex-col gap-5 max-w-4xl">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">
        Меню
      </h1>
      <div class="flex gap-2">
        <UButton
          icon="lucide:folder-plus"
          variant="soft"
          label="Категория"
          @click="addCategory()"
        />
        <UButton
          icon="lucide:plus"
          label="Товар"
          data-testid="add-product"
          :disabled="!catalog?.categories.length"
          @click="editor?.edit()"
        />
      </div>
    </div>

    <template v-if="catalog">
      <section
        v-for="c in catalog.categories"
        :key="c.id"
        class="flex flex-col gap-2"
      >
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-semibold" :class="!c.is_active && 'text-muted line-through'">
            {{ c.name }}
          </h2>
          <UButton
            icon="lucide:pencil"
            size="xs"
            variant="ghost"
            color="neutral"
            aria-label="Переименовать"
            @click="renameCategory(c)"
          />
          <UButton
            :icon="c.is_active ? 'lucide:eye' : 'lucide:eye-off'"
            size="xs"
            variant="ghost"
            color="neutral"
            :aria-label="c.is_active ? 'Скрыть категорию' : 'Показать категорию'"
            @click="patchCategory(c.id, { is_active: !c.is_active })"
          />
          <UButton
            v-if="!productsOf(c.id).length"
            icon="lucide:trash-2"
            size="xs"
            variant="ghost"
            color="error"
            aria-label="Удалить категорию"
            @click="deleteCategory(c.id)"
          />
        </div>
        <div class="grid gap-2">
          <button
            v-for="p in productsOf(c.id)"
            :key="p.id"
            type="button"
            class="text-left rounded-lg border border-default p-3 hover:bg-elevated/50 flex justify-between gap-3"
            :data-testid="`product-${p.slug}`"
            @click="editor?.edit(p)"
          >
            <div>
              <p class="font-medium" :class="!p.is_active && 'text-muted'">
                {{ p.name }} <span v-if="!p.is_active" class="text-xs">(скрыт)</span>
              </p>
              <p class="text-sm text-muted">
                {{ p.modifier_group_ids.map(groupName).join(', ') || 'без добавок' }}
              </p>
            </div>
            <div class="text-right text-sm shrink-0">
              <p v-for="v in p.variants" :key="v.id">
                <span v-if="p.variants.length > 1" class="text-muted">{{ v.name }} </span>{{ formatMoney(v.price_minor) }}
              </p>
            </div>
          </button>
          <p v-if="!productsOf(c.id).length" class="text-sm text-muted">
            В категории пока нет товаров
          </p>
        </div>
      </section>

      <section class="flex flex-col gap-2 mt-4">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold">
            Группы добавок
          </h2>
          <UButton
            icon="lucide:plus"
            size="sm"
            variant="soft"
            label="Группа"
            @click="addGroup()"
          />
        </div>
        <UCard v-for="g in catalog.modifier_groups" :key="g.id">
          <div class="flex flex-wrap items-center gap-2 mb-2">
            <p class="font-medium">
              {{ g.name }}
            </p>
            <span class="text-sm text-muted">выбрать {{ g.min_selected ? `от ${g.min_selected} ` : '' }}до {{ g.max_selected }}</span>
            <UButton
              icon="lucide:sliders-horizontal"
              size="xs"
              variant="ghost"
              color="neutral"
              aria-label="Правила группы"
              @click="editGroup(g)"
            />
            <UButton
              icon="lucide:trash-2"
              size="xs"
              variant="ghost"
              color="error"
              aria-label="Удалить группу"
              @click="deleteGroup(g.id)"
            />
          </div>
          <div class="flex flex-col gap-1">
            <div
              v-for="m in g.modifiers"
              :key="m.id"
              class="flex items-center gap-2"
            >
              <span class="flex-1" :class="!m.is_active && 'text-muted line-through'">{{ m.name }}</span>
              <UInputNumber
                :model-value="minorToRubles(m.price_minor)"
                :min="0"
                :step="10"
                :step-snapping="false"
                class="w-28"
                :aria-label="`Цена ${m.name}, ₽`"
                @update:model-value="(rub) => patchModifier(m.id, { price_minor: rublesToMinor(rub ?? 0) })"
              />
              <USwitch
                :model-value="m.is_active"
                :aria-label="`${m.name} активна`"
                @update:model-value="(on) => patchModifier(m.id, { is_active: on })"
              />
            </div>
            <form class="flex gap-2 mt-1" @submit.prevent="addModifier(g.id)">
              <UInput
                v-model="newModifier[g.id]"
                placeholder="Новая добавка"
                size="sm"
                class="flex-1"
              />
              <UButton
                type="submit"
                size="sm"
                variant="soft"
                icon="lucide:plus"
                aria-label="Добавить добавку"
                :disabled="!newModifier[g.id]?.trim()"
              />
            </form>
          </div>
        </UCard>
      </section>
    </template>

    <ProductEditor
      v-if="catalog"
      ref="editor"
      :catalog="catalog"
      @saved="load()"
    />
    <GroupForm ref="groupForm" @saved="load()" />
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'
import { formatMoney } from '@delivery/api-client'

definePageMeta({ role: 'manager' })

type Catalog = components['schemas']['CatalogAdminOut']
const api = useAdminApi()
const { run, ok } = useAdminAction()
const dialog = useDialog()
const catalog = ref<Catalog>()
const editor = ref<{ edit: (p?: Catalog['products'][number]) => void }>()
const newModifier = reactive<Record<string, string>>({})

async function load() {
  catalog.value = await api.get('/v1/admin/catalog')
}

const productsOf = (categoryId: string) => catalog.value?.products.filter((p) => p.category_id === categoryId) ?? []
const groupName = (id: string) => catalog.value?.modifier_groups.find((g) => g.id === id)?.name ?? ''

async function addCategory() {
  const name = await dialog.prompt('Новая категория')
  if (name && await run(() => api.post('/v1/admin/categories', { body: { name } }), 'Категория добавлена')) {
    await load()
  }
}

async function patchCategory(id: string, body: { name?: string, is_active?: boolean }) {
  if (await ok(() => api.patch('/v1/admin/categories/{category_id}', { path: { category_id: id }, body }))) {
    await load()
  }
}

async function renameCategory(c: Catalog['categories'][number]) {
  const name = await dialog.prompt('Название категории', c.name)
  if (name && name !== c.name) {
    await patchCategory(c.id, { name })
  }
}

async function deleteCategory(id: string) {
  if (await dialog.confirm('Удалить пустую категорию?') && await ok(() => api.delete('/v1/admin/categories/{category_id}', { path: { category_id: id } }))) {
    await load()
  }
}

const groupForm = ref<{ show: (g?: Catalog['modifier_groups'][number]) => void }>()
const addGroup = () => groupForm.value?.show()
const editGroup = (g: Catalog['modifier_groups'][number]) => groupForm.value?.show(g)

async function deleteGroup(id: string) {
  if (await dialog.confirm('Удалить группу добавок?', 'Если её добавки уже заказывали, удалить не получится — выключите их.') && await ok(() => api.delete('/v1/admin/modifier-groups/{group_id}', { path: { group_id: id } }))) {
    await load()
  }
}

async function addModifier(groupId: string) {
  const name = newModifier[groupId]?.trim()
  if (name && await run(() => api.post('/v1/admin/modifier-groups/{group_id}/modifiers', { path: { group_id: groupId }, body: { name } }))) {
    newModifier[groupId] = ''
    await load()
  }
}

async function patchModifier(id: string, body: { price_minor?: number, is_active?: boolean }) {
  if (await ok(() => api.patch('/v1/admin/modifiers/{modifier_id}', { path: { modifier_id: id }, body }))) {
    await load()
  }
}

onMounted(load)
</script>

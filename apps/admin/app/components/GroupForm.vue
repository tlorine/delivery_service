<template>
  <UModal v-model:open="open" :title="groupId ? 'Правила группы' : 'Новая группа добавок'">
    <template #body>
      <form class="flex flex-col gap-4" @submit.prevent="submit">
        <UFormField label="Название" required>
          <UInput
            v-model="name"
            placeholder="Например: Соус"
            class="w-full"
          />
        </UFormField>
        <URadioGroup
          v-model="mode"
          :items="[
            { label: 'Можно не выбирать', value: 'optional' },
            { label: 'Обязательно выбрать', value: 'required' },
          ]"
        />
        <UFormField label="Сколько можно выбрать максимум">
          <UInputNumber
            v-model="max"
            :min="1"
            :max="20"
          />
        </UFormField>
        <UButton
          type="submit"
          label="Сохранить"
          block
          :disabled="!name.trim()"
        />
      </form>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const emit = defineEmits<{ saved: [] }>()
const open = ref(false)
const groupId = ref<string>()
const name = ref('')
const mode = ref<'optional' | 'required'>('optional')
const max = ref(1)
const api = useAdminApi()
const { run, ok } = useAdminAction()

function show(group?: { id: string, name: string, min_selected: number, max_selected: number }) {
  groupId.value = group?.id
  name.value = group?.name ?? ''
  mode.value = group && group.min_selected > 0 ? 'required' : 'optional'
  max.value = group?.max_selected ?? 1
  open.value = true
}
defineExpose({ show })

async function submit() {
  const body = { name: name.value.trim(), min_selected: mode.value === 'required' ? 1 : 0, max_selected: max.value }
  const id = groupId.value
  const done = id
    ? await ok(() => api.patch('/v1/admin/modifier-groups/{group_id}', { path: { group_id: id }, body }))
    : !!(await run(() => api.post('/v1/admin/modifier-groups', { body }), 'Группа добавлена'))
  if (done) {
    open.value = false
    emit('saved')
  }
}
</script>

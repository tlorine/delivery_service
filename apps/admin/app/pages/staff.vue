<template>
  <div class="flex flex-col gap-4 max-w-3xl">
    <h1 class="text-2xl font-semibold">
      Сотрудники
    </h1>
    <UCard>
      <div
        v-for="p in staff"
        :key="p.user_id"
        class="flex flex-wrap items-center gap-3 py-2 border-b border-default last:border-0"
      >
        <div class="flex-1 min-w-48">
          <p class="font-medium">
            {{ p.name }}
          </p>
          <p class="text-sm text-muted">
            {{ p.email }}
          </p>
        </div>
        <USelect
          :model-value="p.role"
          :items="roleItems"
          class="w-40"
          :aria-label="`Роль ${p.name}`"
          @update:model-value="(r) => setRole(p.user_id, r)"
        />
        <UButton
          v-if="p.user_id !== session.me.value?.user_id"
          icon="lucide:user-minus"
          variant="ghost"
          color="error"
          :aria-label="`Удалить ${p.name}`"
          @click="remove(p.user_id)"
        />
      </div>
    </UCard>

    <UCard>
      <p class="font-medium mb-3">
        Добавить сотрудника
      </p>
      <form class="grid sm:grid-cols-2 gap-3" @submit.prevent="add">
        <UFormField label="Имя" required>
          <UInput v-model="draft.name" class="w-full" />
        </UFormField>
        <UFormField label="Email" required>
          <UInput
            v-model="draft.email"
            type="email"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Роль">
          <USelect
            v-model="draft.role"
            :items="roleItems"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Пароль (от 10 символов)" hint="не нужен, если у человека уже есть вход">
          <UInput
            v-model="draft.password"
            type="password"
            autocomplete="new-password"
            class="w-full"
          />
        </UFormField>
        <UButton
          type="submit"
          label="Добавить"
          class="sm:col-span-2"
          :disabled="!draft.name || !draft.email"
        />
      </form>
      <p class="text-xs text-muted mt-3">
        Оператор — заказы и стоп-лист. Менеджер — ещё меню, расписание, доставка, аналитика. Владелец — всё, включая сотрудников и настройки.
      </p>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'

definePageMeta({ role: 'owner' })

type Role = 'owner' | 'manager' | 'operator'
const api = useAdminApi()
const { run, ok } = useAdminAction()
const session = useSession()
const staff = ref<components['schemas']['StaffOut'][]>([])
const roleItems = Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))
const draft = reactive({ name: '', email: '', role: 'operator' as Role, password: '' })

async function load() {
  staff.value = await api.get('/v1/admin/staff')
}

async function add() {
  if (await run(() => api.post('/v1/admin/staff', { body: { ...draft, password: draft.password || null } }), 'Сотрудник добавлен')) {
    Object.assign(draft, { name: '', email: '', role: 'operator', password: '' })
    await load()
  }
}

async function setRole(userId: string, role: string) {
  await ok(() => api.patch('/v1/admin/staff/{user_id}', { path: { user_id: userId }, body: { role: role as Role } }), 'Роль изменена')
  await load()
}

async function remove(userId: string) {
  if (await useDialog().confirm('Удалить сотрудника?', 'Доступ закроется сразу.') && await ok(() => api.delete('/v1/admin/staff/{user_id}', { path: { user_id: userId } }), 'Удалён')) {
    await load()
  }
}

onMounted(load)
</script>

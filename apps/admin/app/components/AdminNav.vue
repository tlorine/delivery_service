<template>
  <div class="flex flex-col gap-4 h-full">
    <div class="px-2">
      <p class="text-xs text-muted">
        Заведение
      </p>
      <USelect
        v-if="(session.me.value?.memberships.length ?? 0) > 1"
        :model-value="session.tenantId.value ?? undefined"
        :items="tenantItems"
        class="w-full mt-1"
        aria-label="Заведение"
        @update:model-value="switchTenant"
      />
      <p
        v-else
        class="font-semibold text-lg leading-6"
        data-testid="tenant-name"
      >
        {{ session.membership.value?.tenant_name }}
      </p>
    </div>

    <UNavigationMenu
      :items="items"
      orientation="vertical"
      class="flex-1"
    />

    <div class="px-2 pb-2 text-sm">
      <p class="font-medium">
        {{ session.me.value?.name }}
      </p>
      <p class="text-muted">
        {{ ROLE_LABEL[session.role.value ?? ''] }}
      </p>
      <UButton
        variant="link"
        color="neutral"
        class="px-0"
        icon="lucide:log-out"
        label="Выйти"
        @click="session.logout()"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { StaffRole } from '~/composables/useSession'

const session = useSession()

const all: { label: string, to: string, icon: string, role: StaffRole }[] = [
  { label: 'Заказы', to: '/orders', icon: 'lucide:receipt-text', role: 'operator' },
  { label: 'Стоп-лист', to: '/stoplist', icon: 'lucide:circle-slash', role: 'operator' },
  { label: 'Меню', to: '/menu', icon: 'lucide:utensils', role: 'manager' },
  { label: 'Расписание', to: '/schedule', icon: 'lucide:clock', role: 'manager' },
  { label: 'Доставка', to: '/delivery', icon: 'lucide:truck', role: 'manager' },
  { label: 'Аналитика', to: '/analytics', icon: 'lucide:chart-column', role: 'manager' },
  { label: 'Сотрудники', to: '/staff', icon: 'lucide:users', role: 'owner' },
  { label: 'Настройки', to: '/settings', icon: 'lucide:settings', role: 'owner' },
]
const items = computed(() => all.filter((i) => session.can(i.role)).map(({ role: _, ...i }) => i))
const tenantItems = computed(() => session.me.value?.memberships.map((m) => ({ label: m.tenant_name, value: m.tenant_id })) ?? [])

async function switchTenant(id: string) {
  session.choose(id)
  await navigateTo('/orders')
  reloadNuxtApp({ force: true })
}
</script>

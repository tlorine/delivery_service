<template>
  <div class="min-h-dvh flex">
    <aside class="hidden lg:flex w-64 shrink-0 flex-col border-r border-default bg-elevated/25 pt-4 sticky top-0 h-dvh">
      <AdminNav />
    </aside>

    <div class="flex-1 min-w-0">
      <header class="lg:hidden sticky top-0 z-10 flex items-center gap-2 px-3 h-14 border-b border-default bg-default">
        <USlideover
          v-model:open="menuOpen"
          side="left"
          title="Меню"
        >
          <UButton
            icon="lucide:menu"
            variant="ghost"
            color="neutral"
            aria-label="Открыть меню"
          />
          <template #body>
            <AdminNav @click="menuOpen = false" />
          </template>
        </USlideover>
        <span class="font-semibold truncate">{{ session.membership.value?.tenant_name }}</span>
      </header>

      <main class="p-3 md:p-6 max-w-6xl">
        <slot />
      </main>
    </div>
    <AppDialog />
  </div>
</template>

<script setup lang="ts">
const session = useSession()
const menuOpen = ref(false)
</script>

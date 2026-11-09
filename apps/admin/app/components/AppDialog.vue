<template>
  <UModal
    :open="dialog.state.value.open"
    :title="dialog.state.value.title"
    @update:open="(o) => !o && dialog.close(null)"
  >
    <template #body>
      <form class="flex flex-col gap-4" @submit.prevent="dialog.close(dialog.state.value.withInput ? (dialog.state.value.input ?? '') : true)">
        <p v-if="dialog.state.value.message" class="text-sm">
          {{ dialog.state.value.message }}
        </p>
        <UInput
          v-if="dialog.state.value.withInput"
          v-model="dialog.state.value.input"
          autofocus
          class="w-full"
          data-testid="dialog-input"
        />
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            color="neutral"
            label="Отмена"
            @click="dialog.close(null)"
          />
          <UButton
            type="submit"
            :color="dialog.state.value.danger ? 'error' : 'primary'"
            :label="dialog.state.value.withInput ? 'Сохранить' : 'Да'"
            data-testid="dialog-ok"
          />
        </div>
      </form>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const dialog = useDialog()
</script>

<template>
  <UCard class="w-full max-w-sm">
    <template #header>
      <h1 class="text-xl font-semibold">
        Вход для сотрудников
      </h1>
    </template>

    <form class="flex flex-col gap-4" @submit.prevent="submit">
      <UFormField label="Email" name="email">
        <UInput
          v-model="email"
          type="email"
          autocomplete="username"
          required
          class="w-full"
          size="lg"
        />
      </UFormField>
      <UFormField label="Пароль" name="password">
        <UInput
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="w-full"
          size="lg"
        />
      </UFormField>
      <p
        v-if="error"
        class="text-sm text-error"
        role="alert"
      >
        {{ error }}
      </p>
      <UButton
        type="submit"
        size="lg"
        block
        :loading="loading"
        label="Войти"
      />
    </form>
  </UCard>
</template>

<script setup lang="ts">
import type { ApiError } from '@delivery/api-client'

definePageMeta({ layout: 'blank' })

const session = useSession()
const route = useRoute()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await session.login(email.value, password.value)
    if (!session.membership.value) {
      error.value = 'У вас нет доступа ни к одному заведению'
      return
    }
    await navigateTo(String(route.query.next ?? '/orders'))
  } catch (e) {
    error.value = errorText((e as ApiError).code)
  } finally {
    loading.value = false
  }
}
</script>

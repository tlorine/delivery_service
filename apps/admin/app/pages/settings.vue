<template>
  <div v-if="settings" class="flex flex-col gap-4 max-w-2xl">
    <h1 class="text-2xl font-semibold">
      Настройки
    </h1>
    <UCard>
      <form class="flex flex-col gap-3" @submit.prevent="save">
        <UFormField label="Название заведения" required>
          <UInput v-model="form.name" class="w-full" />
        </UFormField>
        <UFormField label="Короткое описание">
          <UTextarea
            v-model="form.description"
            :rows="2"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Логотип (ссылка https://)">
          <UInput
            v-model="form.logo_url"
            placeholder="https://…"
            class="w-full"
          />
        </UFormField>
        <UButton
          type="submit"
          label="Сохранить"
          class="self-start"
        />
      </form>
    </UCard>

    <UCard>
      <p class="font-medium mb-3">
        Оформление витрины
      </p>
      <form class="flex flex-col gap-4" @submit.prevent="save">
        <UFormField label="Фирменный цвет" hint="кнопки и акценты на сайте и в Telegram">
          <div class="flex flex-wrap items-center gap-3">
            <input
              v-model="pickerColor"
              type="color"
              class="h-10 w-14 cursor-pointer rounded border border-default bg-transparent"
              aria-label="Выбрать цвет"
              data-testid="accent-picker"
            >
            <UInput
              v-model="form.accent_color"
              placeholder="#D2381F"
              class="w-32"
              aria-label="Цвет в HEX"
              data-testid="accent-hex"
            />
            <UButton
              v-if="form.accent_color"
              variant="link"
              color="neutral"
              label="Как у платформы"
              @click="form.accent_color = ''"
            />
          </div>
        </UFormField>
        <p v-if="form.accent_color && !validColor" class="text-sm text-error">
          Укажите цвет в формате #RRGGBB
        </p>

        <div>
          <p class="text-sm text-muted mb-1.5">
            Так кнопка выглядит на витрине
          </p>
          <div
            class="inline-flex h-12 min-w-56 items-center justify-between gap-6 rounded-xl px-5 font-semibold"
            :style="{ background: preview.accent, color: preview.onAccent }"
            data-testid="accent-preview"
          >
            <span>Добавить</span><span>390 ₽</span>
          </div>
          <p
            v-if="adjusted"
            class="mt-1.5 text-xs text-muted"
            data-testid="accent-adjusted"
          >
            Цвет немного затемнён ({{ preview.accent }}), чтобы текст на кнопках читался — это требование доступности.
          </p>
        </div>

        <UFormField label="Обложка (ссылка https://)" hint="широкое фото зала или блюд, примерно 1500×500">
          <UInput
            v-model="form.cover_url"
            placeholder="https://…"
            class="w-full"
            data-testid="cover-url"
          />
        </UFormField>
        <div v-if="coverPreview" class="overflow-hidden rounded-xl bg-elevated aspect-[3/1]">
          <img
            :src="coverPreview"
            alt="Обложка витрины"
            class="size-full object-cover"
            data-testid="cover-preview"
          >
        </div>
        <UButton
          type="submit"
          label="Сохранить"
          class="self-start"
          :disabled="!!form.accent_color && !validColor"
          data-testid="save-appearance"
        />
      </form>
    </UCard>

    <UCard>
      <p class="font-medium mb-2">
        Telegram
      </p>
      <template v-if="settings.telegram_bot">
        <p>Бот: <span class="font-medium">{{ settings.telegram_bot }}</span></p>
        <p v-if="settings.telegram_staff_chat_connected" class="text-success">
          Уведомления о заказах приходят в чат сотрудников
        </p>
        <div v-else class="mt-2 text-sm">
          <p>Чтобы получать заказы в Telegram: добавьте бота в чат сотрудников и отправьте там команду</p>
          <code class="block mt-1 p-2 rounded bg-elevated select-all">{{ settings.telegram_link_command }}</code>
        </div>
      </template>
      <p v-else class="text-sm text-muted">
        Бот ещё не подключён — обратитесь в поддержку платформы.
      </p>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { components } from '@delivery/api-client'
import { brandTokens, DEFAULT_ACCENT, normalizeHex } from '@delivery/api-client'

definePageMeta({ role: 'owner' })

const api = useAdminApi()
const { ok } = useAdminAction()
const settings = ref<components['schemas']['SettingsOut']>()
const form = reactive({ name: '', description: '', logo_url: '', accent_color: '', cover_url: '' })

// Same colour logic as the storefront (packages/api-client/src/brand.ts): the preview is what buyers see.
const validColor = computed(() => normalizeHex(form.accent_color) !== null)
const preview = computed(() => brandTokens(validColor.value ? form.accent_color : DEFAULT_ACCENT))
const adjusted = computed(() => validColor.value && preview.value.accent !== normalizeHex(form.accent_color))
const pickerColor = computed({
  get: () => normalizeHex(form.accent_color) ?? DEFAULT_ACCENT,
  set: (v: string) => {
    form.accent_color = v.toUpperCase()
  },
})
const coverPreview = computed(() => form.cover_url.startsWith('https://') ? form.cover_url : '')

async function load() {
  settings.value = await api.get('/v1/admin/settings')
  const b = settings.value.branding
  Object.assign(form, {
    name: settings.value.name,
    description: b.description ?? '',
    logo_url: b.logo_url ?? '',
    accent_color: b.accent_color ?? '',
    cover_url: b.cover_url ?? '',
  })
}

async function save() {
  await ok(() => api.patch('/v1/admin/settings', {
    body: {
      name: form.name,
      branding: {
        description: form.description || null,
        logo_url: form.logo_url || null,
        accent_color: normalizeHex(form.accent_color),
        cover_url: form.cover_url.trim() || null,
      },
    },
  }), 'Сохранено')
  await load()
}

onMounted(load)
</script>

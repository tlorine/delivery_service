<template>
  <UBadge
    :color="STATUS_COLOR[status]"
    variant="subtle"
    :label="STATUS_LABEL[status]"
  />
</template>

<script setup lang="ts">
import type { OrderStatus } from '@delivery/api-client'

defineProps<{ status: OrderStatus }>()
</script>

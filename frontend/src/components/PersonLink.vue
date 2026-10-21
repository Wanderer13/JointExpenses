<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const props = withDefaults(
  defineProps<{
    userId: number
    name: string
    email?: string | null
    showEmail?: boolean
  }>(),
  { showEmail: false },
)

const auth = useAuthStore()
const isYou = computed(() => auth.user?.id === props.userId)
</script>

<template>
  <span class="person-link">
    <template v-if="isYou">
      <strong>You</strong>
    </template>
    <RouterLink v-else :to="`/users/${userId}`" class="person-name">{{ name }}</RouterLink>
    <a
      v-if="showEmail && email && !isYou"
      class="person-email muted"
      :href="`mailto:${email}`"
      >{{ email }}</a
    >
  </span>
</template>

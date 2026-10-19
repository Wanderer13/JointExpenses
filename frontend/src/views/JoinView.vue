<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import type { Group } from '../types'

const props = defineProps<{ token: string }>()
const router = useRouter()
const error = ref('')

onMounted(async () => {
  try {
    const group = await api<Group>(`/api/groups/join/${props.token}`, { method: 'POST' })
    router.replace(`/groups/${group.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to join'
  }
})
</script>

<template>
  <div class="panel">
    <h1>Joining group…</h1>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

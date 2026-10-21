import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'
import type { Overview } from '../types'

export const useOverviewStore = defineStore('overview', () => {
  const data = ref<Overview | null>(null)
  const loading = ref(false)

  async function refresh() {
    loading.value = true
    try {
      data.value = await api<Overview>('/api/me/overview')
    } finally {
      loading.value = false
    }
  }

  function clear() {
    data.value = null
  }

  return { data, loading, refresh, clear }
})

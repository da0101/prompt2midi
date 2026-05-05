import { defineStore } from 'pinia'
import { ref } from 'vue'
import { toast } from '../composables/useToast.js'

export const useAceStore = defineStore('ace', () => {
  const status = ref('unknown')
  const message = ref('')

  async function poll() {
    try {
      const res = await fetch('/api/ace/status')
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const data = await res.json()
      status.value = data.status ?? 'unknown'
      message.value = data.message ?? ''
    } catch (error) {
      status.value = 'unknown'
      message.value = 'API server unreachable. Start it with npm run web:dev.'
      return error
    }
    return null
  }

  async function action(name) {
    try {
      const res = await fetch(`/api/ace/${name}`, {
        method: 'POST',
        headers: name === 'stop' ? { 'Content-Type': 'application/json' } : {},
        body: name === 'stop' ? JSON.stringify({ managedOnly: false }) : undefined,
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
    } catch (error) {
      status.value = 'unknown'
      message.value = 'API server unreachable. Start it with npm run web:dev.'
      toast.error('API server unreachable', `Could not ${name} ACE. Run npm run web:dev and refresh.`)
      return false
    }
    const pollError = await poll()
    if (pollError) {
      toast.error('API server unreachable', 'Run npm run web:dev and refresh.')
      return false
    }
    return true
  }

  return { status, message, poll, action }
})

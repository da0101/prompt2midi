import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const RUN_KEY = 'aceui_runId'

export const useRunStore = defineStore('run', () => {
  const currentRunId = ref(localStorage.getItem(RUN_KEY) || null)
  const run = ref(null)
  const isSubmitting = ref(false)
  let pollTimer = null

  // ── Computed ──────────────────────────────────────────────────
  const isActive = computed(() =>
    run.value?.status === 'running' || run.value?.status === 'queued',
  )
  const progress = computed(() => run.value?.progress ?? 0)
  const step = computed(() => {
    if (!currentRunId.value) return 'Idle'
    return run.value?.step || 'Loading…'
  })
  const events = computed(() => run.value?.events ?? [])
  const files = computed(() => run.value?.files ?? {})
  const runError = computed(() => run.value?.error ?? '')
  const isDone = computed(() =>
    run.value?.status === 'succeeded' || run.value?.status === 'failed',
  )

  // ── Helpers ───────────────────────────────────────────────────
  function persist(id) {
    currentRunId.value = id
    if (id) localStorage.setItem(RUN_KEY, id)
    else localStorage.removeItem(RUN_KEY)
  }

  // ── Polling ───────────────────────────────────────────────────
  async function poll() {
    if (!currentRunId.value) return false
    try {
      const res = await fetch(`/api/runs/${currentRunId.value}`)
      if (!res.ok) {
        // Stale run ID (e.g. server restarted) — stop polling and clear
        stopPolling()
        isSubmitting.value = false
        persist(null)
        run.value = null
        return false
      }
      run.value = await res.json()
    } catch {
      return false
    }
    if (isDone.value) {
      stopPolling()
      isSubmitting.value = false
      return true
    }
    return false
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(poll, 1500)
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }

  // ── Actions ───────────────────────────────────────────────────
  async function submit(payload) {
    isSubmitting.value = true
    run.value = null

    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (!res.ok || data.error) {
        run.value = { error: data.error || `Server error ${res.status}`, status: 'failed', events: [], files: {} }
        isSubmitting.value = false
        return
      }

      persist(data.id)
      run.value = data
      startPolling()
    } catch (err) {
      run.value = { error: err.message || 'Network error — is the API server running?', status: 'failed', events: [], files: {} }
      isSubmitting.value = false
    }
  }

  // Reconnect to a run that was started before a page refresh
  async function restore() {
    if (!currentRunId.value) return
    await poll()
    if (isActive.value) startPolling()
  }

  function clear() {
    stopPolling()
    persist(null)
    run.value = null
    isSubmitting.value = false
  }

  return {
    currentRunId, run, isSubmitting,
    isActive, isDone, progress, step, events, files, runError,
    submit, restore, poll, startPolling, stopPolling, clear,
  }
})

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import FormPanel from './components/FormPanel.vue'
import ProgressFooter from './components/ProgressFooter.vue'
import LogSheet from './components/LogSheet.vue'
import ToastStack from './components/ToastStack.vue'
import { useRunStore } from './stores/run.js'
import { useAceStore } from './stores/ace.js'
import { useSheet } from './composables/useSheet.js'
import { toast } from './composables/useToast.js'

const run = useRunStore()
const ace = useAceStore()
const { open: openSheet } = useSheet()
const formRef = ref(null)

let aceInterval = null

// Named handler so it can be removed on unmount (fix #7: no HMR leak)
function onPageHide() {
  if (!formRef.value?.autoStopAce) return
  if (navigator.sendBeacon) {
    navigator.sendBeacon(
      '/api/ace/stop',
      new Blob([JSON.stringify({ managedOnly: true })], { type: 'application/json' }),
    )
  }
}

// Pause generator polling when tab is hidden, resume when visible (fix #8)
function onVisibilityChange() {
  if (document.hidden) {
    clearInterval(aceInterval)
    aceInterval = null
  } else {
    ace.poll()
    aceInterval = setInterval(() => ace.poll(), 2500) // fix #15: arrow wrapper
  }
}

// Fire toast when polling detects run completion
watch(() => run.isDone, (done) => {
  if (!done) return
  if (run.runError) {
    toast.error('Pipeline failed', run.runError)
  } else {
    toast.success('Track ready', 'Open Logs to listen to your generated tracks.')
  }
})

onMounted(async () => {
  await run.restore()
  if (run.isActive) openSheet()

  fetch('/api/ace/start', { method: 'POST' })
    .catch(() => {
      toast.error('API server offline', 'Run npm run web:dev, then refresh this page.')
    })
    .finally(() => ace.poll())
  aceInterval = setInterval(() => ace.poll(), 2500)

  window.addEventListener('pagehide', onPageHide)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  clearInterval(aceInterval)
  run.stopPolling()
  window.removeEventListener('pagehide', onPageHide)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <AppHeader />
  <FormPanel ref="formRef" />
  <ProgressFooter />
  <LogSheet />
  <ToastStack />
</template>

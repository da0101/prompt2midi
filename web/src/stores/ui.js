import { defineStore } from 'pinia'
import { ref } from 'vue'

// HMR-safe sheet state — Pinia stores survive hot-module replacement,
// module-level refs do not.
export const useUIStore = defineStore('ui', () => {
  const sheetOpen = ref(false)
  const open = () => { sheetOpen.value = true }
  const close = () => { sheetOpen.value = false }
  const toggle = () => { sheetOpen.value = !sheetOpen.value }
  return { sheetOpen, open, close, toggle }
})

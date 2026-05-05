import { storeToRefs } from 'pinia'
import { useUIStore } from '../stores/ui.js'

// Thin wrapper so call sites don't need to know about the store.
// storeToRefs ensures sheetOpen stays reactive when destructured.
export function useSheet() {
  const store = useUIStore()
  const { sheetOpen } = storeToRefs(store)
  return { sheetOpen, open: store.open, close: store.close, toggle: store.toggle }
}

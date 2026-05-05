import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

export function useToast() {
  function add(type, title, description = '') {
    const id = ++nextId
    toasts.value.push({ id, type, title, description })
    setTimeout(() => dismiss(id), type === 'error' ? 6000 : 3500)
  }

  function dismiss(id) {
    const i = toasts.value.findIndex(t => t.id === id)
    if (i !== -1) toasts.value.splice(i, 1)
  }

  return {
    toasts,
    success: (title, description) => add('success', title, description),
    error:   (title, description) => add('error',   title, description),
    info:    (title, description) => add('info',    title, description),
    dismiss,
  }
}

// Singleton so any component can fire toasts without prop-drilling
export const toast = useToast()

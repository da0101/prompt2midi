<script setup>
import { ref } from 'vue'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { toast } from '../composables/useToast.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  pick: { type: String, default: 'file' }, // 'file' | 'folder'
})

const emit = defineEmits(['update:modelValue', 'pathDropped'])
const isPicking = ref(false)

async function browse() {
  isPicking.value = true
  try {
    const endpoint = props.pick === 'folder' ? '/api/pick-folder' : '/api/pick-file'
    const res = await fetch(endpoint, { method: 'POST' })
    if (!res.ok) throw new Error(`API returned ${res.status}`)
    const data = await res.json()
    if (data.path) {
      emit('update:modelValue', data.path)
      emit('pathDropped', data.path)
    }
  } catch (error) {
    toast.error('Browse unavailable', 'The local API server is not reachable. Run npm run web:dev and refresh.')
  } finally {
    isPicking.value = false
  }
}
</script>

<template>
  <div class="flex gap-2">
    <Input
      :value="modelValue"
      :placeholder="placeholder"
      type="text"
      class="h-9 text-sm flex-1 min-w-0"
      @input="emit('update:modelValue', $event.target.value)"
    />
    <Button
      size="sm"
      variant="outline"
      class="h-9 px-3 text-xs flex-shrink-0"
      :disabled="isPicking"
      @click="browse"
    >
      {{ isPicking ? '…' : 'Browse' }}
    </Button>
  </div>
</template>

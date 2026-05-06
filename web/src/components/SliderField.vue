<script setup>
import { computed } from 'vue'
import { Label } from '@/components/ui/label'
import FieldTooltip from './FieldTooltip.vue'

const props = defineProps({
  label: { type: String, required: true },
  tooltip: { type: String, default: '' },
  riskHint: { type: String, default: '' },
  riskKind: { type: String, default: 'copy' },
  showRisk: { type: Boolean, default: true },
  decimals: { type: Number, default: 2 },
  numberWidth: { type: String, default: '56px' },
  modelValue: { type: Number, default: 0 },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 1 },
  step: { type: Number, default: 0.01 },
})
const emit = defineEmits(['update:modelValue'])

function onRange(e) {
  emit('update:modelValue', parseFloat(e.target.value))
}

function onNumber(e) {
  const v = parseFloat(e.target.value)
  if (!isNaN(v)) emit('update:modelValue', Math.min(props.max, Math.max(props.min, v)))
}

const displayValue = computed(() => props.modelValue.toFixed(props.decimals))

const pct = computed(() => {
  if (props.max <= props.min) return 0
  return Math.max(0, Math.min(100, ((props.modelValue - props.min) / (props.max - props.min)) * 100))
})
const isFixed = computed(() => props.max <= props.min)

const riskLevel = computed(() => {
  if (pct.value >= 72) return 'high'
  if (pct.value >= 45) return 'medium'
  return 'safe'
})

const riskText = computed(() => {
  if (props.riskHint) return props.riskHint
  if (props.riskKind === 'guide') {
    if (riskLevel.value === 'high') return 'strong reference guidance'
    if (riskLevel.value === 'medium') return 'medium reference guidance'
    return 'loose reference guidance'
  }
  if (props.riskKind === 'source') {
    if (riskLevel.value === 'high') return 'starts very close to audio'
    if (riskLevel.value === 'medium') return 'starts partly from audio'
    return 'starts more from noise'
  }
  if (props.riskKind === 'variation') {
    if (riskLevel.value === 'high') return 'high variation / artifact risk'
    if (riskLevel.value === 'medium') return 'strong variation zone'
    return 'stable variation zone'
  }
  if (riskLevel.value === 'high') return 'high copy risk'
  if (riskLevel.value === 'medium') return 'closer reference zone'
  return 'safer reference zone'
})

const trackStyle = computed(() => ({
  background: `linear-gradient(to right,
    #22c55e 0%,
    #22c55e 42%,
    #f59e0b 58%,
    #ef4444 100%)`,
}))

const thumbAccent = computed(() => {
  if (riskLevel.value === 'high') return '#ef4444'
  if (riskLevel.value === 'medium') return '#f59e0b'
  return '#22c55e'
})
</script>

<template>
  <div class="space-y-1.5 mt-3">
    <Label class="text-xs text-muted-foreground">
      {{ label }}
      <FieldTooltip v-if="tooltip" :text="tooltip" />
      &mdash;
      <span class="text-foreground tabular-nums font-medium">{{ displayValue }}</span>
      <span
        v-if="showRisk"
        class="ml-2 text-[10px] font-semibold uppercase tracking-wide"
        :class="{
          'text-emerald-400': riskLevel === 'safe',
          'text-amber-400': riskLevel === 'medium',
          'text-red-400': riskLevel === 'high',
        }"
      >
        {{ riskText }}
      </span>
    </Label>
    <div class="flex items-center gap-2">
      <input
        type="range"
        :min="min" :max="max" :step="step" :value="modelValue"
        class="flex-1 cursor-pointer h-2 rounded-full"
        :class="{ 'opacity-60 cursor-not-allowed': isFixed }"
        :disabled="isFixed"
        :style="{ ...trackStyle, accentColor: thumbAccent }"
        :aria-label="label"
        :aria-valuenow="modelValue"
        :aria-valuemin="min"
        :aria-valuemax="max"
        @input="onRange"
      />
      <input
        type="number"
        :min="min" :max="max" :step="step" :value="modelValue"
        :style="{ width: numberWidth, flexShrink: 0 }"
        class="text-center text-xs tabular-nums rounded-md border border-border bg-secondary text-foreground px-1.5 py-1 h-8 outline-none focus:border-primary"
        :aria-label="label + ' value'"
        @change="onNumber"
      />
    </div>
  </div>
</template>

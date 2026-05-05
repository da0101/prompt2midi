<script setup>
import { computed } from 'vue'
import { useAceStore } from '../stores/ace.js'
import { Button } from '@/components/ui/button'

const ace = useAceStore()

const statusClass = computed(() => ({
  running:  'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  starting: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  stopping: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  busy:     'bg-amber-500/20 text-amber-400 border-amber-500/30',
  failed:   'bg-red-500/20 text-red-400 border-red-500/30',
  stopped:  'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  unknown:  'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
}[ace.status] || 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'))
</script>

<template>
  <header class="sticky top-0 z-40 flex items-center gap-2.5 border-b border-border bg-background px-5 h-[52px]">
    <div class="flex items-center justify-center rounded-lg flex-shrink-0 w-7 h-7 bg-primary" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="hsl(var(--primary-foreground))" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18V5l12-2v13"/>
        <circle cx="6" cy="18" r="3"/>
        <circle cx="18" cy="16" r="3"/>
      </svg>
    </div>

    <div>
      <h1 class="text-base font-bold tracking-tight leading-none">Inspired</h1>
      <p class="text-[10px] text-muted-foreground leading-none mt-0.5">Reference-driven track clone</p>
    </div>

    <div class="ml-auto flex items-center gap-2">
      <!-- fix #16: aria-live so screen readers announce status changes -->
      <span
        role="status"
        aria-live="polite"
        class="inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase transition-colors"
        :class="statusClass"
        :title="ace.message"
      >
        {{ ace.status }}
      </span>

      <Button size="sm" variant="outline" class="h-7 text-xs px-2.5" @click="ace.action('start')">Start</Button>
      <Button size="sm" variant="outline" class="h-7 text-xs px-2.5" @click="ace.action('stop')">Stop</Button>
      <Button size="sm" variant="outline" class="h-7 text-xs px-2.5" @click="ace.action('restart')">Restart</Button>
    </div>
  </header>
</template>

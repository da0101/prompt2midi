<script setup>
defineProps({ text: { type: String, required: true } })
</script>

<template>
  <span class="relative group inline-flex items-center ml-1 align-middle">
    <!-- Info icon -->
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
      class="text-muted-foreground/40 group-hover:text-muted-foreground cursor-help transition-colors">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="16" x2="12" y2="12"/>
      <line x1="12" y1="8" x2="12.01" y2="8"/>
    </svg>

    <!-- Tooltip bubble -->
    <span
      role="tooltip"
      class="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5
             w-56 rounded-lg border border-border bg-popover px-3 py-2
             text-xs text-muted-foreground leading-relaxed shadow-xl
             opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-[200]
             whitespace-normal"
    >
      {{ text }}
      <!-- Arrow -->
      <span class="absolute top-full left-1/2 -translate-x-1/2
                   border-4 border-transparent border-t-border" />
    </span>
  </span>
</template>

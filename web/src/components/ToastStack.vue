<script setup>
import { toast } from '../composables/useToast.js'
</script>

<template>
  <div
    aria-live="polite"
    aria-label="Notifications"
    style="position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;width:320px;pointer-events:none"
  >
    <transition-group name="toast">
      <div
        v-for="t in toast.toasts.value"
        :key="t.id"
        role="status"
        style="
          pointer-events:auto;
          border-radius:10px;
          border:1px solid hsl(var(--border));
          background:hsl(var(--card));
          padding:12px 14px;
          box-shadow:0 4px 24px rgba(0,0,0,0.35);
          display:flex;
          align-items:flex-start;
          gap:10px;
          cursor:pointer;
        "
        @click="toast.dismiss(t.id)"
      >
        <!-- Icon -->
        <div style="flex-shrink:0;margin-top:1px">
          <!-- success -->
          <svg v-if="t.type === 'success'" width="15" height="15" viewBox="0 0 24 24"
            fill="none" stroke="hsl(142,71%,45%)" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
          <!-- error -->
          <svg v-else-if="t.type === 'error'" width="15" height="15" viewBox="0 0 24 24"
            fill="none" stroke="hsl(0,72%,60%)" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <!-- info -->
          <svg v-else width="15" height="15" viewBox="0 0 24 24"
            fill="none" stroke="hsl(var(--muted-foreground))" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>

        <!-- Text -->
        <div style="flex:1;min-width:0">
          <p style="font-size:13px;font-weight:600;color:hsl(var(--foreground));line-height:1.3;margin:0">
            {{ t.title }}
          </p>
          <p v-if="t.description"
            style="font-size:12px;color:hsl(var(--muted-foreground));margin:3px 0 0;line-height:1.4">
            {{ t.description }}
          </p>
        </div>

        <!-- Dismiss x -->
        <svg style="flex-shrink:0;color:hsl(var(--muted-foreground));margin-top:1px;cursor:pointer"
          width="13" height="13" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active { transition: all 0.2s ease; }
.toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from   { opacity: 0; transform: translateX(20px); }
.toast-leave-to     { opacity: 0; transform: translateX(20px); }
</style>

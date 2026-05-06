<script setup>
import { ref, watch, nextTick, onUnmounted, computed } from 'vue'
import { Bug, CircleAlert, CircleX, Copy, ExternalLink } from 'lucide-vue-next'
import { useRunStore } from '../stores/run.js'
import { useAudioStore } from '../stores/audio.js'
import { useSheet } from '../composables/useSheet.js'
import { toast } from '../composables/useToast.js'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

const run = useRunStore()
const audio = useAudioStore()
const { sheetOpen, close } = useSheet()

const eventsBottom = ref(null)
const showDebug = ref(false)

// Elapsed timer — ticks every second while a run is active
const now = ref(Date.now())
let ticker = null
watch(() => run.isActive, (active) => {
  if (active) {
    ticker = setInterval(() => { now.value = Date.now() }, 1000)
  } else {
    clearInterval(ticker); ticker = null
  }
}, { immediate: true })
onUnmounted(() => clearInterval(ticker))

const elapsedLabel = computed(() => {
  if (!run.run?.createdAt) return null
  const secs = Math.floor((now.value - new Date(run.run.createdAt).getTime()) / 1000)
  if (secs < 0) return null
  const m = Math.floor(secs / 60)
  const s = String(secs % 60).padStart(2, '0')
  return `${m}:${s}`
})

const visibleEvents = computed(() => {
  const events = showDebug.value
    ? run.events
    : run.events.filter((ev) => !['trace', 'log', 'command'].includes(ev.type))
  return events.map((ev) => ({ ...ev, displayMessage: producerCopy(ev.message) }))
})

const debugSeverity = computed(() => {
  if (run.events.some((ev) => ev.type === 'error')) return 'error'
  if (run.events.some((ev) => ev.type === 'warning')) return 'warning'
  return 'ok'
})

const DebugIcon = computed(() => {
  if (debugSeverity.value === 'error') return CircleX
  if (debugSeverity.value === 'warning') return CircleAlert
  return Bug
})

const sunoPromptUrl = computed(() => (
  run.files.sunoPrompt ? '/file?path=' + encodeURIComponent(run.files.sunoPrompt) : ''
))

const debugButtonClass = computed(() => {
  if (!showDebug.value) return 'text-muted-foreground'
  if (debugSeverity.value === 'error') {
    return 'border-destructive/60 bg-destructive/10 text-destructive shadow-[0_0_0_1px_rgba(239,68,68,0.12)]'
  }
  if (debugSeverity.value === 'warning') {
    return 'border-amber-400/60 bg-amber-500/10 text-amber-300 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]'
  }
  return 'border-emerald-400/60 bg-emerald-500/10 text-emerald-300 shadow-[0_0_0_1px_rgba(52,211,153,0.12)]'
})

// Auto-scroll to newest event (list is oldest-first)
watch(
  () => run.events.length,
  async () => {
    if (!sheetOpen.value) return
    await nextTick()
    eventsBottom.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  },
)

// Populate the global player when files arrive.
// Keyed by file paths so this fires once, not on every poll.
watch(
  () => [
    ...(run.files.candidates ?? []),
    run.files.sunoUploadWav ?? '',
  ].join('|'),
  (key) => {
    if (!key || key === '|') return
    const list = [
      ...(run.files.candidates ?? []).map((p, i) => ({
        src: '/file?path=' + encodeURIComponent(p),
        label: `Candidate ${i + 1}`,
      })),
      ...(run.files.sunoUploadWav
        ? [{ src: '/file?path=' + encodeURIComponent(run.files.sunoUploadWav), label: 'Suno proxy' }]
        : []),
    ]
    if (list.length) audio.setTracks(list)
  },
  { immediate: true },
)

async function copySunoPrompt() {
  const text = run.files.sunoPromptText || ''
  if (!text) {
    toast.error('SUNO prompt unavailable', 'The prompt file was not found in this run.')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    toast.success('SUNO prompt copied', `${text.length} characters ready to paste.`)
  } catch {
    toast.error('Copy failed', 'Open the prompt file and copy it manually.')
  }
}

function producerCopy(text) {
  return String(text || '')
    .replace(/\bACE-Step\b/g, 'local generator')
    .replace(/\bace-step\b/gi, 'generation')
    .replace(/\bACE\b/g, 'local generator')
}
</script>

<template>
  <!-- Backdrop -->
  <div
    class="fixed inset-0 bg-black/50 z-[90] transition-opacity duration-300"
    :class="sheetOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'"
    aria-hidden="true"
    @click="close"
  />

  <!-- Sheet -->
  <div
    role="dialog"
    aria-label="Run Log"
    class="fixed left-0 right-0 z-[100] flex flex-col bg-card rounded-t-2xl transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
    style="bottom: 54px; height: 62vh; min-height: 320px; box-shadow: 0 -1px 0 hsl(var(--border)), 0 -8px 32px rgba(0,0,0,0.4)"
    :class="sheetOpen ? 'translate-y-0' : 'translate-y-full'"
  >
    <!-- Pull handle -->
    <div
      role="button"
      tabindex="0"
      aria-label="Close log sheet"
      class="flex justify-center py-2.5 cursor-pointer flex-shrink-0"
      @click="close"
      @keydown.enter="close"
      @keydown.space.prevent="close"
    >
      <div class="w-9 h-1 rounded-full bg-border" />
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between px-4 pb-2.5 flex-shrink-0">
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="text-sm font-bold flex-shrink-0">Run Log</span>
        <!-- Elapsed timer while running -->
        <span v-if="run.isActive && elapsedLabel"
          class="text-xs tabular-nums text-primary font-mono flex-shrink-0">
          {{ elapsedLabel }}
        </span>
        <!-- Run UUID for traceability -->
        <span v-if="run.currentRunId"
          class="text-[10px] text-muted-foreground font-mono truncate"
          :title="run.currentRunId">
          {{ run.currentRunId }}
        </span>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <Button
          variant="outline"
          size="sm"
          class="h-7 px-2.5 text-xs gap-1.5"
          :class="debugButtonClass"
          :aria-pressed="showDebug"
          @click="showDebug = !showDebug"
        >
          <component
            :is="DebugIcon"
            class="w-3.5 h-3.5 transition-transform"
            :class="showDebug ? 'animate-pulse scale-110' : 'opacity-60'"
            aria-hidden="true"
          />
          {{ showDebug ? 'Debug on' : 'Debug' }}
        </Button>
        <Button variant="ghost" size="icon" class="h-7 w-7 text-muted-foreground"
          aria-label="Close log sheet" @click="close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </Button>
      </div>
    </div>

    <Separator />

    <!-- Body -->
    <ScrollArea class="flex-1">
      <div class="px-4 py-4 space-y-4">

        <!-- Running banner -->
        <div v-if="run.isActive"
          class="flex items-start gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2.5 text-xs text-muted-foreground leading-relaxed">
          <span class="mt-0.5 w-2 h-2 rounded-full bg-primary flex-shrink-0 animate-pulse" aria-hidden="true" />
          Pipeline is running — {{ showDebug ? 'debug trace is visible below' : 'major steps are visible below' }}. Audio will appear here when done.
        </div>

        <!-- Empty state -->
        <p v-else-if="!run.run" class="text-xs text-muted-foreground">
          Hit <strong class="text-foreground">Run Pipeline</strong> to start a generation run.
        </p>

        <!-- Error -->
        <p v-if="run.runError" role="alert" class="text-xs text-destructive">{{ run.runError }}</p>

        <!-- Events — oldest first, newest at bottom -->
        <ul v-if="visibleEvents.length" class="space-y-0" aria-label="Pipeline events">
          <li
            v-for="ev in visibleEvents"
            :key="`${ev.at}|${ev.type}|${ev.message}`"
            class="flex gap-2 items-baseline border-b border-white/5 py-1.5 text-xs last:border-0"
          >
            <span
              class="font-bold flex-shrink-0"
              :class="{
                'text-destructive': ev.type === 'error',
                'text-amber-400': ev.type === 'warning',
                'text-primary': ev.type === 'done' || ev.type === 'progress',
                'text-sky-400': ev.type === 'trace',
                'text-muted-foreground/50': ev.type === 'log',
                'text-muted-foreground': !['error','warning','done','progress','trace','log'].includes(ev.type),
              }"
            >{{ ev.type }}</span>
            <span class="text-muted-foreground break-words min-w-0">{{ ev.displayMessage }}</span>
          </li>
          <div ref="eventsBottom" />
        </ul>

        <!-- Generated tracks — click to play in the bottom player -->
        <div v-if="audio.tracks.length" class="space-y-2 pt-1">
          <Separator />
          <p class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Generated files</p>

          <div
            v-for="(track, i) in audio.tracks"
            :key="track.src"
            class="flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors"
            :class="audio.activeIndex === i
              ? 'border-primary/40 bg-primary/5'
              : 'border-border bg-secondary hover:border-primary/20'"
            @click="audio.selectTrack(i)"
          >
            <!-- Play / Pause / Spinner icon -->
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-colors"
              :class="audio.activeIndex === i
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground'"
            >
              <svg v-if="audio.activeIndex === i && audio.isLoading"
                width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2.5" class="animate-spin">
                <circle cx="12" cy="12" r="9" stroke-opacity="0.25"/>
                <path d="M12 3a9 9 0 0 1 9 9"/>
              </svg>
              <svg v-else-if="audio.activeIndex === i && audio.isPlaying"
                width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1"/>
                <rect x="14" y="4" width="4" height="16" rx="1"/>
              </svg>
              <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="currentColor"
                style="margin-left: 1px">
                <polygon points="5,3 19,12 5,21"/>
              </svg>
            </div>

            <!-- Label -->
            <span
              class="text-sm font-medium flex-1"
              :class="audio.activeIndex === i ? 'text-foreground' : 'text-muted-foreground'"
            >{{ track.label }}</span>

            <!-- Live pulse when playing -->
            <span
              v-if="audio.activeIndex === i && audio.isPlaying"
              class="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0 animate-pulse"
            />
          </div>

          <p class="text-[10px] text-muted-foreground">
            Tap a track to load it in the player at the bottom of the screen.
          </p>
        </div>

        <!-- SUNO prompt — copy this after uploading the generated proxy audio -->
        <div v-if="run.files.sunoPrompt || run.files.sunoPromptText" class="space-y-2 pt-1">
          <Separator />
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                SUNO optimized prompt
              </p>
              <p class="text-[10px] text-muted-foreground">
                Upload the SUNO proxy audio, then paste this prompt into SUNO.
              </p>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <Button
                v-if="run.files.sunoPromptText"
                variant="outline"
                size="sm"
                class="h-7 px-2.5 text-xs gap-1.5"
                @click="copySunoPrompt"
              >
                <Copy class="w-3.5 h-3.5" aria-hidden="true" />
                Copy
              </Button>
              <a
                v-if="sunoPromptUrl"
                :href="sunoPromptUrl"
                target="_blank"
                rel="noreferrer"
                class="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                <ExternalLink class="w-3.5 h-3.5" aria-hidden="true" />
                Open
              </a>
            </div>
          </div>
          <pre
            v-if="run.files.sunoPromptText"
            class="max-h-44 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-secondary/30 p-3 text-xs leading-relaxed text-muted-foreground"
          >{{ run.files.sunoPromptText }}</pre>
        </div>

      </div>
    </ScrollArea>
  </div>
</template>

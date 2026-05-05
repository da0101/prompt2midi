<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Howl } from 'howler'
import { useRunStore } from '../stores/run.js'
import { useAudioStore, registerPlayPause } from '../stores/audio.js'
import { useSheet } from '../composables/useSheet.js'
import { Button } from '@/components/ui/button'

const run = useRunStore()
const audio = useAudioStore()
const { sheetOpen, toggle } = useSheet()

const seekBar = ref(null)
const displayTime = ref(0)

let howl = null
let rafId = null
let _dragging = false

// ── RAF tick: poll Howler for current position ───────────────
function tick() {
  if (!howl || !audio.isPlaying) return
  const t = howl.seek()
  if (typeof t === 'number') {
    audio.currentTime = t
    if (!_dragging) {
      displayTime.value = t
      if (seekBar.value) seekBar.value.value = String(Math.floor(t))
    }
  }
  rafId = requestAnimationFrame(tick)
}

function startTick() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(tick)
}

function stopTick() {
  if (rafId) { cancelAnimationFrame(rafId); rafId = null }
}

function destroyHowl() {
  stopTick()
  if (howl) { howl.stop(); howl.unload(); howl = null }
}

// ── Load + play a track ──────────────────────────────────────
watch(() => audio.activeIndex, (index) => {
  destroyHowl()
  if (index < 0 || !audio.tracks[index]) return

  const src = audio.tracks[index].src
  console.log('[howl] loading track', index, src)

  audio.isLoading = true
  audio.isPlaying = false
  audio.currentTime = 0
  audio.duration = 0
  displayTime.value = 0
  if (seekBar.value) seekBar.value.value = '0'

  howl = new Howl({
    src: [src],
    format: ['wav', 'mp3'],
    html5: false,             // Web Audio API — downloads whole file, no Range requests needed
    autoplay: true,
    onload() {
      const dur = howl.duration()
      console.log('[howl] loaded — duration:', dur)
      audio.duration = dur
      audio.isLoading = false
    },
    onplay() {
      console.log('[howl] playing')
      audio.isPlaying = true
      startTick()
    },
    onpause() {
      console.log('[howl] paused')
      audio.isPlaying = false
      stopTick()
    },
    onstop() {
      audio.isPlaying = false
      stopTick()
    },
    onend() {
      console.log('[howl] ended – loopMode:', audio.loopMode)
      audio.isPlaying = false
      stopTick()

      if (audio.loopMode === 'one') {
        howl.seek(0)
        howl.play()
      } else if (audio.canNext) {
        audio.selectTrack(audio.activeIndex + 1)
      } else if (audio.loopMode === 'all') {
        if (audio.activeIndex === 0) {
          // Single track — replay in place
          howl.seek(0)
          howl.play()
        } else {
          // Loop back to first
          audio.selectTrack(0)
        }
      }
      // loopMode 'off' + no next track → stop
    },
    onloaderror(id, err) {
      console.error('[howl] load error:', err)
      audio.isLoading = false
    },
    onplayerror(id, err) {
      console.error('[howl] play error:', err)
      audio.isPlaying = false
    },
  })
})

function onKeyDown(e) {
  if (e.code !== 'Space') return
  if (!audio.activeTrack) return
  const tag = e.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable) return
  e.preventDefault()
  audio.playPause()
}

onMounted(() => {
  registerPlayPause(() => {
    if (!howl) return
    audio.isPlaying ? howl.pause() : howl.play()
  })
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  destroyHowl()
  registerPlayPause(null)
  window.removeEventListener('keydown', onKeyDown)
})

// ── Seek bar handlers ────────────────────────────────────────
function onSeekDown() {
  _dragging = true
  console.log('[seek] drag start')
}

function onSeekInput(e) {
  displayTime.value = Number(e.target.value)
}

function onSeekEnd(e) {
  _dragging = false
  const t = Number(e.target.value)
  console.log('[seek] commit to', t, '— duration:', audio.duration)
  displayTime.value = t
  audio.currentTime = t
  if (howl) {
    howl.seek(t)
    // Resume tick after manual seek so the display keeps updating
    if (audio.isPlaying) startTick()
  }
}

function fmt(s) {
  const total = Math.floor(s || 0)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}
</script>

<template>
  <div
    class="fixed bottom-0 left-0 right-0 z-[110] flex items-center gap-2.5 bg-card border-t border-border px-4"
    style="height: 54px"
  >

    <!-- ── Pipeline progress mode ─────────────────────────────── -->
    <template v-if="!audio.activeTrack">
      <span v-if="run.isActive" class="w-2 h-2 rounded-full bg-primary flex-shrink-0 animate-pulse" />
      <span class="text-xs font-semibold text-foreground truncate flex-shrink-0 max-w-[200px]">
        {{ run.step }}
      </span>
      <div class="flex-1 h-1 rounded-full overflow-hidden bg-secondary">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="run.isActive
            ? 'bg-gradient-to-r from-primary to-sky-400 animate-pulse'
            : 'bg-gradient-to-r from-primary to-sky-400'"
          :style="{ width: Math.max(run.progress, run.isActive ? 4 : 0) + '%' }"
        />
      </div>
      <span class="text-xs tabular-nums flex-shrink-0"
        :class="run.isActive ? 'text-primary' : 'text-muted-foreground'">
        {{ run.progress }}%
      </span>
    </template>

    <!-- ── Audio player mode ──────────────────────────────────── -->
    <template v-else>

      <!-- Skip back -->
      <button
        class="flex-shrink-0 w-7 h-7 flex items-center justify-center transition-colors cursor-pointer"
        :class="audio.canPrev ? 'text-muted-foreground hover:text-foreground' : 'text-muted-foreground/25 cursor-not-allowed'"
        aria-label="Previous track"
        @click="audio.canPrev && audio.selectTrack(audio.activeIndex - 1)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <rect x="4" y="4" width="2" height="16" rx="1"/>
          <polygon points="20,4 8,12 20,20"/>
        </svg>
      </button>

      <!-- Play / Pause / Spinner -->
      <button
        class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-opacity cursor-pointer"
        :class="audio.isLoading ? 'bg-muted cursor-not-allowed' : 'bg-primary text-primary-foreground hover:opacity-80'"
        :aria-label="audio.isPlaying ? 'Pause' : 'Play'"
        @click="audio.playPause()"
      >
        <svg v-if="audio.isLoading" width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2.5" class="animate-spin text-muted-foreground">
          <circle cx="12" cy="12" r="9" stroke-opacity="0.25"/>
          <path d="M12 3a9 9 0 0 1 9 9"/>
        </svg>
        <svg v-else-if="audio.isPlaying" width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="4" width="4" height="16" rx="1"/>
          <rect x="14" y="4" width="4" height="16" rx="1"/>
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="margin-left: 1px">
          <polygon points="5,3 19,12 5,21"/>
        </svg>
      </button>

      <!-- Skip forward -->
      <button
        class="flex-shrink-0 w-7 h-7 flex items-center justify-center transition-colors cursor-pointer"
        :class="audio.canNext ? 'text-muted-foreground hover:text-foreground' : 'text-muted-foreground/25 cursor-not-allowed'"
        aria-label="Next track"
        @click="audio.canNext && audio.selectTrack(audio.activeIndex + 1)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <rect x="18" y="4" width="2" height="16" rx="1"/>
          <polygon points="4,4 16,12 4,20"/>
        </svg>
      </button>

      <!-- Track label -->
      <span class="text-xs font-semibold text-foreground flex-shrink-0 truncate" style="max-width: 90px">
        {{ audio.activeTrack.label }}
      </span>

      <!-- Current time -->
      <span class="text-xs tabular-nums text-muted-foreground flex-shrink-0 w-8 text-right">
        {{ audio.isLoading ? '…' : fmt(displayTime) }}
      </span>

      <!-- Seek bar — uncontrolled, updated imperatively from RAF tick -->
      <input
        ref="seekBar"
        type="range"
        class="flex-1 h-1 cursor-pointer accent-primary"
        min="0"
        :max="audio.duration > 0 ? Math.floor(audio.duration) : 1"
        :disabled="audio.isLoading"
        @mousedown="onSeekDown"
        @touchstart.passive="onSeekDown"
        @input="onSeekInput"
        @change="onSeekEnd"
        @touchend="onSeekEnd"
      />

      <!-- Total time -->
      <span class="text-xs tabular-nums text-muted-foreground flex-shrink-0 w-8">
        {{ audio.isLoading ? '…' : fmt(audio.duration) }}
      </span>

      <!-- Loop mode: off → all → one → off -->
      <button
        class="flex-shrink-0 w-7 h-7 flex items-center justify-center transition-colors cursor-pointer relative"
        :class="audio.loopMode !== 'off' ? 'text-primary' : 'text-muted-foreground/40 hover:text-muted-foreground'"
        :aria-label="audio.loopMode === 'one' ? 'Repeat one' : audio.loopMode === 'all' ? 'Repeat all' : 'No repeat'"
        @click="audio.cycleLoop()"
      >
        <!-- Repeat-one icon -->
        <svg v-if="audio.loopMode === 'one'" width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="17 1 21 5 17 9"/>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
          <polyline points="7 23 3 19 7 15"/>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
          <line x1="11" y1="10" x2="11" y2="19"/>
          <path d="m9 12 2-2"/>
        </svg>
        <!-- Repeat-all / off icon -->
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="17 1 21 5 17 9"/>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
          <polyline points="7 23 3 19 7 15"/>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
        </svg>
        <!-- Active dot indicator under icon for 'all' -->
        <span
          v-if="audio.loopMode === 'all'"
          class="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary"
        />
      </button>

    </template>

    <!-- Logs button — always visible -->
    <Button
      size="sm"
      :variant="sheetOpen ? 'secondary' : 'outline'"
      class="h-7 text-xs gap-1.5 flex-shrink-0"
      :class="{ 'animate-pulse': run.isActive && !sheetOpen }"
      @click="toggle"
    >
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none"
        stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
        <path d="M2 4h12M2 8h12M2 12h8"/>
      </svg>
      Logs
    </Button>

  </div>
</template>

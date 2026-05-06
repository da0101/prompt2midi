import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// Module-level slot — ProgressFooter registers its <audio> play/pause logic here
// so LogSheet can toggle playback without needing a ref to the DOM element.
let _playPauseFn = null
export function registerPlayPause(fn) { _playPauseFn = fn }

export const useAudioStore = defineStore('audio', () => {
  const tracks = ref([])     // { src: string, label: string }[]
  const activeIndex = ref(-1)
  const isPlaying = ref(false)
  const isLoading = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const loopMode = ref('off') // 'off' | 'all' | 'one'

  const activeTrack = computed(() =>
    activeIndex.value >= 0 ? tracks.value[activeIndex.value] : null,
  )
  const canNext = computed(() => activeIndex.value < tracks.value.length - 1)
  const canPrev = computed(() => activeIndex.value > 0)

  function cycleLoop() {
    const modes = ['off', 'all', 'one']
    loopMode.value = modes[(modes.indexOf(loopMode.value) + 1) % modes.length]
  }

  function setTracks(list) {
    tracks.value = list
  }

  function selectTrack(index) {
    if (index < 0 || index >= tracks.value.length) return
    if (index === activeIndex.value) {
      _playPauseFn?.()
      return
    }
    currentTime.value = 0
    duration.value = 0
    isPlaying.value = false
    isLoading.value = true
    activeIndex.value = index
  }

  function playPause() {
    _playPauseFn?.()
  }

  function clear() {
    tracks.value = []
    activeIndex.value = -1
    isPlaying.value = false
    isLoading.value = false
    currentTime.value = 0
    duration.value = 0
  }

  return {
    tracks, activeIndex, isPlaying, isLoading, currentTime, duration, loopMode,
    activeTrack, canNext, canPrev,
    setTracks, selectTrack, playPause, cycleLoop, clear,
  }
})

<script setup>
import { onMounted, ref } from 'vue'
import { toast } from '../composables/useToast.js'
import FilePicker from './FilePicker.vue'
import SliderField from './SliderField.vue'
import FieldTooltip from './FieldTooltip.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { useRunStore } from '../stores/run.js'
import { useAudioStore } from '../stores/audio.js'
import { useSheet } from '../composables/useSheet.js'

const run = useRunStore()
const audioStore = useAudioStore()
const { open: openSheet } = useSheet()

const validationError = ref('')
const reference = ref('')
const DEFAULT_PROMPT = 'same tempo and key area as the reference.'
const TRIBAL_DRUM_PROMPT = 'Add continuous loud fast tribal percussion as a clear main layer across the whole clip: dense 16th-note congas, bongos, shakers, tambourine, clave, wood hits, and low toms over the main groove. Keep the percussion loud, fast, nonstop, and easy to hear.'
const prompt = ref(DEFAULT_PROMPT)
const similarity = ref('medium-high')
const referenceStart = ref(8)
const duration = ref(30)
const candidates = ref(4)
const referenceStrength = ref(0.32)
const coverNoiseStrength = ref(0.14)
const aceSteps = ref(12)
const aceGuidance = ref(7)
const aceSeed = ref(-1)
const aceCaps = ref(defaultAceCaps())
const acePreset = ref('custom')
const vocals = ref(true)
const geminiBrief = ref(false)
const geminiControl = ref(false)
const reconstructionDiagnostic = ref(false)
const outputName = ref('')
const autoStopAce = ref(true)
const droppedOutputDir = ref(null)

function defaultAceCaps() {
  return {
    hardwareLabel: 'Detecting local hardware...',
    model: 'acestep-v15-turbo',
    maxDurationSeconds: 180,
    maxCandidates: 4,
    steps: { min: 1, max: 8, default: 8 },
    guidance: { min: 1, max: 1, default: 1 },
    seed: { min: -1, max: 9999, default: -1 },
    message: 'Detecting local ACE and hardware limits.',
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value)))
}

function applyCaps(caps) {
  aceCaps.value = { ...defaultAceCaps(), ...caps }
  duration.value = clamp(duration.value, 10, aceCaps.value.maxDurationSeconds)
  candidates.value = Math.round(clamp(candidates.value, 1, aceCaps.value.maxCandidates))
  aceSteps.value = Math.round(clamp(aceSteps.value, aceCaps.value.steps.min, aceCaps.value.steps.max))
  aceGuidance.value = clamp(aceGuidance.value, aceCaps.value.guidance.min, aceCaps.value.guidance.max)
  aceSeed.value = Math.round(clamp(aceSeed.value, aceCaps.value.seed.min, aceCaps.value.seed.max))
}

const acePresets = {
  custom: null,
  clone_25: {
    prompt: DEFAULT_PROMPT,
    similarity: 'medium',
    referenceStrength: 0.2,
    coverNoiseStrength: 0.06,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  clone_50: {
    prompt: DEFAULT_PROMPT,
    similarity: 'high',
    referenceStrength: 0.36,
    coverNoiseStrength: 0.14,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  clone_75: {
    prompt: DEFAULT_PROMPT,
    similarity: 'very-high',
    referenceStrength: 0.56,
    coverNoiseStrength: 0.3,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  clone_100: {
    prompt: DEFAULT_PROMPT,
    similarity: 'near-identical',
    referenceStrength: 1,
    coverNoiseStrength: 1,
    aceSeed: 1234,
    geminiBrief: false,
    geminiControl: false,
    reconstructionDiagnostic: false,
  },
  tribal_25: {
    prompt: TRIBAL_DRUM_PROMPT,
    similarity: 'medium',
    referenceStrength: 0.2,
    coverNoiseStrength: 0.06,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  tribal_50: {
    prompt: TRIBAL_DRUM_PROMPT,
    similarity: 'high',
    referenceStrength: 0.36,
    coverNoiseStrength: 0.14,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  tribal_75: {
    prompt: TRIBAL_DRUM_PROMPT,
    similarity: 'very-high',
    referenceStrength: 0.56,
    coverNoiseStrength: 0.3,
    aceSeed: -1,
    reconstructionDiagnostic: false,
  },
  tribal_100: {
    prompt: TRIBAL_DRUM_PROMPT,
    similarity: 'near-identical',
    referenceStrength: 1,
    coverNoiseStrength: 1,
    aceSeed: 1234,
    geminiBrief: false,
    geminiControl: false,
    reconstructionDiagnostic: false,
  },
}

function applyAcePreset(value) {
  acePreset.value = value
  const preset = acePresets[value]
  if (!preset) {
    reconstructionDiagnostic.value = false
    return
  }
  if (preset.prompt !== undefined) prompt.value = preset.prompt
  if (preset.similarity) similarity.value = preset.similarity
  if (preset.referenceStrength !== undefined) referenceStrength.value = preset.referenceStrength
  if (preset.coverNoiseStrength !== undefined) coverNoiseStrength.value = preset.coverNoiseStrength
  if (preset.aceSeed !== undefined) aceSeed.value = clamp(preset.aceSeed, aceCaps.value.seed.min, aceCaps.value.seed.max)
  if (preset.geminiBrief !== undefined) geminiBrief.value = preset.geminiBrief
  if (preset.geminiControl !== undefined) geminiControl.value = preset.geminiControl
  if (preset.reconstructionDiagnostic !== undefined) reconstructionDiagnostic.value = preset.reconstructionDiagnostic
}

onMounted(async () => {
  try {
    const response = await fetch('/api/ace/capabilities')
    if (!response.ok) throw new Error(`API returned ${response.status}`)
    applyCaps(await response.json())
  } catch {
    applyCaps(defaultAceCaps())
  }
})

function onRefChange(val) {
  reference.value = val
  if (val) validationError.value = ''
}

function onOutDrop(fullPath) {
  droppedOutputDir.value = fullPath
  outputName.value = fullPath.split('/').pop() || fullPath
}

function onOutputNameInput(val) {
  outputName.value = val
  droppedOutputDir.value = null
}

function reset() {
  // Clear run + audio state
  run.clear()
  audioStore.clear()

  // Reset form fields
  validationError.value = ''
  similarity.value = 'medium-high'
  referenceStart.value = 8
  duration.value = 30
  candidates.value = 4
  referenceStrength.value = 0.32
  coverNoiseStrength.value = 0.14
  acePreset.value = 'custom'
  aceSteps.value = aceCaps.value.steps.default
  aceGuidance.value = aceCaps.value.guidance.default
  aceSeed.value = -1
  vocals.value = true
  geminiBrief.value = false
  geminiControl.value = false
  reconstructionDiagnostic.value = false
  prompt.value = DEFAULT_PROMPT
  reference.value = ''
  outputName.value = ''
  droppedOutputDir.value = null

  toast.success('Pipeline reset')
}

async function submit() {
  if (!reference.value.trim()) {
    validationError.value = 'Please drop a reference track first.'
    return
  }
  validationError.value = ''
  audioStore.clear()
  openSheet()
  await run.submit({
    reference: reference.value,
    prompt: prompt.value,
    similarityLevel: similarity.value,
    referenceStart: Number(referenceStart.value),
    duration: Number(duration.value),
    candidates: Number(candidates.value),
    referenceStrength: Number(referenceStrength.value),
    coverNoiseStrength: Number(coverNoiseStrength.value),
    aceSteps: Number(aceSteps.value),
    aceGuidance: Number(aceGuidance.value),
    aceSeed: Number(aceSeed.value),
    vocals: vocals.value,
    geminiBrief: geminiBrief.value,
    geminiControl: geminiControl.value,
    reconstructionDiagnostic: false,
    outputName: outputName.value,
    outputDir: droppedOutputDir.value || null,
  })

}

function onGeminiControlChange(value) {
  geminiControl.value = checked(value)
  if (geminiControl.value) geminiBrief.value = true
}

function checked(value) {
  return value === true || value === 'true' || value === 'on' || value === 'checked' || value === 1 || value === '1'
}

// fix #2: expose the boolean value, not the ref object
defineExpose({ get autoStopAce() { return autoStopAce.value } })
</script>

<template>
  <main class="px-5 pt-7 pb-6">
    <div class="max-w-[560px] mx-auto">

      <p class="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-5">
        New Clone
      </p>

      <!-- Reference track -->
      <div>
        <Label class="text-xs text-muted-foreground block mb-1.5">
          Reference track
          <FieldTooltip text="The song ACE listens to. This is the example for rhythm, sound, energy, and structure." />
        </Label>
        <FilePicker
          :model-value="reference"
          placeholder="No file selected"
          pick="file"
          @update:model-value="onRefChange"
        />
      </div>

      <!-- Prompt -->
      <div class="mt-4">
        <Label class="text-xs text-muted-foreground block mb-1.5">
          Prompt direction
          <FieldTooltip text="Tell ACE what to change or add. Example: add loud tribal drums, no vocals, stronger bass." />
        </Label>
        <Textarea v-model="prompt" class="min-h-[66px] resize-y text-sm" />
      </div>

      <Separator class="my-5" />

      <!-- Similarity + Ref start -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <Label class="text-xs text-muted-foreground block mb-1.5">
            Similarity
            <FieldTooltip text="The big closeness mode. Low means make a new cousin. Near-identical means stay very close to the reference." />
          </Label>
          <Select v-model="similarity">
            <SelectTrigger class="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">low</SelectItem>
              <SelectItem value="medium-low">medium-low</SelectItem>
              <SelectItem value="medium">medium</SelectItem>
              <SelectItem value="medium-high">medium-high</SelectItem>
              <SelectItem value="high">high</SelectItem>
              <SelectItem value="very-high">very-high</SelectItem>
              <SelectItem value="near-identical">near-identical</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label class="text-xs text-muted-foreground block mb-1.5">
            Ref start (s)
            <FieldTooltip text="Where ACE starts listening in the song. Use this to skip the intro and point at the best groove." />
          </Label>
          <Input v-model.number="referenceStart" type="number" min="0" step="0.5" class="h-9 text-sm" />
        </div>
      </div>

      <!-- Duration + Candidates -->
      <div class="grid grid-cols-2 gap-3 mt-3">
        <div>
          <Label class="text-xs text-muted-foreground block mb-1.5">
            Duration (s)
          <FieldTooltip :text="`How long the new clip should be. Longer clips take longer and use more memory. This computer/model allows up to ${aceCaps.maxDurationSeconds}s here.`" />
        </Label>
          <Input v-model.number="duration" type="number" min="10" :max="aceCaps.maxDurationSeconds" step="1" class="h-9 text-sm" />
        </div>
        <div>
          <Label class="text-xs text-muted-foreground block mb-1.5">
            Candidates
          <FieldTooltip :text="`How many versions ACE makes in one run. More versions gives more choices, but each one costs time. This computer/model allows up to ${aceCaps.maxCandidates}.`" />
        </Label>
          <Input v-model.number="candidates" type="number" min="1" :max="aceCaps.maxCandidates" step="1" class="h-9 text-sm" />
        </div>
      </div>

      <!-- Sliders -->
      <div class="mt-3">
        <Label class="text-xs text-muted-foreground block mb-1.5">
          ACE preset
          <FieldTooltip text="A saved starting recipe for the sliders. Pick one, then adjust by ear." />
        </Label>
        <Select :model-value="acePreset" @update:model-value="applyAcePreset">
          <SelectTrigger class="h-9 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="custom">custom</SelectItem>
            <SelectItem value="clone_25">25% clone</SelectItem>
            <SelectItem value="clone_50">50% clone</SelectItem>
            <SelectItem value="clone_75">75% clone</SelectItem>
            <SelectItem value="clone_100">100% clone</SelectItem>
            <SelectItem value="tribal_25">25% clone + tribal drums</SelectItem>
            <SelectItem value="tribal_50">50% clone + tribal drums</SelectItem>
            <SelectItem value="tribal_75">75% clone + tribal drums</SelectItem>
            <SelectItem value="tribal_100">100% clone + tribal drums</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <SliderField
        label="Reference guidance"
        tooltip="How tightly ACE holds the reference song's hand while making the new audio. Higher means it keeps listening to the reference for more of the trip."
        risk-kind="guide"
        :model-value="referenceStrength"
        :min="0" :max="1" :step="0.01"
        @update:model-value="referenceStrength = $event"
      />
      <SliderField
        label="Audio start amount"
        tooltip="Where ACE starts from. Low means start from fog and invent more. High means start from a shape that is already close to the reference audio."
        risk-kind="source"
        :model-value="coverNoiseStrength"
        :min="0" :max="1" :step="0.01"
        @update:model-value="coverNoiseStrength = $event"
      />

      <!-- Reconstruction diagnostic UI is temporarily disabled while we stabilize the normal pipeline. -->

      <details class="mt-4 rounded-md border border-border/70 bg-secondary/20 px-3 py-2">
        <summary class="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Advanced ACE
        </summary>
        <p class="mt-2 text-xs leading-relaxed text-muted-foreground">
          {{ aceCaps.message }}
        </p>
        <div class="mt-3">
          <SliderField
            label="Steps"
            :tooltip="aceCaps.steps.note || 'How many cleanup passes ACE tries. More can be cleaner on some models, but turbo is capped.'"
            :show-risk="false"
            :decimals="0"
            number-width="64px"
            :model-value="aceSteps"
            :min="aceCaps.steps.min" :max="aceCaps.steps.max" :step="1"
            @update:model-value="aceSteps = $event"
          />
          <SliderField
            label="Guidance"
            :tooltip="aceCaps.guidance.note || 'How hard ACE listens to the text prompt. Higher means obey the words more, if the model supports it.'"
            :show-risk="false"
            :decimals="1"
            number-width="64px"
            :model-value="aceGuidance"
            :min="aceCaps.guidance.min" :max="aceCaps.guidance.max" :step="0.1"
            @update:model-value="aceGuidance = $event"
          />
          <SliderField
            label="Seed"
            :tooltip="aceCaps.seed.note || 'The dice roll number. -1 means new random dice. A fixed number repeats the same kind of randomness for fair tests.'"
            :show-risk="false"
            :decimals="0"
            number-width="88px"
            :model-value="aceSeed"
            :min="aceCaps.seed.min" :max="aceCaps.seed.max" :step="1"
            @update:model-value="aceSeed = $event"
          />
        </div>
      </details>

      <Separator class="my-5" />

      <!-- Output folder -->
      <div>
        <Label class="text-xs text-muted-foreground block mb-1.5">
          Output folder
          <FieldTooltip text="Where ACE saves the generated files. Leave empty to save inside tmp." />
        </Label>
        <FilePicker
          :model-value="outputName"
          placeholder="Leave empty to use tmp/"
          pick="folder"
          @update:model-value="onOutputNameInput"
          @path-dropped="onOutDrop"
        />
      </div>

      <!-- Vocals -->
      <div class="flex items-center gap-2.5 mt-4">
        <Checkbox
          id="vocals"
          :model-value="vocals"
          @update:model-value="vocals = checked($event)"
        />
        <Label for="vocals" class="text-sm text-muted-foreground cursor-pointer">
          Vocals / hook role enabled
        </Label>
        <FieldTooltip text="Turn this on if you want ACE to make a new vocal or hook role. Turn it off for instrumental tests." />
      </div>

      <!-- Gemini -->
      <div class="flex items-center gap-2.5 mt-3">
        <Checkbox
          id="geminiBrief"
          :model-value="geminiBrief"
          @update:model-value="geminiBrief = checked($event)"
          :disabled="reconstructionDiagnostic"
        />
        <Label for="geminiBrief" class="text-sm text-muted-foreground cursor-pointer">
          Gemini smart ACE brief
        </Label>
        <FieldTooltip text="Ask Gemini to rewrite your idea into a better ACE instruction. Use this when your prompt is messy or too short." />
      </div>

      <div class="flex items-center gap-2.5 mt-3">
        <Checkbox
          id="geminiControl"
          :model-value="geminiControl"
          @update:model-value="onGeminiControlChange"
          :disabled="reconstructionDiagnostic"
        />
        <Label for="geminiControl" class="text-sm text-muted-foreground cursor-pointer">
          Experimental Gemini ACE controls
        </Label>
        <FieldTooltip text="Experimental. Lets Gemini move the closeness sliders for you. Leave off when you want a clean manual test." />
      </div>

      <!-- Buttons -->
      <div class="flex gap-2.5 mt-5">
        <Button class="flex-1" :disabled="run.isSubmitting" @click="submit">
          {{ run.isSubmitting ? 'Running…' : 'Run Pipeline' }}
        </Button>
        <Button variant="outline" @click="reset">Reset</Button>
      </div>

      <!-- Validation error -->
      <p v-if="validationError" role="alert" class="text-xs text-destructive mt-2">{{ validationError }}</p>

      <!-- Auto-stop — fix #1: v-model -->
      <div class="flex items-center gap-2 mt-4">
        <Checkbox id="autostop" v-model="autoStopAce" />
        <Label for="autostop" class="text-xs text-muted-foreground cursor-pointer">
          Stop UI-managed ACE server when this tab closes
        </Label>
      </div>

      <!-- Hint -->
      <p class="text-xs text-muted-foreground leading-relaxed mt-3 pb-2">
        Fast ACE proxy lane only &mdash; skips MIDI, stems, bass scaffolds, MusicGen, and arrangement generation.
      </p>

    </div>
  </main>
</template>

import assert from 'node:assert/strict'
import { build } from 'esbuild'

// Bundle the actual store so these contracts exercise its composition too.
const result = await build({
  stdin: {
    contents: `export { useStore } from './src/stores/useStore';
      export { trackAnalysisProgress } from './src/stores/analysisProgress';
      export { toggleLoraState, updateLoraWeight } from './src/stores/loraState';
      export { canonicalDirectorSkill } from './src/types';
      export { saveModeSettings, loadModeSettings, persistStickyStudioPreferences, modeBlobToLoraIdKeyed, modeBlobToFilenameKeyed, stripEphemeralParams } from './src/stores/studioPersistence';`,
    resolveDir: process.cwd(), loader: 'ts',
  },
  bundle: true, write: false, format: 'esm', platform: 'node',
  define: { 'import.meta.hot': 'undefined' },
})
const { useStore, trackAnalysisProgress, toggleLoraState, updateLoraWeight, canonicalDirectorSkill, saveModeSettings, loadModeSettings, persistStickyStudioPreferences, modeBlobToLoraIdKeyed, modeBlobToFilenameKeyed, stripEphemeralParams } =
  await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`)
const original = useStore.getState()
const pending = []
globalThis.fetch = (url, options) => new Promise(resolve => pending.push({ url, options, resolve }))
const respond = (request, data) => request.resolve(new Response(JSON.stringify({ setup: data })))

useStore.setState({ activeWorkspace: 'alpha' })
const alpha = useStore.getState().loadWorkspaceSetup('alpha')
useStore.setState({ activeWorkspace: 'beta' })
const beta = useStore.getState().loadWorkspaceSetup('beta')
respond(pending[1], { aspect_ratio: '9:16', music_source: 'generate', music_model: 'beta-music' })
await beta
respond(pending[0], { aspect_ratio: '4:3', music_source: 'upload', music_model: 'alpha-music' })
await alpha
assert.equal(useStore.getState().directorAspectRatio, '9:16')
assert.equal(useStore.getState().directorMusicModel, 'beta-music')
assert.equal(useStore.getState().activeWorkspaceSetupLoading, false)

const save = useStore.getState().saveWorkspaceSetup({ aspect_ratio: '1:1' })
useStore.setState({ activeWorkspace: 'gamma' })
respond(pending[2], { aspect_ratio: '1:1' })
await save
assert.equal(useStore.getState().directorAspectRatio, '9:16', 'late save must not change another project')

let resolveStatus
const events = []
let current = true
const progress = trackAnalysisProgress(
  () => new Promise(resolve => { resolveStatus = resolve }),
  value => events.push(value), () => current,
)
const tick = progress.refresh()
resolveStatus({ step: 'transcribing', detail: 'Transcribing', current: 2, total: 6 })
await tick
assert.equal(events.at(-1).current, 2)
const lateTick = progress.refresh()
progress.finish('done')
resolveStatus({ step: 'late', detail: 'Old response', current: 3, total: 6 })
await lateTick
assert.equal(events.at(-1).status, 'done')
assert.equal(events.at(-1).current, 6)
const resetProgress = trackAnalysisProgress(async () => ({ step: 'old', detail: '', current: 1, total: 2 }),
  value => events.push(value), () => current)
const beforeReset = events.length
current = false
await resetProgress.refresh()
resetProgress.finish('error')
assert.equal(events.length, beforeReset, 'reset invalidates old progress')
const errors = []
const failed = trackAnalysisProgress(async () => { throw new Error('offline') }, value => errors.push(value), () => true)
await failed.refresh()
failed.finish('error')
assert.equal(errors.at(-1).status, 'error')

const toggled = toggleLoraState([], {}, 'actor.safetensors', 3)
assert.equal(toggled.multipliers, '1.00;1.00;1.00')
const weighted = updateLoraWeight(toggled.activatedLoras, toggled.weights, 'actor.safetensors', 1, 0.7, 3)
assert.equal(weighted.multipliers, '1.00;0.70;1.00')
assert.deepEqual(toggled.weights['actor.safetensors'], [1, 1, 1], 'weights are immutable')
assert.equal(canonicalDirectorSkill('demo_local_skill'), 'demo_local_skill')

useStore.setState(original, true)
let submitted
// Exercise actual request construction while stopping before any generation.
globalThis.fetch = async (url, options) => {
  if (options?.method === 'POST') {
    submitted = JSON.parse(options.body)
    return new Response(JSON.stringify({ detail: 'Fixture: generation deliberately stopped' }), { status: 400 })
  }
  return new Response(JSON.stringify({}))
}
useStore.setState({ activeWorkspace: 'fixture', directorSceneDescription: 'A quiet station', directorSkill: 'demo_local_skill' })
useStore.getState().applyWorkspaceSetup({
  video_model: 'fixture-video', image_model: 'fixture-image',
  music_source: 'generate', music_model: 'fixture-music',
  advanced: { video_film_grain_intensity: 0.2, video_num_inference_steps: 12, video_self_refiner: 2,
    image_spatial_upsampling: 'lanczos2', untrusted_extra: 'must not leak' },
  default_video_loras: { activated_loras: ['actor.safetensors'], loras_multipliers: '0.70',
    loraWeights: { 'actor.safetensors': [0.7] } },
})
await useStore.getState().startDirectorPipeline()
assert.equal(submitted.skill_type, 'demo_local_skill')
assert.equal(submitted.video_film_grain_intensity, 0.2)
assert.equal(submitted.video_params.num_inference_steps, 12)
assert.equal(submitted.video_self_refiner, 2)
assert.equal(submitted.image_spatial_upsampling, 'lanczos2')
assert.deepEqual(submitted.video_loras.activated_loras, ['actor.safetensors'])
assert.equal(submitted.untrusted_extra, undefined)
useStore.getState().setDirectorVideoFilmGrainIntensity(0.4)
await useStore.getState().startDirectorPipeline()
assert.equal(submitted.video_film_grain_intensity, 0.4, 'per-take edit wins over project defaults')
useStore.getState().applyWorkspaceSetup({ advanced: {}, music_model: '' })
assert.equal(useStore.getState().directorVideoFilmGrainIntensity, 0)
assert.equal(useStore.getState().directorVideoInferenceStepsByModel['fixture-video'], undefined)
assert.equal(useStore.getState().directorMusicModel, original.directorMusicModel)
useStore.setState(original, true)
// Round-trip the real mode-switch action without model/network initialization.
globalThis.fetch = async () => new Response('{}')
globalThis.localStorage = { getItem: () => null, setItem: () => {} }
useStore.setState({ params: { ...original.params, model_type: '', prompt: 'Video prompt', seed: 101 },
  models: [], families: [], enabledModels: new Set() })
useStore.getState().setGenerationMode('image')
useStore.getState().setParam('prompt', 'Image prompt')
useStore.getState().setParam('seed', 202)
useStore.getState().setGenerationMode('video')
assert.equal(useStore.getState().params.prompt, 'Video prompt')
assert.equal(useStore.getState().params.seed, 101)
useStore.getState().setGenerationMode('image')
assert.equal(useStore.getState().params.prompt, 'Image prompt')
assert.equal(useStore.getState().params.seed, 202)
useStore.getState().setStudioImageWorkflow('outpaint')
assert.equal(useStore.getState().params.image_mode, 2)
useStore.getState().setStudioImageWorkflow('upscale')
assert.equal(useStore.getState().generationMode, 'tools')
assert.equal(useStore.getState().toolsUpscaleMedia, 'image')
useStore.getState().setGenerationMode('image')
assert.equal(useStore.getState().params.seed, 202)
useStore.setState(original, true)
console.log('Store contracts passed: workspace races, late saves, progress lifecycle, LoRA phases, plugin identity, mode snapshots and workflow routing.')

// --- Persistence contracts (studioPersistence, no store instance) ---
let memory = new Map()
globalThis.localStorage = {
  getItem: key => (memory.has(key) ? memory.get(key) : null),
  setItem: (key, value) => memory.set(key, String(value)),
  removeItem: key => memory.delete(key),
  clear: () => memory.clear(),
}
assert.equal(loadModeSettings(), null, 'empty storage loads null')
saveModeSettings({
  generationMode: 'video',
  selectedModelPerMode: { video: 'ltx-2' },
  savedParamsPerMode: {
    video: { prompt: 'kept', video_source: '/app/uploads/ghost.mp4', video_prompt_type: 'OBN' },
  },
  savedLoraPerMode: {},
})
let loaded = loadModeSettings()
assert.equal(loaded.generationMode, 'video')
assert.equal(loaded.savedParamsPerMode.video.prompt, 'kept')
assert.equal(loaded.savedParamsPerMode.video.video_source, undefined, 'ephemeral media must not round-trip')
assert.equal(loaded.savedParamsPerMode.video.video_prompt_type, 'OBN', 'non-T flag preserved')
memory.clear()
saveModeSettings({
  generationMode: 'video',
  selectedModelPerMode: { video: 'wan' },
  savedParamsPerMode: {
    video: { video_prompt_type: 'TVG', video_source: '/x.mp4' },
  },
  savedLoraPerMode: {},
})
loaded = loadModeSettings()
assert.equal(loaded.savedParamsPerMode.video.video_prompt_type, 'TVG', 'internal T control letter preserved')
assert.equal(loaded.savedParamsPerMode.video.video_source, undefined)
memory.clear()
saveModeSettings({
  generationMode: 'video',
  selectedModelPerMode: { video: 'wan' },
  savedParamsPerMode: {
    video: { video_prompt_type: 'WAN2_T' },
  },
  savedLoraPerMode: {},
})
loaded = loadModeSettings()
assert.equal(loaded.savedParamsPerMode.video.video_prompt_type, 'WAN2_', 'trailing lone T flag stripped')
// Legacy save (no lora map) writes filename-keyed storage; load returns raw shape.
assert.equal(stripEphemeralParams({ video: { seed: 1, video_mask: '/m.png' } }).video.seed, 1)
assert.equal(stripEphemeralParams({ video: { video_mask: '/m.png' } }).video.video_mask, undefined)
// LoRA lora_id round-trip with a shared civitai id across two file versions.
memory.clear()
saveModeSettings({
  generationMode: 'video',
  selectedModelPerMode: { video: 'h3' },
  savedParamsPerMode: {},
  savedLoraPerMode: {
    video: {
      activated_loras: ['actor_v1.safetensors'],
      loras_multipliers: '0.70',
      loraWeights: { 'actor_v1.safetensors': [0.7], 'actor_v2.safetensors': [1.0] },
      availableLoras: ['actor_v1.safetensors', 'actor_v2.safetensors'],
    },
  },
}, { 'actor_v1.safetensors': 'civitai:555', 'actor_v2.safetensors': 'civitai:555' })
loaded = loadModeSettings()
assert.deepEqual(loaded.savedLoraPerMode.video.activated_loras, ['actor_v1.safetensors'])
assert.deepEqual([...loaded.savedLoraPerMode.video.availableLoras].sort(), ['actor_v1.safetensors', 'actor_v2.safetensors'])
assert.deepEqual(loaded.savedLoraPerMode.video.loraWeights['actor_v2.safetensors'], [1.0], 'multi-version A/B weights survive the round trip')
assert.equal(loaded.savedLoraPerMode.video.loras_multipliers, '0.70')
assert.equal(
  modeBlobToLoraIdKeyed({ activated_loras: ['x.safetensors'], loras_multipliers: '1', loraWeights: {}, availableLoras: [] }, { 'x.safetensors': 'civitai:1' }).activated_loras[0],
  'civitai:1')
// Sticky UI fields survive a later partial (LoRA-only) save.
memory.clear()
saveModeSettings({
  generationMode: 'image', selectedModelPerMode: {}, savedParamsPerMode: {}, savedLoraPerMode: {},
  savedPromptPerMode: { image: 'p' },
  studioVideoWorkflow: 'create', studioImageWorkflow: 'generate', audioSubMode: 'speech',
  selectedModelPerAudioSubMode: { speech: 'kugel' },
  h3OptimizationPreferences: { override_attention: 'sla' },
}, {})
saveModeSettings({ generationMode: 'image', selectedModelPerMode: {}, savedParamsPerMode: {}, savedLoraPerMode: {} }, {})
loaded = loadModeSettings()
assert.equal(loaded.studioVideoWorkflow, 'create')
assert.equal(loaded.audioSubMode, 'speech')
assert.equal(loaded.h3OptimizationPreferences.override_attention, 'sla')
// Sticky preferences: durable tools→image generation mode, server payload, failed-save resilience.
const persisted = []
const updates = []
persistStickyStudioPreferences(
  {
    generationMode: 'tools', toolsUpscaleMedia: 'image',
    selectedModelPerMode: {}, audioSubMode: 'speech',
    selectedModelPerAudioSubMode: {}, h3OptimizationPreferences: {},
    studioVideoWorkflow: 'create', studioImageWorkflow: 'generate',
    savedParamsPerMode: {}, savedLoraPerMode: {}, loraIdByFilename: {},
  },
  settings => persisted.push(settings.generationMode),
  async update => { updates.push(update); throw new Error('offline') },
)
persistStickyStudioPreferences(
  {
    generationMode: 'video', toolsUpscaleMedia: 'video',
    selectedModelPerMode: { video: 'h3' }, audioSubMode: 'music',
    selectedModelPerAudioSubMode: { music: 'ace_step_v1_5_xl_sft_lm_4b' }, h3OptimizationPreferences: {},
    studioVideoWorkflow: 'create', studioImageWorkflow: 'generate',
    savedParamsPerMode: {}, savedLoraPerMode: {}, loraIdByFilename: { 'a.safetensors': 'civitai:1' },
  },
  settings => persisted.push(settings.generationMode),
  async update => { updates.push(update) },
)
await new Promise(resolve => setTimeout(resolve, 0))
await new Promise(resolve => setTimeout(resolve, 0))
assert.deepEqual(persisted, ['image', 'video'], 'tools mode persists as its durable image workflow')
assert.equal(updates[0].generation_mode, 'image')
assert.equal(updates[1].generation_mode, 'video')
assert.equal(updates[1].selected_model_per_mode.video, 'h3')
assert.equal(updates[1].audio_sub_mode, 'music')
assert.equal(updates[1].selected_model_per_audio_sub_mode.music, 'ace_step_v1_5_xl_sft_lm_4b')
assert.equal(updates.length, 2, 'a failed preference save must not poison the queue')
console.log('Persistence contracts passed: ephemeral strip, legacy/lora_id shapes, sticky preservation and queued preference mirror.')

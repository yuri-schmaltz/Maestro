import assert from 'node:assert/strict'
import { build } from 'esbuild'

// Bundle the actual store so these contracts exercise its composition too.
const result = await build({
  stdin: {
    contents: `export { useStore } from './src/stores/useStore';
      export { trackAnalysisProgress } from './src/stores/analysisProgress';
      export { toggleLoraState, updateLoraWeight } from './src/stores/loraState';
      export { canonicalDirectorSkill } from './src/types';`,
    resolveDir: process.cwd(), loader: 'ts',
  },
  bundle: true, write: false, format: 'esm', platform: 'node',
  define: { 'import.meta.hot': 'undefined' },
})
const { useStore, trackAnalysisProgress, toggleLoraState, updateLoraWeight, canonicalDirectorSkill } =
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
useStore.setState({ activeWorkspace: 'fixture', directorSceneDescription: 'A quiet station' })
useStore.getState().applyWorkspaceSetup({
  video_model: 'fixture-video', image_model: 'fixture-image',
  music_source: 'generate', music_model: 'fixture-music',
  advanced: { video_film_grain_intensity: 0.2, video_num_inference_steps: 12, video_self_refiner: 2,
    image_spatial_upsampling: 'lanczos2', untrusted_extra: 'must not leak' },
  default_video_loras: { activated_loras: ['actor.safetensors'], loras_multipliers: '0.70',
    loraWeights: { 'actor.safetensors': [0.7] } },
})
await useStore.getState().startDirectorPipeline()
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
console.log('Store contracts passed: workspace races, late saves, progress lifecycle, LoRA phases and plugin identity.')

import assert from 'node:assert/strict'
import { build } from 'esbuild'
const result = await build({
  stdin: { contents: `export { editDirectorTimeline } from './src/lib/directorTimeline'; export { reviewSnapshot } from './src/lib/reviewSnapshot'; export { reorderWindowPrompts } from './src/lib/reorderWindowPrompts'; export { resolvedGenerationPlan } from './src/lib/generationPlan';`, resolveDir: process.cwd(), loader: 'ts' },
  bundle: true, write: false, format: 'esm', platform: 'node',
})
const { editDirectorTimeline, reviewSnapshot, reorderWindowPrompts, resolvedGenerationPlan } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`)
const file = new Blob(['reference'])
const action = () => 1
const source = { params: { prompt: 'original', refs: [{ name: 'Ana' }] }, file, action }
const frozen = reviewSnapshot(source)
source.params.prompt = 'changed'
source.params.refs[0].name = 'Other'
assert.equal(frozen.params.prompt, 'original')
assert.equal(frozen.params.refs[0].name, 'Ana')
assert.equal(frozen.file, file)
assert.equal(frozen.action, action)
const windows = [
  { index: 1, prompt: 'opening', start_frame: 0, end_frame: 100, start_seconds: 0, end_seconds: 4, opening_state: 'old', closing_state: 'old', injected_keyframes: ['first'] },
  { index: 2, prompt: 'ending', start_frame: 90, end_frame: 150, start_seconds: 3.6, end_seconds: 6, opening_state: 'old2', closing_state: 'old2', injected_keyframes: ['second'] },
]
const original = { windows, window_prompts: ['opening', 'ending'] }
const reordered = reorderWindowPrompts(original, 0, 1)
assert.deepEqual(reordered.window_prompts, ['ending', 'opening'])
assert.deepEqual(reordered.windows.map(w => [w.start_frame, w.end_frame]), [[0, 100], [90, 150]])
assert.deepEqual(reordered.windows[0].injected_keyframes, ['first'])
assert.equal(reordered.windows[0].opening_state, '')
assert.equal(reordered.windows[1].closing_state, '')
assert.equal(original.windows[0].prompt, 'opening')
assert.equal(reorderWindowPrompts(original, -1, 3), original)
const input = { generationMode: 'video', studioVideoWorkflow: 'frames', studioVideoEffectiveCreateRoute: 'generate', studioImageWorkflow: 'generate', params: { model_type: 'current-model', prompt: 'not approved' }, modelOptions: null, models: [], resolutionPreset: '720p', aspectRatio: '16:9', durationSeconds: 8, slidingWindowSeconds: 8, slidingWindowOverlap: 0, outputCount: 1 }
const restored = resolvedGenerationPlan(input, { id: 'saved', prepared: { params: { model_type: 'approved-model', prompt: 'approved prompt', seed: 42, video_length: 1, _review_ui: { generationMode: 'image', outputCount: 3 } } } })
assert.equal(restored.mode, 'image')
assert.equal(restored.modelType, 'approved-model')
assert.equal(restored.prompt, 'approved prompt')
assert.equal(restored.seed, 42)
assert.equal(restored.outputCount, 3)
console.log('Control gauntlet: snapshot isolation, file identity, reordered timing/assets, continuity invalidation and persisted review restoration passed.')

const timeline = [{ clip: { start: 0, end: 12 }, sources: [0] }, { clip: { start: 12, end: 20 }, sources: [1] }]
const split = editDirectorTimeline(timeline, { kind: 'split', index: 0, time: 4 })
assert.deepEqual(split.map(s => [s.clip.start, s.clip.end]), [[0, 4], [4, 12], [12, 20]])
assert.deepEqual(split.map(s => s.sources), [[0], [0], [1]])
const moved = editDirectorTimeline(split, { kind: 'boundary', index: 0, time: 6 })
assert.equal(moved[1].clip.start, 6)
const merged = editDirectorTimeline(moved, { kind: 'merge', index: 1 })
assert.deepEqual(merged[1].sources, [0, 1])
assert.equal(merged[1].clip.end, 20)
const divided = editDirectorTimeline(timeline, { kind: 'subdivide', seconds: 5 })
assert.equal(divided.length, 5)
assert.equal(divided.at(-1).clip.end, 20)
assert.throws(() => editDirectorTimeline(timeline, { kind: 'split', index: 0, time: 0 }))
assert.throws(() => editDirectorTimeline(timeline, { kind: 'subdivide', seconds: 0 }))
assert.equal(timeline[0].clip.end, 12)
console.log('Control gauntlet: scene splitting, boundary adjustment, merging, subdivision and source mapping passed.')

import type { PlannedClip } from '../types'

export interface SceneSlot { clip: PlannedClip; sources: number[] }
export type TimelineEdit = { kind: 'split' | 'boundary'; index: number; time: number } | { kind: 'merge'; index: number } | { kind: 'subdivide'; seconds: number }
const EPS = 0.001
export function editDirectorTimeline(slots: SceneSlot[], edit: TimelineEdit): SceneSlot[] {
  const result = structuredClone(slots)
  if (!result.length) throw new Error('Analyze the audio first.')
  const cut = (index: number, time: number, boundary = false) => {
    const left = result[index]
    const right = boundary ? result[index + 1] : left
    if (!left || !right || !Number.isFinite(time) || time - left.clip.start < 0.1 - EPS || right.clip.end - time < 0.1 - EPS)
      throw new Error('Choose a cut inside the interval, leaving at least 0.1 seconds on each side.')
    const before = structuredClone(left)
    const after = structuredClone(right)
    before.clip.end = time
    after.clip.start = time
    result.splice(index, boundary ? 2 : 1, before, after)
  }
  if (edit.kind === 'split' || edit.kind === 'boundary') cut(edit.index, edit.time, edit.kind === 'boundary')
  else if (edit.kind === 'merge') {
    const a = result[edit.index], b = result[edit.index + 1]
    if (!a || !b) throw new Error('Select a scene with a following scene.')
    a.clip.end = b.clip.end
    a.sources = [...new Set([...a.sources, ...b.sources])]
    result.splice(edit.index + 1, 1)
  } else if (edit.kind === 'subdivide') {
    if (!Number.isFinite(edit.seconds) || edit.seconds < 0.1) throw new Error('Duration must be at least 0.1 seconds.')
    const count = result.reduce((sum, s) => sum + Math.ceil((s.clip.end - s.clip.start) / edit.seconds), 0)
    if (count > 200) throw new Error('Use a longer duration: maximum 200 scenes.')
    return result.flatMap(slot => {
      const count = Math.ceil((slot.clip.end - slot.clip.start) / edit.seconds)
      return Array.from({ length: count }, (_, i) => ({ sources: [...slot.sources], clip: { ...slot.clip,
        start: slot.clip.start + (slot.clip.end - slot.clip.start) * i / count,
        end: slot.clip.start + (slot.clip.end - slot.clip.start) * (i + 1) / count,
      } }))
    })
  }
  if (result.length > 200) throw new Error('Maximum 200 scenes.')
  return result
}

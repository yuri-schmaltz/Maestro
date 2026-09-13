import type { GenerationMode, ModelOptions } from '../types'

export function loraPhaseCount(
  modelOptions: ModelOptions | null,
  generationMode: GenerationMode,
  editSubMode: string,
): number {
  if (generationMode === 'avatar' && editSubMode === 'recast') return 1
  return Math.max(1, modelOptions?.guidance_max_phases ?? 1)
}

export function serializeLoraMultipliers(
  activatedLoras: string[],
  weights: Record<string, number[]>,
  phases: number,
): string {
  return activatedLoras.map(filename => {
    const values = weights[filename] || [1.0]
    return Array.from(
      { length: phases },
      (_, index) => values[index] ?? values[values.length - 1] ?? 1.0,
    ).map(value => value.toFixed(2)).join(';')
  }).join(' ')
}

export interface ToggledLoraState {
  activatedLoras: string[]
  weights: Record<string, number[]>
  multipliers: string
  removed: boolean
}

export function toggleLoraState(
  activatedLoras: string[],
  weights: Record<string, number[]>,
  filename: string,
  phases: number,
): ToggledLoraState {
  const nextActivated = [...activatedLoras]
  const nextWeights = { ...weights }
  const index = nextActivated.indexOf(filename)
  const removed = index >= 0
  if (removed) {
    nextActivated.splice(index, 1)
    delete nextWeights[filename]
  } else {
    nextActivated.push(filename)
    nextWeights[filename] = Array(phases).fill(1.0)
  }
  return {
    activatedLoras: nextActivated,
    weights: nextWeights,
    multipliers: serializeLoraMultipliers(nextActivated, nextWeights, phases),
    removed,
  }
}

export function updateLoraWeight(
  activatedLoras: string[],
  weights: Record<string, number[]>,
  filename: string,
  phaseIndex: number,
  value: number,
  phases: number,
): { weights: Record<string, number[]>; multipliers: string } | null {
  const current = weights[filename]
  if (!current || phaseIndex < 0 || phaseIndex >= phases) return null
  const nextWeights = { ...weights }
  nextWeights[filename] = Array.from(
    { length: phases },
    (_, index) => current[index] ?? current[current.length - 1] ?? 1.0,
  )
  nextWeights[filename][phaseIndex] = value
  return {
    weights: nextWeights,
    multipliers: serializeLoraMultipliers(activatedLoras, nextWeights, phases),
  }
}

import type { StudioPreferenceUpdate } from '../api/client'
import type { GenerationMode, StudioImageWorkflow, StudioVideoWorkflow } from '../types'

export interface StudioPreferenceState {
  generationMode: GenerationMode
  toolsUpscaleMedia: 'image' | 'video'
  selectedModelPerMode: Partial<Record<GenerationMode, string>>
  studioVideoWorkflow: StudioVideoWorkflow
  studioImageWorkflow: StudioImageWorkflow
  audioSubMode: NonNullable<StudioPreferenceUpdate['audio_sub_mode']>
  selectedModelPerAudioSubMode: Record<string, string>
  h3OptimizationPreferences: Record<string, unknown>
}

export interface StudioPreferencePayload {
  generation_mode: Exclude<GenerationMode, 'tools'>
  studio_video_workflow: StudioVideoWorkflow
  studio_image_workflow: StudioImageWorkflow
  audio_sub_mode: NonNullable<StudioPreferenceUpdate['audio_sub_mode']>
  selected_model_per_mode: Record<string, string>
  selected_model_per_audio_sub_mode: Record<string, string>
  h3_optimizations: Record<string, unknown>
}

export function durableGenerationMode(state: Pick<StudioPreferenceState, 'generationMode' | 'toolsUpscaleMedia'>): Exclude<GenerationMode, 'tools'> {
  if (state.generationMode !== 'tools') return state.generationMode
  return state.toolsUpscaleMedia === 'image' ? 'image' : 'video'
}

export function buildStudioPreferencePayload(state: StudioPreferenceState): StudioPreferencePayload {
  const generationMode = durableGenerationMode(state)
  return {
    generation_mode: generationMode,
    studio_video_workflow: state.studioVideoWorkflow,
    studio_image_workflow: state.studioImageWorkflow,
    audio_sub_mode: state.audioSubMode,
    selected_model_per_mode: Object.fromEntries(
      Object.entries(state.selectedModelPerMode).filter(([, model]) => Boolean(model)),
    ),
    selected_model_per_audio_sub_mode: Object.fromEntries(
      Object.entries(state.selectedModelPerAudioSubMode).filter(([, model]) => Boolean(model)),
    ),
    h3_optimizations: state.h3OptimizationPreferences,
  }
}

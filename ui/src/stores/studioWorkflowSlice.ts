import type { StateCreator } from 'zustand'
import type { StudioImageWorkflow, StudioVideoWorkflow } from '../types'
import type { AppState } from './useStore'

export interface StudioWorkflowDependencies {
  persist: () => void
}

export type StudioWorkflowSlice = Pick<AppState,
  'studioVideoWorkflow' | 'studioImageWorkflow' | 'setStudioVideoWorkflow' | 'setStudioImageWorkflow'
>

/** Studio workflow routing state. Mode snapshots remain in the root store. */
export const createStudioWorkflowSlice = (
  set: Parameters<StateCreator<AppState, [], [], StudioWorkflowSlice>>[0],
  get: Parameters<StateCreator<AppState, [], [], StudioWorkflowSlice>>[1],
  dependencies: StudioWorkflowDependencies,
): StudioWorkflowSlice => ({
  studioVideoWorkflow: 'frames' as StudioVideoWorkflow,

  setStudioVideoWorkflow: (workflow) => {
    set({ studioVideoWorkflow: workflow })

    if (workflow === 'frames' || workflow === 'references' || workflow === 'extend' || workflow === 'blend') {
      if (get().generationMode !== 'video') get().setGenerationMode('video')
      const imageMode = workflow === 'extend' ? 3 : workflow === 'blend' ? 4 : 0
      if (Number(get().params.image_mode) !== imageMode) {
        get().setParam('image_mode', imageMode)
      }
      set(state => ({
        studioVideoWorkflow: workflow,
        params: { ...state.params, _studio_video_workflow: workflow },
      }))
      if (workflow === 'frames' || workflow === 'references') {
        get().reconcileStudioVideoCreateRoute(
          `${workflow === 'references' ? 'References' : 'Frames'} workflow opened`,
        )
      }
      dependencies.persist()
      return
    }

    if (workflow === 'upscale') {
      set(state => ({
        toolsTool: 'upscale',
        toolsUpscaleMedia: 'video',
        ...(state.toolsUpscaleMedia === 'image'
          ? { toolsSourcePath: null, toolsSourceName: null, toolsSourceUrl: null }
          : {}),
      }))
      if (get().generationMode !== 'tools') get().setGenerationMode('tools')
      dependencies.persist()
      return
    }

    if (workflow === 'film_grain') {
      set(state => ({
        toolsTool: 'film_grain',
        toolsUpscaleMedia: 'video',
        filmGrainIntensity: state.filmGrainIntensity > 0 ? state.filmGrainIntensity : 0.15,
        ...(state.toolsUpscaleMedia === 'image'
          ? { toolsSourcePath: null, toolsSourceName: null, toolsSourceUrl: null }
          : {}),
      }))
      if (get().generationMode !== 'tools') get().setGenerationMode('tools')
      dependencies.persist()
      return
    }

    const editMode: AppState['editSubMode'] = workflow === 'prompt_edit'
      ? 'edit_anything'
      : workflow === 'repaint'
        ? 'restyle'
        : workflow
    if (get().generationMode !== 'avatar') get().setGenerationMode('avatar')
    get().setEditSubMode(editMode)
    dependencies.persist()
  },

  studioImageWorkflow: 'generate' as StudioImageWorkflow,

  setStudioImageWorkflow: (workflow) => {
    if (workflow === 'upscale') {
      set(state => ({
        studioImageWorkflow: 'upscale',
        toolsTool: 'upscale',
        toolsUpscaleMedia: 'image',
        ...(state.toolsUpscaleMedia === 'video'
          ? { toolsSourcePath: null, toolsSourceName: null, toolsSourceUrl: null }
          : {}),
      }))
      if (get().generationMode !== 'tools') get().setGenerationMode('tools')
      dependencies.persist()
      return
    }

    if (get().generationMode !== 'image') get().setGenerationMode('image')
    set(state => ({
      studioImageWorkflow: workflow,
      params: {
        ...state.params,
        image_mode: workflow === 'inpaint' || workflow === 'outpaint' ? 2 : 1,
        _studio_image_workflow: workflow,
      },
    }))
    dependencies.persist()
  },
})

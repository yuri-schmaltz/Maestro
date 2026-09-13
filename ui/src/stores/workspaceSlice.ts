import type { StateCreator } from 'zustand'
import * as api from '../api/client'
import type {
  AppSection,
  AspectRatio,
  GenerationMode,
  ResolutionPreset,
} from '../types'
import type { AppState } from './useStore'

/** Workspace state and actions composed into the root store. */
export const createWorkspaceSlice: StateCreator<AppState, [], [], Partial<AppState>> = (set, get) => ({
  workspaces: [],
  activeWorkspace: 'default',
  activeWorkspaceSetup: null,
  activeWorkspaceSetupLoading: false,
  browsingUploads: false,

  loadWorkspaceSetup: async (name) => {
    if (!name || name === 'default') {
      set({ activeWorkspaceSetup: null, activeWorkspaceSetupLoading: false })
      return
    }
    set({ activeWorkspaceSetupLoading: true })
    try {
      const setup = await api.fetchWorkspaceSetup(name)
      set({ activeWorkspaceSetup: setup, activeWorkspaceSetupLoading: false })
      get().applyWorkspaceSetup(setup)
    } catch (error) {
      console.error('Failed to load workspace setup:', error)
      set({ activeWorkspaceSetup: null, activeWorkspaceSetupLoading: false })
    }
  },

  saveWorkspaceSetup: async (setup) => {
    const name = get().activeWorkspace
    if (!name || name === 'default') {
      throw new Error('The default workspace cannot hold a custom project setup.')
    }
    const persisted = await api.saveWorkspaceSetup(name, setup)
    set({ activeWorkspaceSetup: persisted })
    get().applyWorkspaceSetup(persisted)
  },

  applyWorkspaceSetup: (setup) => {
    const patch: {
      directorAspectRatio?: AspectRatio
      directorResolution?: ResolutionPreset
      directorSeamless?: boolean
      directorAutoMode?: boolean
      selectedModelPerMode?: Partial<Record<GenerationMode, string>>
      directorMusicSource?: 'upload' | 'generate' | null
      directorMusicModel?: string
      directorAdvancedDefaults?: Record<string, unknown>
    } = {}
    if (setup.aspect_ratio) patch.directorAspectRatio = setup.aspect_ratio as AspectRatio
    if (setup.resolution) patch.directorResolution = setup.resolution as ResolutionPreset
    if (typeof setup.seamless === 'boolean') patch.directorSeamless = setup.seamless
    if (typeof setup.auto_mode === 'boolean') patch.directorAutoMode = setup.auto_mode

    let nextModels: Partial<Record<GenerationMode, string>> | undefined
    if (setup.video_model) nextModels = { ...(get().selectedModelPerMode || {}), video: setup.video_model }
    if (setup.image_model) nextModels = { ...(nextModels || get().selectedModelPerMode || {}), image: setup.image_model }
    if (nextModels) patch.selectedModelPerMode = nextModels
    if (setup.music_source === 'upload' || setup.music_source === 'generate') {
      patch.directorMusicSource = setup.music_source
    }
    if (setup.music_model) patch.directorMusicModel = setup.music_model
    if (setup.advanced && typeof setup.advanced === 'object') {
      patch.directorAdvancedDefaults = { ...setup.advanced }
    }
    if (Object.keys(patch).length > 0) set(patch)

    const applyLoraDefaults = (mode: 'image' | 'video', value: unknown) => {
      if (!value || typeof value !== 'object') return
      const blob = value as {
        activated_loras?: unknown
        loras_multipliers?: unknown
        loraWeights?: unknown
        availableLoras?: unknown
      }
      const activated = Array.isArray(blob.activated_loras) ? blob.activated_loras as string[] : []
      const multipliers = typeof blob.loras_multipliers === 'string' ? blob.loras_multipliers : ''
      const weights = blob.loraWeights && typeof blob.loraWeights === 'object'
        ? blob.loraWeights as Record<string, number[]>
        : {}
      const available = Array.isArray(blob.availableLoras) ? blob.availableLoras as string[] : []
      get().directorSetLora(mode, activated, multipliers, weights, available)
    }
    applyLoraDefaults('image', setup.default_image_loras)
    applyLoraDefaults('video', setup.default_video_loras)
  },

  loadWorkspaces: async () => {
    try {
      const data = await api.fetchWorkspaces()
      const realWorkspaces = data.workspaces.filter(workspace => workspace.name !== 'default')
      const activeIsReal = data.active !== 'default'
      const current = get()
      const previousActive = current.activeWorkspace
      if (realWorkspaces.length === 0 && !activeIsReal && current.appSection !== 'configurations') {
        set({ workspaces: data.workspaces, activeWorkspace: data.active, appSection: 'projects' as AppSection })
      } else {
        set({ workspaces: data.workspaces, activeWorkspace: data.active })
      }
      if (activeIsReal && data.active !== previousActive) {
        get().loadWorkspaceSetup(data.active)
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error)
    }
  },

  switchWorkspace: async (name) => {
    if (name === '__uploads__') {
      set({ browsingUploads: true, outputs: [], outputsTotal: 0, selectedOutput: 0, selectedOutputMeta: null })
      get().loadOutputs()
      return
    }
    try {
      await api.setActiveWorkspace(name)
      set({ browsingUploads: false, activeWorkspace: name, outputs: [], outputsTotal: 0, selectedOutput: 0, selectedOutputMeta: null })
      get().loadOutputs()
      get().loadWorkspaces()
      get().loadWorkspaceSetup(name)
    } catch (error) {
      console.error('Failed to switch workspace:', error)
    }
  },

  createWorkspace: async (name) => {
    try {
      await api.createWorkspace(name)
      await api.setActiveWorkspace(name)
      set({ browsingUploads: false, activeWorkspace: name, outputs: [], outputsTotal: 0, selectedOutput: 0, selectedOutputMeta: null })
      set({ activeWorkspaceSetup: null })
      get().loadOutputs()
      get().loadWorkspaces()
    } catch (error) {
      console.error('Failed to create workspace:', error)
      throw error
    }
  },

  deleteWorkspace: async (name) => {
    const result = await api.deleteWorkspace(name)
    if (result.switched_to_default) {
      set({ browsingUploads: false, activeWorkspace: 'default', outputs: [], outputsTotal: 0, selectedOutput: 0, selectedOutputMeta: null })
      get().loadOutputs()
    }
    get().loadWorkspaces()
  },
})

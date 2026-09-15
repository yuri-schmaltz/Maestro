// Studio/Director post-processing knobs — split out of useStore.ts root.
//
// `setParam`/`setParams` already live in studioModeSlice.ts (the actual
// per-mode params mutation). What stayed in the root was the *director-
// only* post-processing surface: spatial upsampling, film-grain and the
// H3 self-refiner level, separated for image and video. These don't share
// invariants with the per-mode Studio params (they apply per-take, not
// per-mode), and they have no persistence hook — the Director pipeline
// just reads them at submit time.
//
// Extracted as a StateCreator so the root `useStore` composes it via the
// same pattern as `studioModelSlice` / `studioModeSlice` etc. State and
// action names are kept identical to the public AppState shape, so the
// root facade exposes them as `useStore.getState().setDirectorXxx(...)`
// without callers needing to migrate.

export type DirectorFinishingSlice = {
  // Image post-processing (per-take)
  directorImageSpatialUpsampling: string
  setDirectorImageSpatialUpsampling: (v: string) => void
  directorImageFilmGrainIntensity: number
  setDirectorImageFilmGrainIntensity: (v: number) => void
  directorImageFilmGrainSaturation: number
  setDirectorImageFilmGrainSaturation: (v: number) => void

  // Video post-processing (per-take)
  directorVideoSpatialUpsampling: string
  setDirectorVideoSpatialUpsampling: (v: string) => void
  directorVideoFilmGrainIntensity: number
  setDirectorVideoFilmGrainIntensity: (v: number) => void
  directorVideoFilmGrainSaturation: number
  setDirectorVideoFilmGrainSaturation: (v: number) => void
  directorVideoSelfRefiner: number
  setDirectorVideoSelfRefiner: (v: number) => void

  // Audio post-processing (per-take)
  directorAudioScale: number
  setDirectorAudioScale: (v: number) => void
}

export const createDirectorFinishingSlice = (
  set: (partial: Partial<DirectorFinishingSlice>) => void,
): DirectorFinishingSlice => ({
  directorImageSpatialUpsampling: '',
  setDirectorImageSpatialUpsampling: (v) => set({ directorImageSpatialUpsampling: v }),
  directorImageFilmGrainIntensity: 0,
  setDirectorImageFilmGrainIntensity: (v) => set({ directorImageFilmGrainIntensity: v }),
  directorImageFilmGrainSaturation: 0.5,
  setDirectorImageFilmGrainSaturation: (v) => set({ directorImageFilmGrainSaturation: v }),

  directorVideoSpatialUpsampling: '',
  setDirectorVideoSpatialUpsampling: (v) => set({ directorVideoSpatialUpsampling: v }),
  directorVideoFilmGrainIntensity: 0,
  setDirectorVideoFilmGrainIntensity: (v) => set({ directorVideoFilmGrainIntensity: v }),
  directorVideoFilmGrainSaturation: 0.5,
  setDirectorVideoFilmGrainSaturation: (v) => set({ directorVideoFilmGrainSaturation: v }),
  directorVideoSelfRefiner: 0,
  setDirectorVideoSelfRefiner: (v) => set({ directorVideoSelfRefiner: v }),

  directorAudioScale: 1.0,
  setDirectorAudioScale: (v) => set({ directorAudioScale: v }),
})

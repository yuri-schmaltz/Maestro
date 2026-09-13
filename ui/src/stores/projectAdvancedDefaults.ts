import type { AppState } from './useStore'

const upsamplers = new Set(['', 'lanczos1.5', 'lanczos2'])
const numberIn = (value: unknown, fallback: number, min: number, max: number) =>
  typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max ? value : fallback
const upsampler = (value: unknown) => typeof value === 'string' && upsamplers.has(value) ? value : ''

/** Hydrate known Director controls; later per-take edits and restored snapshots win. */
export function projectAdvancedDefaults(
  value: Record<string, unknown>,
  state: AppState,
  videoModel: string,
) {
  const steps = { ...state.directorVideoInferenceStepsByModel }
  const configuredSteps = numberIn(value.video_num_inference_steps, 0, 1, 50)
  if (Number.isInteger(configuredSteps) && configuredSteps > 0) steps[videoModel] = configuredSteps
  else delete steps[videoModel]
  return {
    directorAdvancedDefaults: { ...value },
    directorImageSpatialUpsampling: upsampler(value.image_spatial_upsampling),
    directorVideoSpatialUpsampling: upsampler(value.video_spatial_upsampling),
    directorImageFilmGrainIntensity: numberIn(value.image_film_grain_intensity, 0, 0, 1),
    directorImageFilmGrainSaturation: numberIn(value.image_film_grain_saturation, 0.5, 0, 1),
    directorVideoFilmGrainIntensity: numberIn(value.video_film_grain_intensity, 0, 0, 1),
    directorVideoFilmGrainSaturation: numberIn(value.video_film_grain_saturation, 0.5, 0, 1),
    directorVideoSelfRefiner: ([0, 1, 2].includes(Number(value.video_self_refiner)) ? Number(value.video_self_refiner) : 0),
    directorVideoInferenceStepsByModel: steps,
    directorH3TurboModeByModel: {
      ...state.directorH3TurboModeByModel,
      [videoModel]: value.minimax_h3_turbo_mode === true,
    },
  }
}

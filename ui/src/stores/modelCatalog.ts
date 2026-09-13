import type { ApiModel } from '../api/client'
import type { ModelDef } from '../types'

/** Normalize backend model records without discarding Director metadata. */
export function normalizeBackendModels(models: ApiModel[]): ModelDef[] {
  return models.map(model => ({
    ...model,
    guidance_max_phases: model.guidance_max_phases ?? 1,
    fps: model.fps ?? 16,
    is_downloaded: model.is_downloaded ?? false,
    nsfw_only: model.nsfw_only ?? false,
  }))
}

/** Compose server models with UI-only virtual models in one stable boundary. */
export function composeModelCatalog(
  backendModels: ApiModel[],
  virtualModels: ModelDef[],
): ModelDef[] {
  return [...normalizeBackendModels(backendModels), ...virtualModels]
}

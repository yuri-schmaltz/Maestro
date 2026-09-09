import type {
  AspectRatio,
  GenerationMode,
  GenerateParams,
  ModelDef,
  ModelOptions,
  ResolutionPreset,
  StudioImageWorkflow,
  StudioVideoEffectiveCreateRoute,
  StudioVideoWorkflow,
} from '../types'
import {
  continuationFirstWindowFrames,
  durationWindowPlan,
} from './durationPlanning'

/**
 * P0 "What will be generated" plan review. Everything in this module is a
 * pure function of a state snapshot (plus one flag about whether the AI
 * prompt planner was forced to defer to the GPU queue). It exists so the
 * Studio Generate path can show the user an honest pre-submit summary of
 * the request it is about to freeze — the same model, route, resolution,
 * frames, and enhancement decisions that startGeneration silently derives
 * at submit time.
 */

export type ReviewAction = 'generate' | 'queue'

export interface ReviewEnhanceState {
  /** Auto single-pass prompt enhancement applies to this setup. */
  automatic: boolean
  /** The effective prompt has already been AI-enhanced. */
  alreadyEnhanced: boolean
  /** Enhancement was deferred to the server (a render owns the GPU). */
  deferred: boolean
  /** Prompt is empty, so nothing to plan. */
  empty: boolean
}

export interface ReviewPlan {
  reviewId?: string
  resolvedParams?: Record<string, unknown>
  originalPrompt?: string
  windowPrompts?: string[]
  mode: GenerationMode | 'tools'
  workflowLabel: string
  routeLabel: string | null
  routeKind: StudioVideoEffectiveCreateRoute | null
  modelType: string
  modelLabel: string
  architecture: string
  resolutionPreset: ResolutionPreset
  aspectRatio: AspectRatio
  resolutionToken: string
  resolutionLabel: string
  resolutionApprox: boolean
  fps: number
  durationSeconds: number
  windowSeconds: number
  overlapSeconds: number
  windowCount: number
  generatedSeconds: number
  requestedFrames: number
  framesMin: number
  framesMax: number | null
  framesApprox: boolean
  steps: number
  cfg: number
  seed: number
  loras: string[]
  outputCount: number
  multiWindowEnabled: boolean
  promptModeLabel: string
  prompt: string
  promptWordCount: number
  enhance: ReviewEnhanceState
  warnings: string[]
}

/** Everything the plan builder reads from the store. Pass `get()`/an
 *  AppState snapshot — structural typing keeps the two decoupled. */
export interface GenerationPlanInput {
  generationMode: GenerationMode
  studioVideoWorkflow: StudioVideoWorkflow
  studioVideoEffectiveCreateRoute: StudioVideoEffectiveCreateRoute
  studioImageWorkflow: StudioImageWorkflow
  params: GenerateParams
  modelOptions: ModelOptions | null
  models: ModelDef[]
  resolutionPreset: ResolutionPreset
  aspectRatio: AspectRatio
  durationSeconds: number
  slidingWindowSeconds: number
  slidingWindowOverlap: number
  outputCount: number
}

export interface BuildGenerationPlanOptions {
  /** AI prompt planning could not run now and will run on the server. */
  enhanceDeferred?: boolean
}

/**
 * Model-selected ("auto_*") resolution tokens resolve to different real
 * pixel canvases per architecture. Publish the known tables so the review
 * panel can surface actual dimensions next to the symbolic preset; unknown
 * architectures fall back to an honest "model-chosen" label instead of a
 * fabricated number.
 */
const H3_AUTO_PIXELS: Record<string, string> = {
  auto_480p: '864x480',
  auto_540p: '960x544',
  auto_720p: '1280x704',
  auto_768p: '1344x768',
  auto_1080p: '1920x1088',
}

const LTX_AUTO_PIXELS: Record<string, string> = {
  auto_480p: '896x512',
  auto_540p: '1024x576',
  auto_720p: '1280x704',
  auto_1080p: '1920x1088',
}

function autoPixelTable(architecture: string): Record<string, string> | null {
  const arch = architecture.toLowerCase()
  if (arch.startsWith('minimax_h3')) return H3_AUTO_PIXELS
  if (arch.startsWith('ltx')) return LTX_AUTO_PIXELS
  return null
}

function wordCount(value: string): number {
  return (value.match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || []).length
}

const ROUTE_LABELS: Record<StudioVideoEffectiveCreateRoute, string> = {
  generate: 'Text-to-video',
  guided: 'Frame-guided',
  audio: 'Audio-driven',
  omni: 'Reference (Omni)',
}

export function buildGenerationPlan(
  input: GenerationPlanInput,
  options: BuildGenerationPlanOptions = {},
): ReviewPlan {
  const {
    generationMode,
    studioVideoWorkflow,
    studioVideoEffectiveCreateRoute,
    studioImageWorkflow,
    params,
    modelOptions,
    models,
    resolutionPreset,
    aspectRatio,
    durationSeconds,
    slidingWindowSeconds,
    slidingWindowOverlap,
    outputCount,
  } = input
  const warnings: string[] = []

  const modelDef = models.find(model => model.model_type === params.model_type)
  const modelLabel = modelDef?.name || params.model_type || 'Model'
  const architecture = String(
    modelOptions?.architecture || modelDef?.architecture || '',
  )
  const isLtxPromptModel = modelOptions?.multi_window_sequence_controls === true
  const isH3PromptModel = architecture.startsWith('minimax_h3')
  const fps = modelOptions?.fps ?? 16
  const framesMin = Math.max(1, modelOptions?.frames_minimum ?? fps)
  const framesMax = modelOptions?.frames_maximum ?? null

  const isPrimaryCreate = generationMode === 'video'
    && (studioVideoWorkflow === 'frames' || studioVideoWorkflow === 'references')
    && Number(params.image_mode) === 0
  const routeLabel = isPrimaryCreate
    ? (ROUTE_LABELS[studioVideoEffectiveCreateRoute] ?? null)
    : null
  const routeKind = isPrimaryCreate ? studioVideoEffectiveCreateRoute : null

  let workflowLabel = 'Generation'
  if (generationMode === 'video') {
    workflowLabel = studioVideoWorkflow === 'extend'
      ? 'Video Extend'
      : studioVideoWorkflow === 'blend'
        ? 'Blend video'
        : studioVideoWorkflow === 'references'
          ? 'References'
          : galleryWorkflowLabel(studioVideoWorkflow, studioVideoEffectiveCreateRoute)
  } else if (generationMode === 'image') {
    workflowLabel = imageWorkflowLabel(studioImageWorkflow)
  } else if (generationMode === 'audio') {
    workflowLabel = 'Audio'
  } else if (generationMode === 'avatar') {
    workflowLabel = 'Edit (Transform)'
  } else if (generationMode === 'tools') {
    workflowLabel = 'Post-processing'
  }

  // Resolution — always resolve the token to a pixel label when possible.
  const resolutionToken = typeof params.resolution === 'string' && params.resolution
    ? params.resolution
    : resolutionPreset === 'auto'
      ? 'auto'
      : `auto_${resolutionPreset}`
  let resolutionLabel = resolutionToken
  let resolutionApprox = false
  const explicitPixels = resolutionToken.match(/^(\d{2,5})x(\d{2,5})$/)
  if (explicitPixels) {
    resolutionLabel = resolutionToken
  } else if (resolutionToken === 'auto') {
    resolutionLabel = 'Model default'
  } else {
    const table = autoPixelTable(architecture)
    const pixels = table?.[resolutionToken]
    if (pixels) {
      resolutionLabel = `${resolutionPreset} (≈${pixels})`
      resolutionApprox = true
    } else {
      resolutionLabel = `${resolutionToken.replace('auto_', '')} (model-chosen)`
      resolutionApprox = true
    }
    if (resolutionApprox) {
      warnings.push(`Resolution "${resolutionToken}" is chosen by the model at render time; ${resolutionLabel.includes('≈') ? 'the ≈ dimension is the model family default' : 'exact pixels depend on the model'}.`)
    }
  }

  // Duration → windows → frames, reusing the exact submit-time geometry.
  const overlapSeconds = slidingWindowOverlap / fps
  const discardSeconds = (modelOptions?.sliding_window_defaults?.discard_last_frames ?? 0) / fps
  const firstWindowSeconds = (
    studioVideoWorkflow === 'extend'
    && modelOptions?.sliding_window === true
  )
    ? continuationFirstWindowFrames(
        Math.round(slidingWindowSeconds * fps),
        slidingWindowOverlap,
      ) / fps
    : slidingWindowSeconds
  const windowPlan = durationWindowPlan(
    durationSeconds,
    slidingWindowSeconds,
    overlapSeconds,
    discardSeconds,
    firstWindowSeconds,
  )
  const requestedFrames = Math.max(
    framesMin,
    Math.min(
      framesMax ?? Math.max(framesMin, Math.round(durationSeconds * fps)),
      Math.round(durationSeconds * fps),
    ),
  )
  const framesApprox = requestedFrames !== Math.round(durationSeconds * fps)

  // Multi-window + prompt planning mode (mirrors startGeneration).
  const promptMode = isLtxPromptModel
    ? params.ltx_window_prompt_mode
    : params.minimax_h3_sequence_prompt_mode
  const multiWindowEnabled = isLtxPromptModel
    ? params.ltx_multi_window === true
    : (
      isH3PromptModel
      && (
        modelOptions?.omni_reference === true
        || routeKind === 'omni'
      )
    )
      ? params.minimax_h3_reference_sequence === true
      : params.minimax_h3_multi_window === true
  const promptModeLabel = multiWindowEnabled
    ? (promptMode === 'manual'
        ? 'Manual (each line = one window)'
        : promptMode === 'creative'
          ? 'AI plan — Creative'
          : 'AI plan — Faithful/Auto')
    : 'Full prompt'

  const alreadyEnhanced = isLtxPromptModel
    ? Boolean(typeof params._ltx_original_prompt === 'string' && params._ltx_original_prompt.trim())
    : Boolean(typeof params._h3_original_prompt === 'string' && params._h3_original_prompt.trim())

  const prompt = String(params.prompt || '').trim()
  const promptEmpty = prompt.length === 0
  const usesMultiplePasses = multiWindowEnabled && windowPlan.windowCount > 1
  const enhanceAutomatic = (
    !promptEmpty
    && generationMode === 'video'
    && (isH3PromptModel || isLtxPromptModel)
    && (promptMode === 'auto' || promptMode === 'creative')
    && !usesMultiplePasses
    && !alreadyEnhanced
  )
  const enhanceDeferred = enhanceAutomatic && options.enhanceDeferred === true

  if (windowPlan.windowCount > 1) {
    warnings.push(
      `${windowPlan.windowCount} native windows (${slidingWindowSeconds.toFixed(1)}s each at ${fps} fps) will be planned and joined end-to-end.`,
    )
  }
  if (enhanceDeferred) {
    warnings.push('AI prompt planning will run when this job reaches the GPU — you are confirming the raw idea now.')
  }

  const loras = (Array.isArray(params.activated_loras) ? params.activated_loras : [])
    .filter(name => typeof name === 'string' && name.trim())

  return {
    mode: generationMode === 'avatar' ? 'avatar' : generationMode,
    workflowLabel,
    routeLabel,
    routeKind,
    modelType: params.model_type,
    modelLabel,
    architecture,
    resolutionPreset,
    aspectRatio,
    resolutionToken,
    resolutionLabel,
    resolutionApprox,
    fps,
    durationSeconds,
    windowSeconds: slidingWindowSeconds,
    overlapSeconds,
    windowCount: windowPlan.windowCount,
    generatedSeconds: windowPlan.generatedSeconds,
    requestedFrames,
    framesMin,
    framesMax,
    framesApprox,
    steps: params.num_inference_steps ?? modelOptions?.default_num_inference_steps ?? 8,
    cfg: params.guidance_scale ?? modelOptions?.default_guidance_scale ?? 1.0,
    seed: params.seed ?? -1,
    loras,
    outputCount: Math.max(1, outputCount || 1),
    multiWindowEnabled,
    promptModeLabel,
    prompt,
    promptWordCount: wordCount(prompt),
    enhance: {
      automatic: enhanceAutomatic,
      alreadyEnhanced,
      deferred: enhanceDeferred,
      empty: promptEmpty,
    },
    warnings,
  }
}

function galleryWorkflowLabel(
  workflow: StudioVideoWorkflow,
  route: StudioVideoEffectiveCreateRoute | null,
): string {
  if (workflow === 'frames') return route === null ? 'Frames' : ROUTE_LABELS[route]
  return workflow
}

function imageWorkflowLabel(workflow: StudioImageWorkflow): string {
  switch (workflow) {
    case 'generate': return 'Generate'
    case 'inpaint': return 'Inpaint'
    case 'outpaint': return 'Outpaint'
    case 'upscale': return 'Upscale'
    default: return 'Image'
  }
}
/** Build the review from persisted request metadata, also after reconnect. */
export function resolvedGenerationPlan(input: GenerationPlanInput, result: {
  id: string
  prepared: { params: Record<string, unknown> }
}): ReviewPlan {
  const effective = result.prepared.params
  const ui = (effective._review_ui || {}) as Partial<GenerationPlanInput>
  const plan = buildGenerationPlan({ ...input, ...ui, params: { ...input.params, ...effective } })
  const windows = effective.h3_window_plan as { planning_warnings?: string[] } | undefined
  plan.warnings.push(...(windows?.planning_warnings || []), ...((effective._review_notes || []) as string[]))
  plan.reviewId = result.id
  plan.resolvedParams = effective
  plan.originalPrompt = String(effective._review_original_prompt || effective._h3_original_prompt || effective._ltx_original_prompt || effective.prompt || '')
  plan.windowPrompts = (effective.h3_window_prompts || effective.ltx_window_prompts || []) as string[]
  plan.requestedFrames = Number(effective.video_length || 0)
  plan.seed = Number(effective.seed)
  plan.enhance = { automatic: false, alreadyEnhanced: plan.prompt !== plan.originalPrompt, deferred: false, empty: !plan.prompt }
  return plan
}

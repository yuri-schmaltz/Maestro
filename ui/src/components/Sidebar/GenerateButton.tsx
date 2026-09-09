import { useEffect, useState } from 'react'
import { AlertTriangle, Eye, ListPlus, Loader2, Play } from 'lucide-react'
import {
  modelSupportsImageWorkflow,
  modelSupportsStudioVideoMediaIntent,
  useStore,
} from '../../stores/useStore'
import { GenerationReviewPanel } from './GenerationReviewPanel'

export function GenerateButton() {
  useEffect(() => { void useStore.getState().restoreGenerationReview() }, [])
  const startGeneration = useStore(s => s.startGeneration)
  const setSidebarOpen = useStore(s => s.setSidebarOpen)
  const reviewPlan = useStore(s => s.reviewPlan)
  const reviewBeforeGenerate = useStore(s => s.reviewBeforeGenerate)
  const reviewBusy = useStore(s => s.reviewBusy)
  const openGenerationReview = useStore(s => s.openGenerationReview)
  // Strategy B: Director is no longer a top-level mode. The legacy
// sidebarMode === 'director' value may still exist for the pre-rollout
// branch; in the new world the equivalent signal is `workspaceStage ===
// 'director'`. We check both so the Generate button's disabled state
// stays accurate after the migration.
const isDirectorMode = useStore(s =>
  s.sidebarMode === 'director'
  || (s.sidebarMode === 'workspace' && s.workspaceStage === 'director'),
)
  const [pendingAction, setPendingAction] = useState<'generate' | 'queue' | null>(null)

  // Check if i2v-only model needs a start image. Video mode only: edit
  // sub-modes supply their own source media (Recast runs the i2v-only
  // SCAIL-2 against a source video + reference image, no start image).
  const generationMode = useStore(s => s.generationMode)
  const studioVideoWorkflow = useStore(s => s.studioVideoWorkflow)
  const studioVideoEffectiveCreateRoute = useStore(s => s.studioVideoEffectiveCreateRoute)
  const currentModel = useStore(s => s.models.find(model => model.model_type === s.params.model_type))
  const modelOptions = useStore(s => s.modelOptions)
  const imageMode = useStore(s => Number(s.params.image_mode || 0))
  const isPrimaryCreate = generationMode === 'video'
    && (studioVideoWorkflow === 'frames' || studioVideoWorkflow === 'references')
    && imageMode === 0
  const modelIsOmniReference = Boolean(
    currentModel?.omni_reference
    || currentModel?.director?.video_strategy === 'omni_reference'
    || currentModel?.model_type.toLowerCase().startsWith('minimax_h3_ref2va'),
  )
  const isOmniReference = modelIsOmniReference
  const isI2vOnly = currentModel
    ? currentModel.is_i2v && !currentModel.is_t2v
    : Boolean(modelOptions?.i2v_class && !modelOptions?.t2v_class)
  const hasOmniReferences = useStore(s => (
    (s.params.minimax_h3_references?.length ?? 0) > 0
  ))
  const hasFlexibleOmniReferences = useStore(s => (
    s.params.minimax_h3_references?.some(reference => !(
      reference.type === 'audio' && reference.audio_intent === 'drive'
    )) === true
  ))
  const hasFrameAudioDrive = useStore(s => Boolean(s.params.audio_guide))
  const hasReferenceAudioDrive = useStore(s => Boolean(
    s.params.minimax_h3_references?.some(reference => (
      reference.type === 'audio' && reference.audio_intent === 'drive'
    )),
  ))
  const hasGuidedInput = useStore(s => Boolean(
    s.startImage
    || s.endImage
    || s.params.image_start
    || s.params.image_end
    || s.imageRefs.length
    || (
      Array.isArray(s.params.image_refs)
      && s.params.image_refs.length
      && s.params.frames_positions
    ),
  ))
  const hasStartImage = useStore(s => !!(s.startImage || s.params.image_start))
  const createWorkflow = studioVideoWorkflow === 'references' ? 'references' : 'frames'
  const studioMediaIntent = {
    workflow: createWorkflow,
    hasFrameGuidance: createWorkflow === 'frames' && hasGuidedInput,
    hasOmniReferences: createWorkflow === 'references' && hasFlexibleOmniReferences,
    hasAudioDrive: createWorkflow === 'references' ? hasReferenceAudioDrive : hasFrameAudioDrive,
  } as const
  const routeModelCompatible = !isPrimaryCreate
    || modelSupportsStudioVideoMediaIntent(currentModel, studioMediaIntent)
  const needsCreateModel = isPrimaryCreate && !routeModelCompatible
  const needsGuidance = isPrimaryCreate
    && studioVideoEffectiveCreateRoute === 'guided'
    && !hasGuidedInput
  const needsImage = generationMode === 'video'
    && isI2vOnly
    && !isOmniReference
    && !hasStartImage
    && (!isPrimaryCreate || createWorkflow === 'frames')
  const needsReference = generationMode === 'video'
    && studioVideoWorkflow === 'references'
    && isOmniReference
    && !hasOmniReferences
    && !hasReferenceAudioDrive
  const editSubMode = useStore(s => s.editSubMode)
  const editVideoPath = useStore(s => s.editVideoPath)
  const outpaintVideoBox = useStore(s => s.outpaintVideoBox)
  const isOutpaint = generationMode === 'avatar' && editSubMode === 'outpaint'
  const needsOutpaintSource = isOutpaint && !editVideoPath
  const hasOutpaintArea = (
    outpaintVideoBox.x > 0.0005
    || outpaintVideoBox.y > 0.0005
    || outpaintVideoBox.x + outpaintVideoBox.w < 0.9995
    || outpaintVideoBox.y + outpaintVideoBox.h < 0.9995
  )
  const needsOutpaintArea = isOutpaint && !!editVideoPath && !hasOutpaintArea
  const imageWorkflow = useStore(s => s.studioImageWorkflow)
  const imageSourcePath = useStore(s => s.imageWorkflowSourcePath)
  const imageMaskPath = useStore(s => s.imageWorkflowMaskPath)
  const imageRefs = useStore(s => s.imageRefs)
  const imagePadding = useStore(s => s.imageOutpaintPadding)
  const needsImageGenerateSource = generationMode === 'image'
    && imageWorkflow === 'generate'
    && currentModel?.requires_image_reference === true
    && imageRefs.length === 0
  const needsImageWorkflowSource = generationMode === 'image'
    && (imageWorkflow === 'inpaint' || imageWorkflow === 'outpaint')
    && !imageSourcePath
  const needsImageMask = generationMode === 'image'
    && imageWorkflow === 'inpaint'
    && !imageMaskPath
  const needsImageOutpaintArea = generationMode === 'image'
    && imageWorkflow === 'outpaint'
    && Object.values(imagePadding).every(value => value === 0)
  const incompatibleImageModel = generationMode === 'image'
    && !modelSupportsImageWorkflow(currentModel, imageWorkflow, imageRefs.length > 0)
  const blocked = needsCreateModel || needsGuidance || needsImage || needsReference || needsOutpaintSource || needsOutpaintArea
    || needsImageGenerateSource || needsImageWorkflowSource || needsImageMask
    || needsImageOutpaintArea || incompatibleImageModel
  const queueSupported = generationMode !== 'avatar'
    && !(generationMode === 'video' && imageMode === 4)

  const perform = async (action: 'generate' | 'queue') => {
    setPendingAction(action)
    if (action === 'generate') setSidebarOpen(false)
    try {
      await startGeneration(action === 'queue' ? 'queue' : 'now')
    } finally {
      setPendingAction(null)
    }
  }

  const submit = (action: 'generate' | 'queue') => {
    if (blocked || pendingAction || reviewBusy || (action === 'queue' && !queueSupported)) return
    // With "Confirm every generation" on, Generate/Queue open the review
    // panel instead of submitting — the panel never submits by itself.
    // Director mode owns its own pipeline, so its Generate stays untouched.
    if (!isDirectorMode && reviewBeforeGenerate) {
      void openGenerationReview(action)
      return
    }
    void perform(action)
  }

  const openReview = () => {
    if (isDirectorMode || blocked || pendingAction || reviewBusy) return
    void openGenerationReview('generate')
  }

  if (blocked) {
    const label = needsCreateModel
      ? 'Need model'
      : needsGuidance
        ? 'Need frame'
      : needsImage
      ? 'Need image'
      : needsReference
        ? 'Need reference'
      : incompatibleImageModel
        ? 'Need model'
      : needsImageGenerateSource || needsImageWorkflowSource
        ? 'Need source'
      : needsImageMask
        ? 'Need mask'
      : needsImageOutpaintArea
        ? 'Choose canvas'
      : needsOutpaintSource
        ? 'Need source'
        : 'Choose canvas'
    const title = needsOutpaintArea
      ? 'Choose a larger output aspect or resize the source to create an area for Outpaint to generate.'
      : needsCreateModel
        ? `Enable or select a video model compatible with the current ${studioVideoEffectiveCreateRoute === 'omni' ? 'reference' : studioVideoEffectiveCreateRoute === 'guided' ? 'frame-guided' : studioVideoEffectiveCreateRoute === 'audio' ? 'audio-driven' : 'text'} inputs.`
        : needsGuidance
          ? 'Add a start frame, end frame, or timed frame.'
      : needsReference
        ? 'Add at least one character, image, video, or audio reference.'
        : incompatibleImageModel
          ? 'Enable or select a model compatible with this Image workflow.'
        : needsImageMask
          ? 'Upload a black-and-white mask. White areas will be regenerated.'
        : needsImageOutpaintArea
          ? 'Expand at least one side of the source canvas.'
        : undefined
    return (
      <>
        <div className="grid w-[158px] shrink-0 grid-cols-[2fr_auto_1fr] overflow-hidden rounded-lg bg-amber-500/20 text-indicator-warning">
          <button
            type="button"
            disabled
            title={title}
            className="flex cursor-not-allowed items-center justify-center gap-1.5 whitespace-nowrap px-2 py-2 text-xs font-medium"
          >
            <AlertTriangle size={13} />
            {label}
          </button>
          <button
            type="button"
            disabled
            title={title || 'Review the exact generation plan before it runs.'}
            aria-label="Review unavailable"
            className="flex cursor-not-allowed items-center justify-center border-l border-current/15"
          >
            <Eye size={14} />
          </button>
          <button
            type="button"
            disabled
            title={title || `${label} before adding this generation to the queue.`}
            aria-label="Add to queue unavailable"
            className="flex cursor-not-allowed items-center justify-center border-l border-current/15"
          >
            <ListPlus size={14} />
          </button>
        </div>
        {reviewBusy && !reviewPlan && <button className="text-xs text-text-muted underline" onClick={() => useStore.getState().closeGenerationReview()}>Cancel review preparation</button>}
      {reviewPlan && <GenerationReviewPanel />}
      </>
    )
  }

  const pending = pendingAction !== null || reviewBusy

  return (
    <>
      <div className={`grid w-[158px] shrink-0 grid-cols-[2fr_auto_1fr] overflow-hidden rounded-lg font-medium text-white shadow-accent-glow transition-all ${
        pending ? 'bg-bg-active text-text-muted' : 'bg-cta'
      }`}>
        <button
          type="button"
          onClick={() => submit('generate')}
          disabled={pending}
          title="Generate now"
          className="flex items-center justify-center gap-1.5 whitespace-nowrap px-2 py-2 text-xs transition-colors hover:bg-white/10 disabled:cursor-wait disabled:hover:bg-transparent"
        >
          {pendingAction === 'generate'
            ? <Loader2 size={13} className="animate-spin" />
            : <Play size={13} fill="currentColor" />}
          Generate
        </button>
        <button
          type="button"
          onClick={openReview}
          disabled={pending || isDirectorMode}
          title={isDirectorMode
            ? 'Review is part of the Director steps — this Generate keeps Studio submission behavior'
            : 'Review before generating — inspect the exact plan (prompt, model, resolution, duration) without submitting'}
          aria-label="Review before generating"
          className="flex items-center justify-center border-l border-white/20 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:border-text-muted/20 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          {reviewBusy
            ? <Loader2 size={14} className="animate-spin" />
            : <Eye size={14} />}
        </button>
        <button
          type="button"
          onClick={() => submit('queue')}
          disabled={pending || !queueSupported}
          title={queueSupported
            ? 'Hold current Studio settings in the queue without starting generation'
            : 'Add to Queue is not available for specialized Transform and Blend workflows yet'}
          aria-label="Add current Studio settings to the queue"
          className="flex items-center justify-center border-l border-white/20 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:border-text-muted/20 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          {pendingAction === 'queue'
            ? <Loader2 size={14} className="animate-spin" />
            : <ListPlus size={14} />}
        </button>
      </div>
      {reviewBusy && !reviewPlan && <button className="text-xs text-text-muted underline" onClick={() => useStore.getState().closeGenerationReview()}>Cancel review preparation</button>}
      {reviewPlan && <GenerationReviewPanel />}
    </>
  )
}
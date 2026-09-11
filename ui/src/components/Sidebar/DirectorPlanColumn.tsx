// filepath: ui/src/components/Sidebar/DirectorPlanColumn.tsx
//
// DirectorPlanColumn — middle column of the Director 3-col layout.
//
// Renders the "what the AI is planning for me" surfaces that used to
// live inline in DirectorChat:
//   1. Structure (clip structure with pacing slider) for music-video path
//   2. Style / scene description view (after the user submits the brief)
//   3. Image prompts review (one card per shot, editable textareas)
//   4. Image generation progress + the generated clip images grid
//   5. Video prompts review (one card per shot, editable textareas)
//
// The chat on the left keeps the conversational surface (welcome, skill
// picker, upload, analyze, completion badges, chat composer). The
// technical setup on the right keeps aspect ratio / resolution / models
// / LoRAs. The plan column is where the user actually *works* on the
// shots — the things that determine what the renderer will draw.
//
// Step gating mirrors what DirectorChat used to do:
//   - structure shows while step ∈ {structure, style, plan, review, ...}
//   - style shows once the user has entered the style step
//   - image prompts / image gen show for shot-image workflows
//   - video prompts show once plan_video or review_video is reached
//
// All state lives in the store (useStore); this component is purely a
// re-mount of the same sub-components DirectorChat already exported.

import { useStore } from '../../stores/useStore'
import { useMemo, useState, useRef } from 'react'
import { Redo2, Undo2 } from 'lucide-react'
import {
  StructureView,
  StyleForm,
  ImagePromptsReview,
  ImageGenView,
  VideoPromptsReview,
  LlmLogStage,
} from './DirectorChat'

const STEP_ORDER = ['upload', 'analyze', 'structure', 'style', 'plan', 'review', 'generate_images', 'plan_video', 'review_video'] as const
type DirectorStep = typeof STEP_ORDER[number]

/**
 * Middle column of the Director planning layout. Renders only the stages
 * that are relevant given the current `directorStep` — the chat on the
 * left keeps the conversational layer, the setup on the right keeps the
 * technical choices, and this column owns the per-shot artifacts.
 */
export function DirectorPlanColumn() {
  const step = useStore(s => s.directorStep)
  const loading = useStore(s => s.directorLoading)
  const skill = useStore(s => s.directorSkill)
  const shortFilmPath = useStore(s => s.shortFilmPath)
  const isShortFilm = skill === 'short_film'
  const isStoryPath = isShortFilm && shortFilmPath === 'story'

  // Step navigation helpers — same logic DirectorChat used inline.
  const currentIndex = STEP_ORDER.indexOf(step as DirectorStep)
  const pastStep = (s: DirectorStep) => currentIndex > STEP_ORDER.indexOf(s)
  const atStep = (s: DirectorStep) => step === s

  // planning surfaces
  const plannedClips = useStore(s => s.directorPlannedClips)
  const energyBias = useStore(s => s.directorEnergyBias)
  const setEnergyBias = useStore(s => s.directorSetEnergyBias)
  const shortFilmSetPacingBias = useStore(s => s.shortFilmSetPacingBias)
  const confirmStructure = useStore(s => s.directorConfirmStructure)
  const totalClipDuration = plannedClips.length > 0 ? plannedClips[plannedClips.length - 1].end : 0
  const beatDistribution = useMemo(() => {
    const counts: Record<number, number> = {}
    for (const c of plannedClips) counts[c.beat_count] = (counts[c.beat_count] || 0) + 1
    return Object.entries(counts)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([beats, count]) => `${count}x${beats}-beat`)
      .join(', ')
  }, [plannedClips])

  // local bias slider state (mirrors DirectorChat)
  const [localBias, setLocalBias] = useState<number | null>(null)
  const sliderRef = useRef<number | null>(null)

  // style / scene description
  const sceneDescription = useStore(s => s.directorSceneDescription)
  const speakers = useStore(s => s.directorSpeakers)
  const speakerMappings = useStore(s => s.directorSpeakerMappings)
  const setSpeakerMapping = useStore(s => s.directorSetSpeakerMapping)
  const insertSpeakerMention = useStore(s => s.directorInsertSpeakerMention)
  const referenceImage = useStore(s => s.directorReferenceImage)
  const shortFilmCharacters = useStore(s => s.shortFilmCharacters)
  const shortFilmTargetDuration = useStore(s => s.shortFilmTargetDuration)

  // pipeline / model selection affects whether shot images are generated
  const selectedDirectorShotImageSupport = useStore(s => s.models.find(
    model => model.model_type === (s.selectedModelPerMode.video || 'ltx2_22B_distilled_1_1'),
  )?.director?.shot_image_support)
  const directorShotImageGuidance = useStore(s => s.directorShotImageGuidance)
  const directorHasVisualReferences = useStore(s => Boolean(
    s.directorReferenceImage
    || s.directorReferenceImagePath
    || s.directorCharacterRefs.length
    || s.directorCharacterRefPaths.length
    || s.directorLocationRefs.length
    || s.directorLocationRefPaths.length,
  ))
  const usesShotImages = useMemo(() => {
    const support = selectedDirectorShotImageSupport
    if (support === 'required') return true
    if (directorHasVisualReferences) return true
    // 'direct_references' means the model wants raw reference images
    // without going through the shot-image pipeline.
    if (support === 'direct_references') return false
    return directorShotImageGuidance !== 'prompt_only'
  }, [selectedDirectorShotImageSupport, directorHasVisualReferences, directorShotImageGuidance])

  // planning prompts / image gen
  const clipPlans = useStore(s => s.directorClipPlans)
  const clipImages = useStore(s => s.directorClipImages)
  const setClipImage = useStore(s => s.directorSetClipImage)
  const imageGenProgress = useStore(s => s.directorImageGenProgress)
  const editClipPlan = useStore(s => s.directorEditClipPlan)
  const planPrompts = useStore(s => s.directorPlanPrompts)
  const planVideoPrompts = useStore(s => s.directorPlanVideoPrompts)
  const generateStartImages = useStore(s => s.directorGenerateStartImages)
  const applyToClips = useStore(s => s.directorApplyToClips)
  const directorGenerate = useStore(s => s.directorGenerate)
  const shortFilmPlanPrompts = useStore(s => s.shortFilmPlanPrompts)
  const shortFilmPlanVideoPrompts = useStore(s => s.shortFilmPlanVideoPrompts)
  const shortFilmPlanFromStory = useStore(s => s.shortFilmPlanFromStory)
  const autoMode = useStore(s => s.directorAutoMode)
  const isGenerating = useStore(s => s.isGenerating)
  const pipelineStatus = useStore(s => s.pipelineStatus)
  const pipelineActive = Boolean(
    pipelineStatus && !['completed', 'failed', 'cancelled'].includes(pipelineStatus.status),
  )
  const directorQueue = useStore(s => s.directorQueue)
  const directorQueueEditingEntryId = useStore(s => s.directorQueueEditingEntryId)
  const queueCurrentDirectorPipeline = useStore(s => s.queueCurrentDirectorPipeline)

  const planHistory = useRef<Array<{
    index: number
    field: 'video_prompt' | 'image_prompt'
    previous: string
    next: string
  }>>([])
  const [historyCursor, setHistoryCursor] = useState(-1)
  const [historyLength, setHistoryLength] = useState(0)
  const editPlanWithHistory = (index: number, field: 'video_prompt' | 'image_prompt', value: string) => {
    const current = useStore.getState().directorClipPlans[index]?.[field] || ''
    if (current === value) return
    planHistory.current = planHistory.current.slice(0, historyCursor + 1)
    planHistory.current.push({ index, field, previous: current, next: value })
    setHistoryCursor(planHistory.current.length - 1)
    setHistoryLength(planHistory.current.length)
    editClipPlan(index, field, value)
  }
  const undoPlanEdit = () => {
    const change = planHistory.current[historyCursor]
    if (!change) return
    editClipPlan(change.index, change.field, change.previous)
    setHistoryCursor(cursor => cursor - 1)
  }
  const redoPlanEdit = () => {
    const change = planHistory.current[historyCursor + 1]
    if (!change) return
    editClipPlan(change.index, change.field, change.next)
    setHistoryCursor(cursor => cursor + 1)
  }

  // speaker samples (recomputed from analysis lyrics)
  const analysis = useStore(s => s.directorAnalysis)
  const speakerSamples = useMemo<Record<string, string[]>>(() => {
    const out: Record<string, string[]> = {}
    const lyrics = analysis?.lyrics
    if (!Array.isArray(lyrics)) return out
    for (const speaker of speakers) out[speaker] = []
    for (const seg of lyrics) {
      if (seg.speaker && out[seg.speaker] && seg.text) {
        out[seg.speaker].push(seg.text)
      }
    }
    return out
  }, [analysis, speakers])

  // If the user has no skill selected yet (or is still at the upload step
  // for a non-story path), there's nothing to plan — render an empty hint
  // instead of empty cards.
  const showPlanSurfaces = Boolean(skill) && (
    isStoryPath
      ? pastStep('style')
      : (pastStep('analyze') || pastStep('structure') || pastStep('style'))
  )

  if (!showPlanSurfaces) {
    return (
      <div className="h-full flex items-center justify-center p-6 text-center">
        <p className="text-xs text-text-muted leading-relaxed">
          {isStoryPath
            ? 'Submit a story description to start planning scenes.'
            : isShortFilm
              ? 'Upload dialogue audio to start scene planning.'
              : 'Upload a track to start clip planning.'}
        </p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3" data-testid="director-plan-column">
      {/* 1) Structure — clip structure with pacing slider. Skipped for
          the story path (no audio → no clip boundary detection). */}
      {!isStoryPath && (atStep('structure') || pastStep('structure')) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <header className="flex items-center justify-between">
            <h3 className="text-xs text-text-muted uppercase tracking-wider">
              {isShortFilm ? 'Scene structure' : 'Clip structure'}
            </h3>
            <span className="text-2xs text-text-muted">
              {plannedClips.length} {isShortFilm ? 'scenes' : 'clips'} · {formatTotalDuration(totalClipDuration)}
            </span>
          </header>
          <StructureView
            plannedClips={plannedClips}
            energyBias={energyBias}
            localBias={localBias}
            setLocalBias={setLocalBias}
            sliderRef={sliderRef}
            setEnergyBias={isShortFilm ? shortFilmSetPacingBias : setEnergyBias}
            loading={loading}
            totalClipDuration={totalClipDuration}
            beatDistribution={beatDistribution}
            confirmStructure={confirmStructure}
            isActive={atStep('structure')}
            isShortFilm={isShortFilm}
          />
        </section>
      )}

      {/* 2) Style / scene description — the user's creative brief,
          rendered as a read-only confirmation of what was submitted. */}
      {(atStep('style') || pastStep('style')) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <header className="flex items-center justify-between">
            <h3 className="text-xs text-text-muted uppercase tracking-wider">Scene description</h3>
            {isShortFilm && (
              <span className="text-2xs text-text-muted">
                {shortFilmTargetDuration}s film
              </span>
            )}
          </header>
          <StyleForm
            speakers={speakers}
            speakerMappings={speakerMappings}
            speakerSamples={speakerSamples}
            setSpeakerMapping={setSpeakerMapping}
            insertSpeakerMention={insertSpeakerMention}
            isActive={atStep('style')}
            isShortFilm={isShortFilm}
            isStoryPath={isStoryPath}
          />
          {pastStep('style') && sceneDescription && (
            <div className="bg-bg-tertiary rounded-lg p-2 border border-border/50">
              <p className="text-xs text-text-primary whitespace-pre-wrap">{sceneDescription}</p>
            </div>
          )}
          {isStoryPath && referenceImage && (
            <div className="flex items-center gap-2 text-2xs text-text-muted">
              <span>Reference attached · {shortFilmCharacters.length} characters</span>
            </div>
          )}
        </section>
      )}

      {(clipPlans.length > 0 || plannedClips.length > 0) && (
        <div className="flex items-center justify-end gap-1">
          <span className="mr-auto text-2xs text-text-muted">Prompt edits</span>
          <button type="button" onClick={undoPlanEdit} disabled={historyCursor < 0} className="rounded p-1 text-text-muted hover:bg-bg-hover hover:text-text-primary disabled:opacity-30" title="Undo prompt edit">
            <Undo2 size={12} />
          </button>
          <button type="button" onClick={redoPlanEdit} disabled={historyCursor >= historyLength - 1} className="rounded p-1 text-text-muted hover:bg-bg-hover hover:text-text-primary disabled:opacity-30" title="Redo prompt edit">
            <Redo2 size={12} />
          </button>
        </div>
      )}

      {/* 3) Plan loading + log — the first LLM pass writes
          image_prompt per clip. The collapsible log stays in the chat
          history once complete; we re-render it here so the user can
          read the full reasoning without scrolling back through chat. */}
      {(pastStep('plan') || (atStep('plan') && !loading)) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">
            {isShortFilm ? 'Scene planning' : usesShotImages ? 'Image and video prompts' : 'Video planning'}
          </h3>
          <LlmLogStage
            stage="plan"
            label={isShortFilm ? 'Scene planning' : usesShotImages ? 'Image and video prompts' : 'Video planning'}
          />
        </section>
      )}

      {/* 4) Image prompts review — one card per clip with an editable
          image_prompt textarea. The user can re-roll the whole batch or
          move to image generation. */}
      {usesShotImages && (atStep('review') || pastStep('review')) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">Start image prompts</h3>
          <ImagePromptsReview
            clipPlans={clipPlans}
            plannedClips={plannedClips}
            speakerMappings={speakerMappings}
            editClipPlan={editPlanWithHistory}
            planPrompts={isStoryPath ? shortFilmPlanFromStory : isShortFilm ? shortFilmPlanPrompts : planPrompts}
            planVideoPrompts={isShortFilm ? shortFilmPlanVideoPrompts : planVideoPrompts}
            generateStartImages={generateStartImages}
            loading={loading}
            isActive={atStep('review')}
            isShortFilm={isShortFilm}
          />
        </section>
      )}

      {/* 5) Image generation — progress + the actual images that came
          back from the image model. Each card is tagged with the clip
          index so the user can mentally pair it with the prompt above. */}
      {usesShotImages && (atStep('generate_images') || pastStep('generate_images')) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">Generated images</h3>
          <ImageGenView
            loading={loading}
            imageGenProgress={imageGenProgress}
            clipImages={clipImages}
            planVideoPrompts={isShortFilm ? shortFilmPlanVideoPrompts : planVideoPrompts}
          />
        </section>
      )}

      {/* 6) Plan video log — second LLM pass that writes video_prompt
          per clip. Same collapsible history as the image-prompt log. */}
      {(pastStep('plan_video') || (atStep('plan_video') && !loading) || atStep('review_video')) && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">Video prompts</h3>
          <LlmLogStage stage="plan_video" label="Video prompts" />
        </section>
      )}

      {/* 7) Video prompts review — final per-clip editing surface
          before the user clicks Generate. */}
      {atStep('review_video') && (
        <section className="bg-bg-secondary rounded-lg p-3 border border-border space-y-2">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">Video prompts per clip</h3>
          <VideoPromptsReview
            clipPlans={clipPlans}
            plannedClips={plannedClips}
            clipImages={clipImages}
            setClipImage={setClipImage}
            allowSceneImageUploads={!usesShotImages && !autoMode}
            speakerMappings={speakerMappings}
            editClipPlan={editPlanWithHistory}
            planVideoPrompts={isShortFilm ? shortFilmPlanVideoPrompts : planVideoPrompts}
            directorGenerate={directorGenerate}
            queueCurrent={queueCurrentDirectorPipeline}
            applyToClips={applyToClips}
            loading={loading}
            isShortFilm={isShortFilm}
            isGenerating={isGenerating || pipelineActive || Boolean(directorQueue?.running)}
            isAutoGenerating={autoMode && pipelineActive}
            editingQueueEntryId={directorQueueEditingEntryId}
          />
        </section>
      )}
    </div>
  )
}

/**
 * Format seconds → mm:ss for the clip structure header.
 */
function formatTotalDuration(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

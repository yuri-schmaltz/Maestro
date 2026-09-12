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
import {
  StructureView,
  StyleForm,
  ImagePromptsReview,
  ImageGenView,
  VideoPromptsReview,
  LlmLogStage,
  AnalysisSummary,
} from './DirectorChat'
import { DirectorTimelineIconButton } from './DirectorTimelineEditor'

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
  // expansion state for the analysis-details panel that now lives
  // inside the clip-structure card.
  const [showAnalysisDetails, setShowAnalysisDetails] = useState(false)

  // analysis snapshot used by both the inline "Analysis complete" badge
  // and the speaker-sample aggregation. Hoisted up here so it can be
  // referenced inside the clip-structure section above without
  // violating the temporal dead zone.
  const analysis = useStore(s => s.directorAnalysis)

  // style / scene description
  // The directorSceneDescription state is still tracked (the
  // composer textarea on the left binds to it), but we no longer
  // re-render it as a read-only confirmation in this column. The
  // left composer is the single source of truth for the brief.
  void useStore(s => s.directorSceneDescription)
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

  // The undo/redo history (planHistory ref + historyCursor/length state
  // + undoPlanEdit/redoPlanEdit handlers + the "Prompt edits" Undo/Redo
  // row below the planning cards) used to live here. The row has been
  // removed — the Image Prompts / Video Prompts cards now own their own
  // textareas and rely on the underlying editClipPlan store action for
  // persistence, which means there is no UI affordance for the history
  // any more. editPlanWithHistory is now a thin wrapper kept around so
  // the existing call sites in ImagePromptsReview / VideoPromptsReview
  // don't need to be touched; it preserves the no-op guard against
  // setting the same value twice.
  const editPlanWithHistory = (index: number, field: 'video_prompt' | 'image_prompt', value: string) => {
    const current = useStore.getState().directorClipPlans[index]?.[field] || ''
    if (current === value) return
    editClipPlan(index, field, value)
  }

  // speaker samples (recomputed from analysis lyrics)
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
    // The three skill-specific messages (audio upload, dialogue upload,
    // story description) used to live here. The user asked to collapse
    // them into a single generic placeholder while the column is empty
    // — the actual call-to-action for picking a skill lives in the
    // chat column on the left, so repeating it here is redundant.
    return (
      <div className="h-full flex items-center justify-center p-6 text-center">
        <p className="text-xs text-text-muted leading-relaxed">
          Planning controls will appear here.
        </p>
      </div>
    )
  }

  return (
    /* Wrapper padding: p-4 (16px) matches the inner padding of the
       sections below so the first/last cards sit at the same inset
       as the cards stacked underneath them. The outer
       .director-stage-plan card adds another 20px on top, so the
       visible inset is 36px from the column's rounded border —
       generous enough to let the cards breathe without wasting
       vertical real estate. */
    <div className="h-full overflow-y-auto p-4 space-y-3" data-testid="director-plan-column">
      {/* 1) Structure — clip structure with pacing slider. Skipped for
          the story path (no audio → no clip boundary detection). */}
      {!isStoryPath && (atStep('structure') || pastStep('structure')) && (
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
          <header className="flex items-center justify-between gap-2">
            <h3 className="text-xs text-text-muted uppercase tracking-wider">
              {isShortFilm ? 'Scene structure' : 'Clip structure'}
            </h3>
            {/* Top-right cluster: only the compact wizard icon that
                opens the timeline editor. The "N clips · 2:33" counter
                used to live here, but the same numbers are now embedded
                inside the structure preview row (the user prefers a
                clean header) so the wizard icon stands alone as the
                affordance. */}
            <DirectorTimelineIconButton />
          </header>
          {/* "Analysis complete" badge used to live in the left chat
              column as a system bubble; the user asked to consolidate
              it (plus the "Edit scene timing" button below) into the
              clip-structure card so the planning surface is the single
              source of truth for the post-analyze view. */}
          {analysis && pastStep('analyze') && (
            <AnalysisSummary
              analysis={analysis}
              showDetails={showAnalysisDetails}
              setShowDetails={setShowAnalysisDetails}
              isShortFilm={isShortFilm}
            />
          )}
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
          {/* The "Edit scene timing" button used to render here as a
              full-width row below the structure preview. The user asked
              to relocate it to the top-right of the card as a compact
              wizard icon — see the header block above. */}
        </section>
      )}

      {/* 2) Style / scene description — the user's creative brief,
          rendered as a read-only confirmation of what was submitted. */}
      {(atStep('style') || pastStep('style')) && (
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
          <header className="flex items-center justify-between gap-2">
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
          {/* The read-only confirmation of the scene description used to
              render here as a separate paragraph block, but the same
              text is already visible in the left-column composer
              textarea. Duplicating it here wasted a huge amount of
              vertical space in the center column — space that the
              Image Prompts / Video Prompts planning cards need once
              planning starts. Removed; the StyleForm's "Scene
              description submitted. Planning shots..." message is
              enough confirmation that the brief was received. */}
          {isStoryPath && referenceImage && (
            <div className="flex items-center gap-2 text-2xs text-text-muted">
              <span>Reference attached · {shortFilmCharacters.length} characters</span>
            </div>
          )}
        </section>
      )}

      {/* 3) Plan loading + log — the first LLM pass writes
          image_prompt per clip. The collapsible log stays in the chat
          history once complete; we re-render it here so the user can
          read the full reasoning without scrolling back through chat. */}
      {(pastStep('plan') || (atStep('plan') && !loading)) && (
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
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
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
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
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
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
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
          <h3 className="text-xs text-text-muted uppercase tracking-wider">Video prompts</h3>
          <LlmLogStage stage="plan_video" label="Video prompts" />
        </section>
      )}

      {/* 7) Video prompts review — final per-clip editing surface
          before the user clicks Generate. */}
      {atStep('review_video') && (
        <section className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
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

/* formatTotalDuration used to power the "N clips · 2:33" counter in
 * the clip-structure header. Removed: the header now just shows the
 * section title + wizard icon, and the same numbers live inside the
 * <StructureView/> preview row. */

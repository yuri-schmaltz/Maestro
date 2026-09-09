// filepath: ui/src/components/Stages/DirectorStage.tsx
//
// DirectorStage — Strategy B (Director-as-Stage) from the
// merge feasibility analysis. This component is a thin wrapper that
// mounts the existing `<DirectorChat/>` inside a Studio-styled shell so
// it can be displayed as a tab alongside the other Studio controls
// instead of forcing the user to flip `sidebarMode: 'director' | 'studio'`.
//
// Why this exists
// ----------------
// Pre-merge, the only way to access the Director planning UI was to
// flip the top-level mode toggle (`AppModeToggle`). That meant the
// user lost the Studio queue / generation context every time they
// wanted to plan a new scene or revisit a prompt plan. Strategy B
// promotes Director to a Stage that lives inside the Workspace; the
// old `sidebarMode === 'director'` mode is kept as a feature-flagged
// fallback so this rollout can be reverted with zero risk.
//
// What's NOT here
// ---------------
// - No new state. The DirectorChat reads from the same Director
//   slices (`directorStep`, `directorLoading`, `directorClipPlans`, …).
// - No API changes. Cancel still routes through
//   `useStore.cancelDirectorV2Plan()` + `useStore.stopPipeline()`.
// - No Python changes. `director_pipeline.py`, `v2_plan_cancel.py`,
//   `DirectorOrchestrator` are untouched.
//
// The wrapper only renders a header + the existing DirectorChat and
// listens for the parent to mount/unmount it. Cancellation, planning,
// and prompt polish flow through unchanged.
//
// Skill chooser
// -------------
// A "Choose different skill" button in the header opens an in-stage
// modal with the same Music Video / Short Film cards the DirectorChat
// shows on first launch. Clicking a card calls
// `useStore.resetDirectorSkillOnly()` (preserves audio, analysis,
// scene description, plan progress) + `setDirectorSkill(skill)` so
// the chat picks up at the new skill's "upload" step. Cancelling
// leaves the existing skill untouched.

import { useEffect, useState } from 'react'
import { X, Sparkles, ArrowRight, Music, Film, Mic, Wand2 } from 'lucide-react'
import { DirectorChat } from '../Sidebar/DirectorChat'
import { useStore } from '../../stores/useStore'
import type { DirectorSkill } from '../../types'

interface DirectorStageProps {
  /** Called when the user clicks the close button on the stage header. */
  onClose?: () => void
  /** Render in compact mode (no header) when nested inside another surface. */
  embedded?: boolean
}

interface SkillOption {
  id: DirectorSkill
  label: string
  desc: string
  icon: typeof Music
  active: boolean
}

// Mirrors the SkillSelector in DirectorChat.tsx so the modal surface
// matches what the user sees on first launch. Keep this in sync if
// the underlying list changes (new skills added to the registry).
const SKILL_OPTIONS: SkillOption[] = [
  { id: 'music_video', label: 'Music Video', desc: 'Automated music video from audio', icon: Music, active: true },
  { id: 'short_film', label: 'Short Film', desc: 'Dialogue-driven scenes from audio', icon: Film, active: true },
  { id: 'video_podcast', label: 'Video Podcast', desc: 'Coming Soon', icon: Mic, active: false },
  { id: 'viral_video', label: 'Viral Video', desc: 'Coming Soon', icon: Wand2, active: false },
]

interface DirectorStageProps {
  /** Called when the user clicks the close button on the stage header. */
  onClose?: () => void
  /** Render in compact mode (no header) when nested inside another surface. */
  embedded?: boolean
}

/**
 * Mounts the Director planning UI as a Stage inside the Workspace.
 *
 * The optional header surfaces the user's mental model:
 * "I'm planning right now" — without forcing them off the Studio queue
 * they're watching. Closing the stage returns them to the Studio view
 * without erasing any planning progress (DirectorChat keeps its own
 * `directorStep`).
 */
export function DirectorStage({ onClose, embedded = false }: DirectorStageProps) {
  const pipelineId = useStore(s => s.pipelineId)
  const pipelineStatus = useStore(s => s.pipelineStatus)
  const directorStep = useStore(s => s.directorStep)
  const directorClipPlans = useStore(s => s.directorClipPlans)
  const directorSkill = useStore(s => s.directorSkill)
  const closeDirectorStage = useStore(s => s.closeDirectorStage)
  const directorApplyToClips = useStore(s => s.directorApplyToClips)
  const resetDirectorSkillOnly = useStore(s => s.resetDirectorSkillOnly)
  const setDirectorSkill = useStore(s => s.setDirectorSkill)

  // Skill chooser modal — toggled by the "Choose different skill"
  // header button. Lives in Stage state (not the store) because it's
  // pure UI ephemera: nothing outside the modal needs to know it's open.
  const [skillChooserOpen, setSkillChooserOpen] = useState(false)

  // Continue in Studio is only meaningful once the plan is reviewed —
  // pre-review there's nothing to apply yet.
  const canContinueToStudio = directorClipPlans.length > 0
    && (directorStep === 'review' || directorStep === 'review_video')

  // Make sure the DirectorChat's LLM-log polling effect runs whenever
  // the Stage is mounted. The legacy `<DirectorChat/>` was only mounted
  // when sidebarMode === 'director', so its effects could rely on that
  // signal; here we forward a minimal re-mount hint by changing the
  // wrapper key. Polling itself is already keyed off `useEffect` deps
  // inside DirectorChat, so we don't actually need a key — but we keep
  // the place marker so a future log-stream-pause change has a hook.
  useEffect(() => {
    // Intentionally empty: present so React DevTools shows the mount.
    return () => {
      // Same: cleanup hook reserved for future "pause LLM stream when
      // stage is hidden" behavior (out of scope for Stage 1).
    }
  }, [pipelineId, pipelineStatus?.status])

  if (embedded) {
    return <DirectorChat />
  }

  return (
    <div
      className="flex flex-col h-full bg-bg-secondary border-l border-border"
      data-testid="director-stage"
      data-pipeline-status={pipelineStatus?.status ?? 'idle'}
    >
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center gap-2 text-text-primary">
          <Sparkles size={14} className="text-accent-blue" />
          <span className="text-xs font-semibold uppercase tracking-wider">
            Director — Planning
          </span>
          {directorSkill && (
            <span className="text-[10px] text-text-muted normal-case tracking-normal">
              · {directorSkill === 'short_film' ? 'Short Film' : 'Music Video'}
            </span>
          )}
          {pipelineStatus?.status === 'running' && (
            <span className="ml-1 text-[10px] text-accent-blue">● Live</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {/* "Choose skill" — opens the in-stage modal that lists Music
              Video / Short Film. Visible when:
                (a) a skill is already selected (so the user can swap),
                (b) the user is still at the initial 'upload' step
                    where the inline SkillSelector lives — the header
                    button gives a faster path that doesn't require
                    scrolling the chat history.
              Once the user is mid-flow (analyze/plan/review/…) the
              button stays visible so they can switch contexts without
              losing audio or analysis. */}
          {(directorSkill || directorStep === 'upload') && (
            <button
              type="button"
              onClick={() => setSkillChooserOpen(true)}
              title="Switch between Music Video and Short Film"
              aria-label="Choose skill"
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
            >
              <Wand2 size={12} />
              Choose skill
            </button>
          )}
          {canContinueToStudio && (
            <button
              type="button"
              onClick={() => {
                // Apply the planned prompts to the Studio clips, then
                // collapse the Stage so the user sees their Studio queue
                // ready to run. Replaces the legacy directorApplyToClips
                // flow that flipped sidebarMode wholesale.
                directorApplyToClips()
                closeDirectorStage()
              }}
              title="Apply plans to Studio and return to the queue"
              aria-label="Continue in Studio"
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-accent-blue hover:text-accent-blue-hover hover:bg-bg-hover transition-colors"
            >
              Continue in Studio
              <ArrowRight size={12} />
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close Director stage"
              title="Close Director stage (return to Studio)"
              className="p-1.5 rounded-lg hover:bg-bg-hover text-text-secondary hover:text-text-primary transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        <DirectorChat />
      </div>
      {/* In-stage skill chooser modal. Renders above the chat but does
          not unmount it — when the user picks a new skill the chat
          re-renders at the new skill's "upload" step automatically. */}
      {skillChooserOpen && (
        <SkillChooserModal
          currentSkill={directorSkill}
          onCancel={() => setSkillChooserOpen(false)}
          onPick={(skill) => {
            // Preserve audio, analysis, scene description, plan
            // progress — only the skill + derived fields are reset.
            // setDirectorSkill runs the same input-strength fix-up
            // logic the initial pick does, so H3 video models stay
            // consistent across skill swaps.
            resetDirectorSkillOnly()
            setDirectorSkill(skill)
            setSkillChooserOpen(false)
          }}
        />
      )}
    </div>
  )
}

interface SkillChooserModalProps {
  currentSkill: DirectorSkill | null
  onCancel: () => void
  onPick: (skill: DirectorSkill) => void
}

/**
 * In-stage modal that lists the available Director skills. Mirrors
 * the `<SkillSelector/>` first-launch UX so the user sees a familiar
 * surface; clicking a card commits the change via the parent's
 * `onPick` callback. Inactive skills (Video Podcast, Viral Video)
 * stay visible with a "Soon" badge so users know what's coming.
 */
function SkillChooserModal({ currentSkill, onCancel, onPick }: SkillChooserModalProps) {
  // Close on Escape so the modal feels native to the rest of the app.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="skill-chooser-title"
      onClick={onCancel}
      data-testid="director-skill-chooser"
    >
      <div
        className="bg-bg-secondary border border-border rounded-xl shadow-2xl w-[480px] max-w-[90vw] p-5"
        onClick={e => e.stopPropagation()}
      >
        <header className="flex items-start justify-between mb-3">
          <div>
            <h2
              id="skill-chooser-title"
              className="text-sm font-semibold text-text-primary"
            >
              Choose a skill
            </h2>
            <p className="text-[11px] text-text-muted mt-1">
              Switch between Music Video and Short Film without losing
              your audio, analysis, or scene description.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close skill chooser"
            className="p-1 rounded-md hover:bg-bg-hover text-text-secondary hover:text-text-primary transition-colors"
          >
            <X size={14} />
          </button>
        </header>

        <div className="grid grid-cols-2 gap-2">
          {SKILL_OPTIONS.map(opt => {
            const isCurrent = opt.id === currentSkill
            const Icon = opt.icon
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => opt.active && onPick(opt.id)}
                disabled={!opt.active}
                aria-pressed={isCurrent}
                className={`relative p-3 rounded-lg border text-left transition-all ${
                  isCurrent
                    ? 'border-accent-blue bg-accent-blue/10'
                    : opt.active
                      ? 'border-border bg-bg-tertiary/50 hover:border-accent-blue hover:bg-accent-blue/5 cursor-pointer'
                      : 'border-border/30 bg-bg-tertiary/20 opacity-50 cursor-not-allowed'
                }`}
                data-testid={`director-skill-option-${opt.id}`}
              >
                <Icon
                  size={16}
                  className={
                    isCurrent || opt.active
                      ? 'text-accent-blue mb-1.5'
                      : 'text-text-muted mb-1.5'
                  }
                />
                <div className="text-xs font-medium text-text-primary">
                  {opt.label}
                  {isCurrent && (
                    <span className="ml-1.5 text-[9px] text-accent-blue">
                      Current
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">
                  {opt.desc}
                </div>
                {!opt.active && (
                  <span className="absolute top-1.5 right-1.5 text-[8px] bg-bg-hover text-text-muted px-1.5 py-0.5 rounded-full">
                    Soon
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <footer className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-border">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-[11px] text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          >
            Cancel
          </button>
        </footer>
      </div>
    </div>
  )
}
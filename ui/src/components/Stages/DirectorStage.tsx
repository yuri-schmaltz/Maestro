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

import { useEffect } from 'react'
import {
  DirectorChat,
  DirectorSetupPanel,
  DirectorGenerationOptions,
} from '../Sidebar/DirectorChat'
import { DirectorPlanColumn } from '../Sidebar/DirectorPlanColumn'
import { useStore } from '../../stores/useStore'

interface DirectorStageProps {
  /** Render in compact mode (no header) when nested inside another surface. */
  embedded?: boolean
}

/**
 * Mounts the Director planning UI as a Stage inside the Workspace.
 *
 * The 3-column layout (chat / plan / setup) gives the user a single
 * surface for everything Director: creative conversation on the left,
 * per-shot artifacts (clip structure, image prompts, generated images,
 * video prompts) in the middle, and the technical choices (aspect
 * ratio, resolution, workflow, models, LoRAs) on the right.
 *
 * The skill chooser modal that used to live here was removed — the
 * `<SkillSelector/>` inside DirectorChat already offers the same
 * switching surface during the upload step.
 */
export function DirectorStage({ embedded = false }: DirectorStageProps) {
  const pipelineId = useStore(s => s.pipelineId)
  const pipelineStatus = useStore(s => s.pipelineStatus)
  const directorStep = useStore(s => s.directorStep)

  // Setup (aspect ratio / resolution / workflow / models) stays editable
  // while the user is still at the upload or analyze step. Once they
  // confirm the structure or move past it, the technical choices are
  // baked into the plan and changing them mid-stream would invalidate
  // prompts that downstream clips already depend on.
  const setupLocked = directorStep !== 'upload' && directorStep !== 'analyze'

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
      className="flex flex-col h-full min-h-0 bg-bg-secondary"
      data-testid="director-stage"
      data-pipeline-status={pipelineStatus?.status ?? 'idle'}
    >
      <div className="director-stage-columns">
        <aside className="director-stage-chat" aria-label="Director chat & decisions">
          <DirectorChat />
        </aside>
        <section className="director-stage-plan" aria-label="Director plan & shots">
          <DirectorPlanColumn />
        </section>
        <aside className="director-stage-options" aria-label="Director setup & generation options">
          <DirectorSetupPanel locked={setupLocked} />
          <div className="pt-3 mt-3 border-t border-border/50">
            <DirectorGenerationOptions />
          </div>
        </aside>
      </div>
    </div>
  )
}
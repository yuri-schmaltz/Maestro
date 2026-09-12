import { Clapperboard, SlidersHorizontal } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { DirectorStage } from '../Stages/DirectorStage'
import { Sidebar } from '../Sidebar/Sidebar'
import { MainContent } from '../MainContent/MainContent'

/**
 * Standalone Planning / Studio toggle that lives in the bottom
 * HardwareStatusBar (leftSlot). Reading the stage from the store
 * keeps this component decoupled from DirectorPage — App.tsx
 * renders <HardwareStatusBar leftSlot={<DirectorStageToggle/>}/>
 * whenever the Director tab is active, and the toggle mutates the
 * same workspaceStage state as the in-page version used to.
 */
export function DirectorStageToggle() {
  const stage = useStore(s => s.workspaceStage)
  const openPlanning = useStore(s => s.openDirectorStage)
  const openStudio = useStore(s => s.closeDirectorStage)
  return (
    <div className="shell-segmented" role="group" aria-label="Director workflow">
      <button aria-pressed={stage === 'director'} onClick={openPlanning}>
        <Clapperboard size={12} />Planning
      </button>
      <button aria-pressed={stage === 'studio'} onClick={openStudio}>
        <SlidersHorizontal size={12} />Studio
      </button>
    </div>
  )
}

/**
 * Director page — single screen, full-height layout.
 *
 * Two columns side-by-side so the user can see the planning chat AND
 * the saved-pipelines dashboard at the same time, without scrollbars
 * stacking vertically. The Studio toggle (Planning / Studio) used to
 * live in the section-toolbar above the workspace; it now sits in
 * the bottom HardwareStatusBar via the leftSlot prop so the
 * workspace gets the full vertical height back.
 *
 *   ┌─────────────────────────────────────────┬─────────────┐
 *   │  DirectorStage (chat + composer)        │  Dashboard  │
 *   │  flex:1                                 │  360px      │
 *   └─────────────────────────────────────────┴─────────────┘
 *
 * When `stage === 'studio'` we render the original Studio layout
 * (Sidebar + MainContent) without the dashboard — manual generation
 * doesn't need pipeline history.
 */
export function DirectorPage() {
  const stage = useStore(s => s.workspaceStage)

  return (
    <div className="flex h-full min-h-0 flex-col">
      {stage === 'director' ? (
        <div className="director-layout">
          <div className="director-stage-pane">
            <DirectorStage />
          </div>
        </div>
      ) : (
        // Studio mode renders the legacy layout (Sidebar + MainContent)
        // side-by-side. The media-preview toggle that used to live in
        // the section toolbar is gone — its only job was flipping
        // the mobile breakpoint between preview and controls, and now
        // that the toolbar is empty we always show the controls.
        <div className="flex min-h-0 flex-1">
          <div className="flex h-full min-w-0 w-full md:w-auto">
            <Sidebar />
          </div>
          <div className="hidden md:flex min-w-0 flex-1">
            <MainContent />
          </div>
        </div>
      )}
    </div>
  )
}

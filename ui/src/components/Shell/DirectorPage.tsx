import { useState } from 'react'
import { Clapperboard, SlidersHorizontal, Images, LayoutDashboard } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { DirectorStage } from '../Stages/DirectorStage'
import { Sidebar } from '../Sidebar/Sidebar'
import { MainContent } from '../MainContent/MainContent'
import { DirectorDashboard } from '../DirectorDashboard/DirectorDashboard'

/**
 * Director page — single screen, full-height layout.
 *
 * Two columns side-by-side so the user can see the planning chat AND
 * the saved-pipelines dashboard at the same time, without scrollbars
 * stacking vertically. The Studio toggle (Planning / Studio) keeps
 * the legacy manual-generation view reachable for users who don't
 * need the dashboard.
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
  const openPlanning = useStore(s => s.openDirectorStage)
  const openStudio = useStore(s => s.closeDirectorStage)
  const workspace = useStore(s => s.activeWorkspace)
  const dashboardOpen = useStore(s => s.dashboardOpen)
  const setDashboardOpen = useStore(s => s.setDashboardOpen)
  const [showPreview, setShowPreview] = useState(false)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="section-toolbar">
        <div className="min-w-0">
          <h1 className="text-sm font-semibold">Director</h1>
          <p className="max-w-48 truncate text-xs text-text-muted">{workspace}</p>
        </div>
        <div className="flex items-center gap-3">
          {stage === 'director' && (
            <button
              onClick={() => setDashboardOpen(!dashboardOpen)}
              aria-pressed={dashboardOpen}
              title={dashboardOpen ? 'Hide dashboard' : 'Show dashboard'}
              className={`shell-icon-button ${dashboardOpen ? 'is-active' : ''}`}
              aria-label={dashboardOpen ? 'Hide dashboard' : 'Show dashboard'}
            >
              <LayoutDashboard size={15} />
            </button>
          )}
          <div className="shell-segmented" role="group" aria-label="Director workflow">
            <button aria-pressed={stage === 'director'} onClick={openPlanning}>
              <Clapperboard size={14} />Planning
            </button>
            <button aria-pressed={stage === 'studio'} onClick={openStudio}>
              <SlidersHorizontal size={14} />Studio
            </button>
          </div>
          {stage === 'studio' && (
            <button
              className="shell-icon-button studio-preview-toggle"
              aria-label={showPreview ? 'Show generation controls' : 'Show media preview'}
              onClick={() => setShowPreview(!showPreview)}
            >
              <Images size={16} />
            </button>
          )}
        </div>
      </div>

      {stage === 'director' ? (
        <div className={`director-layout ${dashboardOpen ? 'has-dashboard' : ''}`}>
          <div className="director-stage-pane">
            <DirectorStage />
          </div>
          {dashboardOpen && (
            <aside className="director-dashboard-pane" aria-label="Pipeline dashboard">
              <DirectorDashboard embedded />
            </aside>
          )}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className={`${showPreview ? 'hidden md:flex' : 'flex'} h-full min-w-0 w-full md:w-auto`}>
            <Sidebar />
          </div>
          <div className={`${showPreview ? 'flex' : 'hidden md:flex'} min-w-0 flex-1`}>
            <MainContent />
          </div>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { Clapperboard, SlidersHorizontal, Images } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { DirectorStage } from '../Stages/DirectorStage'
import { Sidebar } from '../Sidebar/Sidebar'
import { MainContent, PipelinePlaceholder } from '../MainContent/MainContent'

export function DirectorPage() {
  const pipeline = useStore(s => s.pipelineStatus)
  const hasPipeline = useStore(s => Boolean(s.pipelineId))
  const showProduction = hasPipeline && pipeline && pipeline.status !== 'completed'
  const stage = useStore(s => s.workspaceStage)
  const openPlanning = useStore(s => s.openDirectorStage)
  const openStudio = useStore(s => s.closeDirectorStage)
  const workspace = useStore(s => s.activeWorkspace)
  const [showPreview, setShowPreview] = useState(false)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="section-toolbar">
        <div className="min-w-0"><h1 className="text-sm font-semibold">Director</h1><p className="max-w-48 truncate text-[11px] text-text-muted">{workspace}</p></div>
        <div className="shell-segmented" role="group" aria-label="Director workflow">
          <button aria-pressed={stage === 'director'} onClick={openPlanning}><Clapperboard size={14} />Planning</button>
          <button aria-pressed={stage === 'studio'} onClick={openStudio}><SlidersHorizontal size={14} />Studio</button>
        </div>
        {stage === 'studio' && <button className="shell-icon-button studio-preview-toggle" aria-label={showPreview ? 'Show generation controls' : 'Show media preview'} onClick={() => setShowPreview(!showPreview)}><Images size={16} /></button>}
      </div>
      {stage === 'director' ? (
        <div className={`director-planning-layout ${showProduction ? 'has-production' : ''}`}>
          <div className="director-planning-surface"><DirectorStage /></div>
          {showProduction && <div className="director-production-surface" aria-label="Production review and progress"><PipelinePlaceholder /></div>}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className={`${showPreview ? 'hidden md:flex' : 'flex'} h-full min-w-0 w-full md:w-auto`}><Sidebar /></div>
          <div className={`${showPreview ? 'flex' : 'hidden md:flex'} min-w-0 flex-1`}><MainContent /></div>
        </div>
      )}
    </div>
  )
}

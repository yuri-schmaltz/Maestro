import { useEffect, useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  Check,
  Clock,
  ListVideo,
  Loader2,
  Pause,
  Pencil,
  Play,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { formatEtaDuration } from '../../lib/format'
import { PROMPT_ENHANCEMENT_ACTIVITY } from '../../lib/promptEnhancementActivity'

const ACTIVE_JOB_STATUSES = new Set(['held', 'queued', 'running', 'awaiting_review'])
const ACTIVE_DIRECTOR_STATUSES = new Set(['held', 'queued', 'running', 'awaiting_review'])
const ACTIVE_PIPELINE_STATUSES = new Set(['queued', 'running', 'paused'])

function compactStatus(value: string): string {
  return value.replace(/_/g, ' ').replace(/^./, letter => letter.toUpperCase())
}

function progressPercent(step: number, totalSteps: number, progress: number): number {
  if (totalSteps > 0) return Math.max(0, Math.min(100, (step / totalSteps) * 100))
  return Math.max(0, Math.min(100, progress * 100))
}

/**
 * Full-page Generation Queue. Mirrors the layout the old
 * `GlobalQueuePopover` offered in a 390px panel, but expanded to a
 * proper page section: heading + count badge at top, three grouped
 * sections (Director now / Studio & Editor / Director queue), and the
 * same empty state when nothing's running.
 *
 * Polls the Director queue periodically (same cadence as the popover)
 * and exposes all the same controls: start/pause Director, start held
 * Studio jobs, cancel individual jobs, reorder/remove Director
 * entries, jump into the Director for an awaiting_review project.
 */
export function QueuePage() {
  const jobs = useStore(state => state.jobs)
  const isEnhancing = useStore(state => state.isEnhancing)
  const stopGeneration = useStore(state => state.stopGeneration)
  const startStudioQueue = useStore(state => state.startStudioQueue)
  const directorQueue = useStore(state => state.directorQueue)
  const directorQueueLoading = useStore(state => state.directorQueueLoading)
  const loadDirectorQueue = useStore(state => state.loadDirectorQueue)
  const loadDirectorQueueEntry = useStore(state => state.loadDirectorQueueEntry)
  const startDirectorQueue = useStore(state => state.startDirectorQueue)
  const pauseDirectorQueue = useStore(state => state.pauseDirectorQueue)
  const removeDirectorQueueEntry = useStore(state => state.removeDirectorQueueEntry)
  const moveDirectorQueueEntry = useStore(state => state.moveDirectorQueueEntry)
  const pipelineId = useStore(state => state.pipelineId)
  const pipelineStatus = useStore(state => state.pipelineStatus)
  const stopPipeline = useStore(state => state.stopPipeline)
  const setSidebarOpen = useStore(state => state.setSidebarOpen)
  const setAppSection = useStore(state => state.setAppSection)
  const [startingAll, setStartingAll] = useState(false)

  const studioJobs = useMemo(
    () => {
      const activeJobs = jobs.filter(job => ACTIVE_JOB_STATUSES.has(job.status))
      return isEnhancing ? [PROMPT_ENHANCEMENT_ACTIVITY, ...activeJobs] : activeJobs
    },
    [isEnhancing, jobs],
  )
  const studioHeldCount = studioJobs.filter(job => job.status === 'held').length
  const directorEntries = directorQueue?.entries || []
  const pendingDirectorCount = directorEntries.filter(entry => (
    ACTIVE_DIRECTOR_STATUSES.has(entry.status)
  )).length
  const startableDirectorCount = directorEntries.filter(entry => (
    entry.status === 'held' || entry.status === 'queued'
  )).length
  const activePipeline = Boolean(
    pipelineId && pipelineStatus && ACTIVE_PIPELINE_STATUSES.has(pipelineStatus.status),
  )
  const activePipelineIsQueued = Boolean(
    activePipeline && directorEntries.some(entry => (
      (entry.status === 'running' || entry.status === 'awaiting_review')
      && (!entry.pipeline_id || entry.pipeline_id === pipelineId)
    )),
  )
  const totalCount = studioJobs.length
    + pendingDirectorCount
    + (activePipeline && !activePipelineIsQueued ? 1 : 0)

  useEffect(() => {
    void loadDirectorQueue()
  }, [loadDirectorQueue])

  useEffect(() => {
    if (!directorQueue?.running && !directorQueue?.entries.some(entry => entry.status === 'awaiting_review')) return
    const timer = window.setInterval(() => void loadDirectorQueue(), 2500)
    return () => window.clearInterval(timer)
  }, [directorQueue?.running, directorQueue?.entries, loadDirectorQueue])

  const startAllQueues = async () => {
    if (startingAll) return
    setStartingAll(true)
    try {
      // Release Studio first. Director's existing GPU gate sees those jobs
      // as queued/running and waits, so one click safely starts both systems.
      if (studioHeldCount > 0) await startStudioQueue()
      if (
        startableDirectorCount > 0
        && (!directorQueue?.running || directorQueue.paused)
      ) {
        await startDirectorQueue()
      }
    } finally {
      setStartingAll(false)
    }
  }

  const openDirectorEntry = async (entryId: string) => {
    await loadDirectorQueueEntry(entryId)
    setSidebarOpen(true)
    setAppSection('director')
  }

  return (
    <div className="section-scroll">
      <div className="section-container">
        <div className="section-heading queue-page-heading">
          <div>
            <div className="queue-page-eyebrow">
              <ListVideo size={14} className="text-accent-blue" />
              <span>Generation Queue</span>
              <span className="queue-page-count">{totalCount} {totalCount === 1 ? 'item' : 'items'}</span>
            </div>
            <p>Studio, Director, and Editor in one place. Hold, queue, start, or cancel generation jobs from here.</p>
          </div>
          <div className="queue-page-actions">
            {studioHeldCount > 0 && (
              <button
                type="button"
                onClick={() => void startAllQueues()}
                disabled={startingAll}
                className="shell-secondary-button"
                title="Start all held Studio jobs, then any held Director projects"
              >
                {startingAll ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Start all
              </button>
            )}
            {directorQueue?.running && !directorQueue.paused ? (
              <button
                type="button"
                onClick={() => void pauseDirectorQueue()}
                disabled={directorQueueLoading}
                className="shell-secondary-button"
                title="Finish the active Director project, then stop dispatching"
              >
                <Pause size={14} /> Pause Director
              </button>
            ) : (
              startableDirectorCount > 0 && (
                <button
                  type="button"
                  onClick={() => void startDirectorQueue()}
                  disabled={directorQueueLoading || startingAll}
                  className="shell-secondary-button"
                  title="Resume Director dispatching"
                >
                  <Play size={14} /> Start Director
                </button>
              )
            )}
          </div>
        </div>

        {!activePipeline && studioJobs.length === 0 && directorEntries.length === 0 && (
          <div className="shell-empty">
            <ListVideo size={40} strokeWidth={1.5} />
            <h2>Queue is empty</h2>
            <p>Queued Studio generations, Editor exports, and held Director projects will appear here.</p>
          </div>
        )}

        {activePipeline && !activePipelineIsQueued && pipelineStatus && (
          <section className="queue-section">
            <div className="queue-section-header">
              <span>Director now</span>
              <span className="text-accent-blue">1 active</span>
            </div>
            <div className="queue-card">
              <div className="queue-card-row">
                <Loader2 size={14} className="shrink-0 animate-spin text-accent-blue" />
                <div className="queue-card-meta">
                  <div className="queue-card-title">{pipelineStatus.progress?.message || compactStatus(pipelineStatus.phase)}</div>
                  <div className="queue-card-subtitle">
                    Director · {compactStatus(pipelineStatus.status)}
                    {pipelineStatus.progress?.project_eta_seconds != null
                      ? ` · ${formatEtaDuration(pipelineStatus.progress.project_eta_seconds)} remaining`
                      : ''}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void stopPipeline()}
                  className="shell-icon-button hover:text-red-400"
                  title="Stop Director generation"
                  aria-label="Stop Director generation"
                >
                  <Square size={13} />
                </button>
              </div>
              {pipelineStatus.progress && pipelineStatus.progress.total > 0 && (
                <div className="queue-progress">
                  <div
                    className="queue-progress-fill bg-accent-blue"
                    style={{ width: `${Math.max(0, Math.min(100, (pipelineStatus.progress.current / pipelineStatus.progress.total) * 100))}%` }}
                  />
                </div>
              )}
            </div>
          </section>
        )}

        {studioJobs.length > 0 && (
          <section className="queue-section">
            <div className="queue-section-header">
              <span>Studio &amp; Editor</span>
              {studioHeldCount > 0 ? (
                <button
                  type="button"
                  onClick={() => void startAllQueues()}
                  disabled={startingAll}
                  className="queue-section-action is-success"
                  title="Start all held Studio jobs"
                >
                  {startingAll ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                  Start queue
                </button>
              ) : (
                <span className="queue-section-meta">{studioJobs.length} active</span>
              )}
            </div>
            <div className="queue-list">
              {studioJobs.map((job, index) => {
                const percent = progressPercent(job.step, job.totalSteps, job.progress)
                const isPromptPlanning = job.kind === 'prompt_enhancement'
                const label = job.phase || job.message || (
                  job.status === 'held'
                    ? 'Ready — waiting for Start Queue'
                    : job.status === 'queued'
                      ? 'Waiting to start'
                      : 'Generating'
                )
                return (
                  <div key={job.id || `pending-${index}`} className="queue-card">
                    <div className="queue-card-row">
                      {job.status === 'running'
                        ? <Loader2 size={14} className="shrink-0 animate-spin text-accent-blue" />
                        : <Clock size={14} className="shrink-0 text-text-muted" />}
                      <div className="queue-card-meta">
                        <div className="queue-card-title">{label}</div>
                        <div className="queue-card-subtitle">
                          {job.kind === 'editor_export'
                            ? `Editor export · ${compactStatus(job.status)}`
                            : isPromptPlanning
                              ? 'Studio · AI planning'
                              : `Studio · ${compactStatus(job.status)}`}
                          {job.totalSteps > 0 ? ` · Step ${job.step}/${job.totalSteps}` : ''}
                          {job.generationEtaSeconds != null
                            ? ` · ${formatEtaDuration(job.generationEtaSeconds)} remaining`
                            : ''}
                        </div>
                      </div>
                      {!isPromptPlanning && (
                        <button
                          type="button"
                          onClick={() => { if (job.id) stopGeneration(job.id) }}
                          disabled={!job.id}
                          className="shell-icon-button hover:text-red-400 disabled:opacity-30"
                          title={!job.id
                            ? 'Waiting for the server to accept this job'
                            : job.status === 'held'
                              ? 'Remove held generation'
                              : job.status === 'queued'
                                ? 'Cancel queued generation'
                                : 'Stop generation'}
                          aria-label="Cancel job"
                        >
                          {job.status === 'held' || job.status === 'queued'
                            ? <X size={13} />
                            : <Square size={12} />}
                        </button>
                      )}
                    </div>
                    <div className="queue-progress">
                      <div
                        className={`queue-progress-fill bg-accent-blue ${percent === 0 && job.status === 'running' ? 'is-indeterminate' : ''}`}
                        style={percent > 0 ? { width: `${percent}%` } : undefined}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        )}

        {directorEntries.length > 0 && (
          <section className="queue-section">
            <div className="queue-section-header">
              <div className="queue-section-title-group">
                <span>Director</span>
                <span className="queue-section-meta">{pendingDirectorCount} waiting</span>
              </div>
              {directorQueue?.running && !directorQueue.paused ? (
                <button
                  type="button"
                  onClick={() => void pauseDirectorQueue()}
                  disabled={directorQueueLoading}
                  className="queue-section-action is-warning"
                  title="Finish the active Director project, then stop dispatching"
                >
                  <Pause size={11} /> Pause after current
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void startAllQueues()}
                  disabled={(startableDirectorCount === 0 && studioHeldCount === 0) || directorQueueLoading || startingAll}
                  className="queue-section-action is-success"
                  title="Start queue"
                >
                  {startingAll ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                  Start queue
                </button>
              )}
            </div>
            <div className="queue-list">
              {directorEntries.map((entry, index) => (
                <div key={entry.id} className="queue-card is-row">
                  {entry.status === 'running'
                    ? <Loader2 size={13} className="shrink-0 animate-spin text-accent-blue" />
                    : entry.status === 'completed'
                      ? <Check size={13} className="shrink-0 text-indicator-success" />
                      : <Clock size={13} className="shrink-0 text-text-muted" />}
                  <button
                    type="button"
                    onClick={() => {
                      if (entry.status === 'awaiting_review' && entry.pipeline_id) {
                        void useStore.getState().reattachDirectorPipeline(entry.pipeline_id)
                        setAppSection('director')
                      } else void openDirectorEntry(entry.id)
                    }}
                    disabled={directorQueueLoading}
                    className="queue-card-body"
                    title={entry.error || entry.message || entry.scene_description}
                  >
                    <div className="queue-card-title">
                      {entry.scene_description || `${entry.pipeline_type.replace(/_/g, ' ')} project`}
                    </div>
                    <div className={`queue-card-subtitle ${entry.status === 'failed' ? 'is-error' : ''}`}>
                      {compactStatus(entry.status)} · {entry.error || entry.message || entry.video_model}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (entry.status === 'awaiting_review' && entry.pipeline_id) {
                        void useStore.getState().reattachDirectorPipeline(entry.pipeline_id)
                        setAppSection('director')
                      } else void openDirectorEntry(entry.id)
                    }}
                    disabled={directorQueueLoading}
                    className="shell-icon-button"
                    title="Open Director project"
                    aria-label="Open Director project"
                  >
                    <Pencil size={12} />
                  </button>
                  {entry.status !== 'running' && entry.status !== 'awaiting_review' && (
                    <>
                      <button
                        type="button"
                        onClick={() => void moveDirectorQueueEntry(entry.id, -1)}
                        disabled={index === 0 || directorQueueLoading}
                        className="shell-icon-button"
                        title="Move up"
                        aria-label="Move up"
                      >
                        <ArrowUp size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={() => void moveDirectorQueueEntry(entry.id, 1)}
                        disabled={index === directorEntries.length - 1 || directorQueueLoading}
                        className="shell-icon-button"
                        title="Move down"
                        aria-label="Move down"
                      >
                        <ArrowDown size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeDirectorQueueEntry(entry.id)}
                        disabled={directorQueueLoading}
                        className="shell-icon-button hover:text-red-400"
                        title="Remove from queue"
                        aria-label="Remove from queue"
                      >
                        <Trash2 size={12} />
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}


import type { DirectorAnalyzeProgress } from '../types'

type AnalysisStatus = { step: string; detail: string; current: number; total: number }

/** Owns one polling session. Late responses cannot resurrect finished work. */
export function trackAnalysisProgress(
  fetchStatus: () => Promise<AnalysisStatus>,
  publish: (progress: DirectorAnalyzeProgress) => void,
  isCurrent: () => boolean,
) {
  let active = true
  let pending = false
  let latest: DirectorAnalyzeProgress = { current: 0, total: 0, message: 'Analyzing audio', status: 'running' }
  const emit = () => { if (isCurrent()) publish(latest) }
  emit()
  const refresh = async () => {
    if (!active || pending || !isCurrent()) return
    pending = true
    try {
      const status = await fetchStatus()
      if (!active || !isCurrent() || !status.step) return
      const total = Math.max(0, Number(status.total) || 0)
      latest = {
        current: Math.min(total, Math.max(0, Number(status.current) || 0)),
        total,
        message: status.detail || status.step,
        status: 'running',
      }
      emit()
    } catch { /* A failed status probe must not fail the analysis request. */ }
    finally { pending = false }
  }
  return {
    refresh,
    finish(status: 'done' | 'error') {
      if (!active) return
      active = false
      latest = { ...latest, status, current: status === 'done' ? latest.total : latest.current }
      emit()
    },
    cancel() { active = false },
  }
}

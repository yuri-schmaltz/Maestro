import { useState } from 'react'
import { getFileUrl, selectSceneTake } from '../../api/client'
import { useStore } from '../../stores/useStore'
import type { PipelineClipState } from '../../types'

export function SceneTakes({ pid, clip, busy }: { pid: string; clip: PipelineClipState; busy: boolean }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const choose = async (kind: 'image' | 'video', filename: string) => {
    setSaving(true)
    setError('')
    try {
      await selectSceneTake(pid, clip.index, kind, filename)
      await useStore.getState().loadSavedPipeline(pid)
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to select take') }
    finally { setSaving(false) }
  }
  return <div className="space-y-2">
    {(['image', 'video'] as const).map(kind => {
      const takes = clip[`${kind}_takes`] || []
      if (takes.length < 2) return null
      return <details key={kind} className="text-xs border border-border rounded p-2">
        <summary>Compare {takes.length} {kind} takes</summary>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
          {takes.map((take, index) => {
            const selected = take.filename === (kind === 'video' ? clip.video_filename : clip.start_image_filename)
            return <div key={take.filename} className={`border rounded p-2 ${selected ? 'border-green-500' : 'border-border'}`}>
              {kind === 'video'
                ? <video src={getFileUrl(take.filename)} controls preload="none" className="w-full aspect-video bg-black" />
                : <img src={getFileUrl(take.filename)} alt={`Take ${index + 1}`} className="w-full aspect-video object-contain" />}
              <p className="text-[10px] mt-1">Take {index + 1}{selected ? ' · selected' : ''}</p>
              <details className="text-[10px] text-text-muted"><summary>Prompt and source settings</summary><pre className="whitespace-pre-wrap break-all max-h-44 overflow-auto">{JSON.stringify(take.settings, null, 2)}</pre></details>
              <button disabled={busy || saving || selected} className="text-accent-blue text-[10px] mt-2 disabled:opacity-40" onClick={() => void choose(kind, take.filename)}>
                {kind === 'video' ? 'Approve this take' : 'Use this image'}
              </button>
            </div>
          })}
        </div>
        <p className="text-[10px] text-text-muted mt-2">The selected take is used for future rejoin and Director imports into Editor. Existing timelines keep their current media.</p>
      </details>
    })}
    {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
  </div>
}

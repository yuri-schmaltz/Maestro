/* eslint-disable react-refresh/only-export-components -- shared options between
   ProjectSetup form chips and the Director right-column override live here
   so the two surfaces stay in lockstep. */
import { useEffect, useMemo, useState } from 'react'
import { Film, ImagePlus, Music, X } from 'lucide-react'
import type { ProjectSetupDefaults, AspectRatio, ResolutionPreset, GenerationMode } from '../../types'
import { DEFAULT_PROJECT_SETUP } from '../../types'
import { fetchModels, workspaceCoverUrl, type ApiModel } from '../../api/client'

/** AspectRatio options surfaced in the project-setup form. Mirrors
 *  `DirectorAspectRatioSelector` so the two surfaces pick from the
 *  same set; ultra-wide (21:9) only shows when the project's video
 *  model supports it. */
export const PROJECT_SETUP_ASPECT_RATIOS: ReadonlyArray<{ value: AspectRatio; label: string; desc: string }> = [
  { value: '16:9', label: '16:9', desc: 'Wide' },
  { value: '9:16', label: '9:16', desc: 'Portrait' },
  { value: '1:1', label: '1:1', desc: 'Square' },
  { value: '4:3', label: '4:3', desc: 'Classic' },
  { value: '3:4', label: '3:4', desc: 'Tall' },
  { value: '21:9', label: '21:9', desc: 'Cinema' },
]

/** Resolution preset options. `auto` is intentionally excluded because
 *  the project setup is what the user wants every generation to
 *  START with — "auto" is a per-take decision that lives on the
 *  right column of the Director. */
export const PROJECT_SETUP_RESOLUTIONS: ReadonlyArray<{ value: ResolutionPreset; label: string }> = [
  { value: '480p', label: '480p' },
  { value: '540p', label: '540p' },
  { value: '720p', label: '720p' },
  { value: '1080p', label: '1080p' },
]

/** One-click starting setups for the New project dialog. Only flags the
 *  fields a fresh project needs; model/advanced choices stay per-project
 *  because they depend on the installed catalog. */
export const PROJECT_SETUP_TEMPLATES: ReadonlyArray<{ value: string; label: string; desc: string; setup: Partial<ProjectSetupDefaults> }> = [
  { value: 'short-film', label: 'Short film', desc: '16:9 · 720p', setup: { aspect_ratio: '16:9', resolution: '720p' } },
  { value: 'reels', label: 'Reels', desc: '9:16 · 1080p', setup: { aspect_ratio: '9:16', resolution: '1080p' } },
  { value: 'cinema', label: 'Cinema', desc: '21:9 · 1080p', setup: { aspect_ratio: '21:9', resolution: '1080p' } },
  { value: 'square', label: 'Square', desc: '1:1 · 1080p', setup: { aspect_ratio: '1:1', resolution: '1080p' } },
]

export interface ProjectSetupFormProps {
  value: ProjectSetupDefaults
  onChange: (next: ProjectSetupDefaults) => void
  disabled?: boolean
  /** Render compact version (less spacing) — used inside the small
   *  Edit setup modal so it fits next to other controls. */
  compact?: boolean
  /** Workspace name used to preview an already-uploaded cover. Omit
   *  when the workspace doesn't exist yet (New project dialog) — a
   *  picked file is then held locally and reported via
   *  `onPendingCover` so the parent can upload it at save time. */
  workspaceName?: string | null
  /** Called with a picked-but-unsaved cover File (null when cleared).
   *  The parent uploads it on submit and writes the returned filename
   *  into `cover_image`. */
  onPendingCover?: (file: File | null) => void
}

/**
 * ProjectSetupForm — reusable fields editor for project-level choices.
 *
 * Used by both the New project dialog (ProjectsPage) and the per-card
 * Edit setup affordance. Each section is collapsible; defaults stay
 * open so the user sees the model pickers without having to expand
 * every group. Every change flows through `onChange` so the parent can
 * own the submit / persist logic (keep the source of truth in one
 * place — the form is a pure controlled component).
 */
export function ProjectSetupForm({
  value,
  onChange,
  disabled = false,
  compact = false,
  workspaceName = null,
  onPendingCover,
}: ProjectSetupFormProps) {
  const safeValue: ProjectSetupDefaults = { ...DEFAULT_PROJECT_SETUP, ...value }
  const [models, setModels] = useState<ApiModel[]>([])
  const [pendingCover, setPendingCover] = useState<File | null>(null)
  const [coverError, setCoverError] = useState('')
  const update = (patch: Partial<ProjectSetupDefaults>) => onChange({ ...safeValue, ...patch })

  useEffect(() => {
    let cancelled = false
    fetchModels()
      .then(data => {
        if (!cancelled) setModels(data.models || [])
      })
      .catch(() => { if (!cancelled) setModels([]) })
    return () => { cancelled = true }
  }, [])

  const pendingCoverUrl = useMemo(
    () => (pendingCover ? URL.createObjectURL(pendingCover) : null),
    [pendingCover],
  )
  useEffect(() => () => { if (pendingCoverUrl) URL.revokeObjectURL(pendingCoverUrl) }, [pendingCoverUrl])

  const pickCover = (file: File | null) => {
    setCoverError('')
    if (!file) {
      setPendingCover(null)
      onPendingCover?.(null)
      if (safeValue.cover_image) update({ cover_image: '' })
      return
    }
    const ext = (file.name.split('.').pop() || '').toLowerCase()
    if (!['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext)) {
      setCoverError('Cover must be a .png, .jpg, .jpeg, .webp or .bmp file.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setCoverError('Cover image too large (max 10 MB).')
      return
    }
    setPendingCover(file)
    onPendingCover?.(file)
  }
  const coverPreview = pendingCoverUrl
    || (safeValue.cover_image && workspaceName ? workspaceCoverUrl(workspaceName, safeValue.cover_image) : null)

  const supportsUltraWide = (safeValue.video_model || '').toLowerCase().startsWith('minimax_h3')
  const aspectOptions = PROJECT_SETUP_ASPECT_RATIOS.filter(opt => opt.value !== '21:9' || supportsUltraWide)

  // Both pickers list the full installed catalog (deduplicated, sorted
  // by display name) — every available model shows up. Empty string
  // means "use whatever the Studio already has", which lets the form
  // stay usable when the model catalog isn't loaded yet (offline /
  // first paint).
  const modelOptions = [
    { value: '', label: 'Use last selected' },
    ...[...models]
      .filter((m, i, arr) => arr.findIndex(o => o.model_type === m.model_type) === i)
      .sort((a, b) => (a.name || a.model_type).localeCompare(b.name || b.model_type))
      .map(m => ({ value: m.model_type, label: m.name || m.model_type })),
  ]

  const sectionCls = compact ? 'space-y-1.5' : 'space-y-2'

  return (
    <div className={`text-sm ${compact ? 'space-y-2.5' : 'space-y-3'}`}>
      {/* Cover — the project card thumbnail. The file is only uploaded
          when the parent saves (the workspace may not exist yet in the
          New project dialog), so a picked file is held locally and
          previewed until submit. */}
      <fieldset className={sectionCls} aria-label="Project cover">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Cover</legend>
        {coverPreview ? (
          <div className="relative">
            <img
              src={coverPreview}
              alt="Project cover preview"
              className="w-full h-28 object-contain bg-bg-tertiary rounded-lg border border-border"
              onError={e => { e.currentTarget.style.display = 'none' }}
            />
            <button
              type="button"
              onClick={() => pickCover(null)}
              disabled={disabled}
              aria-label="Remove cover image"
              title="Remove cover image"
              className="absolute top-1.5 right-1.5 bg-bg-primary/80 rounded-full p-1 hover:bg-bg-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <X size={12} className="text-text-muted" />
            </button>
            {pendingCover && (
              <span className="absolute bottom-1.5 left-1.5 text-2xs text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
                {pendingCover.name} · uploads on save
              </span>
            )}
          </div>
        ) : (
          <label className={`flex items-center gap-2 rounded-lg border border-dashed px-3 py-2 cursor-pointer transition-colors ${disabled ? 'opacity-50 cursor-not-allowed' : 'border-border hover:border-accent-blue'}`}>
            <ImagePlus size={14} className="text-accent-blue/70 shrink-0" />
            <span className="text-xs text-text-secondary">Upload a cover image (.png, .jpg, .webp, .bmp)</span>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.bmp"
              className="hidden"
              disabled={disabled}
              onChange={e => { pickCover(e.target.files?.[0] || null); e.target.value = '' }}
            />
          </label>
        )}
        {coverError && <p className="text-2xs text-red-400" role="alert">{coverError}</p>}
      </fieldset>

      {/* Skill — which Director workflow this project plans with.
          Chosen once here so the Director chat never asks again;
          changing it later re-syncs the Director through
          applyWorkspaceSetup. */}
      <fieldset className={sectionCls} aria-label="Director skill">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Skill</legend>
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Director skill">
          {([
            { id: 'music_video' as const, label: 'Music Video', desc: 'Automated music video from audio', Icon: Music },
            { id: 'short_film' as const, label: 'Short Film', desc: 'Dialogue-driven scenes from audio', Icon: Film },
          ]).map(({ id, label, desc, Icon }) => {
            const active = (safeValue.director_skill || 'music_video') === id
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={disabled}
                onClick={() => update({ director_skill: id })}
                className={`p-2.5 rounded-lg border text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                  active
                    ? 'border-accent-blue/60 bg-accent-blue/5'
                    : 'border-border hover:border-border-light'
                }`}
              >
                <Icon size={16} className={active ? 'text-accent-blue mb-1.5' : 'text-text-muted mb-1.5'} />
                <div className="text-xs font-medium text-text-primary">{label}</div>
                <div className="text-2xs text-text-muted mt-0.5">{desc}</div>
              </button>
            )
          })}
        </div>
      </fieldset>

      {/* Output — aspect + resolution. Always visible because every
          project needs a render format and "use whatever was last"
          is the worst possible default for a fresh project. */}
      <fieldset className={sectionCls} aria-label="Output format">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Output format</legend>
        <div className="flex gap-2">
          <div className="flex-1">
            <FormSelect
              label="Aspect ratio"
              value={safeValue.aspect_ratio || ''}
              onChange={next => update({ aspect_ratio: next as AspectRatio })}
              options={aspectOptions.map(opt => ({ value: opt.value, label: `${opt.label} — ${opt.desc}` }))}
              disabled={disabled}
            />
          </div>
          <div className="flex-1">
            <FormSelect
              label="Resolution"
              value={safeValue.resolution || ''}
              onChange={next => update({ resolution: next as ResolutionPreset })}
              options={PROJECT_SETUP_RESOLUTIONS.map(opt => ({ value: opt.value, label: opt.label }))}
              disabled={disabled}
            />
          </div>
        </div>
      </fieldset>

      {/* Workflow — Seamless (one continuous timeline across windows)
          and Auto (skip every review step). Both default to off so the
          Director always opens with manual review unless the project
          creator opted in. */}
      <fieldset className={sectionCls} aria-label="Workflow defaults">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Workflow</legend>
        <div className="grid grid-cols-2 gap-2">
          <label className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 select-none transition-all ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${safeValue.seamless ? 'border-accent-blue/60 bg-accent-blue/5' : 'border-border hover:border-border-light'}`}>
            <input
              type="checkbox"
              checked={Boolean(safeValue.seamless)}
              disabled={disabled}
              onChange={e => update({ seamless: e.target.checked })}
              className="accent-accent-blue w-3 h-3 shrink-0"
            />
            <span className="min-w-0">
              <span className="text-xs text-text-secondary block leading-tight">Seamless</span>
              <span className="text-2xs text-text-muted block leading-tight truncate">continuous sliding window</span>
            </span>
          </label>
          <label className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 select-none transition-all ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${safeValue.auto_mode ? 'border-red-500/60 bg-red-500/5' : 'border-border hover:border-border-light'}`}>
            <input
              type="checkbox"
              checked={Boolean(safeValue.auto_mode)}
              disabled={disabled}
              onChange={e => update({ auto_mode: e.target.checked })}
              className="accent-red-500 w-3 h-3 shrink-0"
            />
            <span className="min-w-0">
              <span className={`text-xs block leading-tight ${safeValue.auto_mode ? 'text-red-400' : 'text-text-secondary'}`}>Auto</span>
              <span className="text-2xs text-text-muted block leading-tight truncate">skip review steps</span>
            </span>
          </label>
        </div>
      </fieldset>

      {/* Models — picked once at project creation so every take
          starts from a known baseline. Both pickers list the full
          installed catalog. Empty string means "use whatever the
          Studio already has", which lets the form stay usable when
          the model catalog isn't loaded yet (offline / first paint). */}
      <fieldset className={sectionCls} aria-label="Default models">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Models</legend>
        <div className="flex gap-2">
          <div className="flex-1">
            <FormSelect
              label="Video model"
              value={safeValue.video_model || ''}
              onChange={next => update({ video_model: next })}
              options={modelOptions}
              disabled={disabled}
            />
          </div>
          <div className="flex-1">
            <FormSelect
              label="Image model"
              value={safeValue.image_model || ''}
              onChange={next => update({ image_model: next })}
              options={modelOptions}
              disabled={disabled}
            />
          </div>
        </div>
      </fieldset>

      {/* About — optional metadata shown on the project card. Kept at
          the bottom so the technical defaults stay the focus. */}
      <fieldset className={sectionCls} aria-label="About this project">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">About</legend>
        <label className="block">
          <span className="text-xs text-text-secondary block mb-1">Description</span>
          <textarea
            value={safeValue.description || ''}
            onChange={e => update({ description: e.target.value })}
            disabled={disabled}
            rows={2}
            placeholder="What is this project about?"
            className="w-full rounded-lg border border-border bg-bg-secondary px-2.5 py-1.5 text-xs text-text-primary resize-none disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:border-accent-blue"
          />
        </label>
        <label className="block">
          <span className="text-xs text-text-secondary block mb-1">Tags</span>
          <input
            type="text"
            value={(safeValue.tags || []).join(', ')}
            onChange={e => update({ tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })}
            disabled={disabled}
            placeholder="film, draft, reel"
            className="w-full rounded-lg border border-border bg-bg-secondary px-2.5 py-1.5 text-xs text-text-primary disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:border-accent-blue"
          />
        </label>
      </fieldset>
    </div>
  )
}

function FormSelect({
  label, value, onChange, options, disabled,
}: {
  label: string
  value: string
  onChange: (next: string) => void
  options: ReadonlyArray<{ value: string; label: string }>
  disabled?: boolean
}) {
  return (
    <label className="block">
      <span className="text-xs text-text-secondary block mb-1">{label}</span>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-lg border border-border bg-bg-secondary px-2.5 py-1.5 text-xs text-text-primary disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:border-accent-blue"
      >
        {options.map(opt => (
          <option key={opt.value || 'blank'} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </label>
  )
}

/** Compact summary used in the Project card chip ("Music Video · 16:9 · 720p · LTX-2"). */
export function ProjectSetupSummary({
  setup, videoModelLabel, imageModelLabel,
}: {
  setup?: ProjectSetupDefaults
  videoModelLabel?: string
  imageModelLabel?: string
}): string {
  if (!setup) return 'Default settings'
  const parts: string[] = []
  const skillLabel = setup.director_skill === 'short_film' ? 'Short Film'
    : setup.director_skill === 'music_video' ? 'Music Video' : undefined
  if (skillLabel) parts.push(skillLabel)
  if (setup.aspect_ratio) parts.push(setup.aspect_ratio)
  if (setup.resolution) parts.push(setup.resolution)
  if (setup.video_model) parts.push(videoModelLabel || shortModelLabel(setup.video_model))
  if (setup.image_model && !parts.includes(videoModelLabel || '') && setup.image_model !== setup.video_model) {
    parts.push(imageModelLabel || shortModelLabel(setup.image_model))
  }
  return parts.length ? parts.join(' · ') : 'Default settings'
}

/** Friendly model name from the catalog id ("ltx2_22B_distilled_1_1" → "LTX-2 Distilled"). */
export function shortModelLabel(modelType: string): string {
  if (!modelType) return ''
  return modelType
    .replace(/_/g, ' ')
    .replace(/\s+\d+\s*$/, '')
    .split(' ')
    .filter(Boolean)
    .map(part => part.match(/^[a-z]+$/i) ? part.toUpperCase() : part)
    .slice(0, 4)
    .join(' ')
}

/** Re-export GenerationMode typing helper to keep the imports next to the form. */
export type { GenerationMode }

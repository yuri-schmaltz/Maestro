/* eslint-disable react-refresh/only-export-components -- shared options between
   ProjectSetup form chips and the Director right-column override live here
   so the two surfaces stay in lockstep. */
import { useState } from 'react'
import { Film, Music } from 'lucide-react'
import type { ProjectSetupDefaults, AspectRatio, ResolutionPreset, GenerationMode } from '../../types'
import { DEFAULT_PROJECT_SETUP } from '../../types'
import { fetchModels, type ApiModel } from '../../api/client'
import { useEffect } from 'react'

/** Architectures that produce video output. Used to filter the model
 *  catalog into a video picker and an image picker without needing a
 *  per-model `kind` tag. Keep in sync with the architectures WanGP
 *  knows about — losing video models out of the picker would silently
 *  disable a route the user already used, which is worse UX than
 *  showing a model that picks the wrong picker row. */
const VIDEO_ARCHITECTURE_PREFIXES = ['ltx', 'wan', 'hunyuan', 'minimax', 'svd', 'h3']

/** Architectures that produce image output. The "everything else"
 *  fallback would also work, but an explicit allowlist catches
 *  audio/TTS models that shouldn't show in either picker. */
const IMAGE_ARCHITECTURE_PREFIXES = ['flux', 'sdxl', 'sd3', 'sd_', 'stablediffusion', 'klein', 'ace_step']

function isVideoModel(model: ApiModel): boolean {
  const arch = (model.architecture || '').toLowerCase()
  return VIDEO_ARCHITECTURE_PREFIXES.some(prefix => arch.startsWith(prefix))
}
function isImageModel(model: ApiModel): boolean {
  const arch = (model.architecture || '').toLowerCase()
  return IMAGE_ARCHITECTURE_PREFIXES.some(prefix => arch.startsWith(prefix))
}

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
  /** When true (default) only surface video models whose director
   *  capability matrix shows at least one compatible pipeline type,
   *  so a project created against a model that Director can't drive
   *  fails fast at creation time instead of first generation. */
  filterDirectorCapable?: boolean
  disabled?: boolean
  /** Render compact version (less spacing) — used inside the small
   *  Edit setup modal so it fits next to other controls. */
  compact?: boolean
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
  filterDirectorCapable = true,
  disabled = false,
  compact = false,
}: ProjectSetupFormProps) {
  const safeValue: ProjectSetupDefaults = { ...DEFAULT_PROJECT_SETUP, ...value }
  const [models, setModels] = useState<ApiModel[]>([])

  useEffect(() => {
    let cancelled = false
    fetchModels()
      .then(data => {
        if (!cancelled) setModels(data.models || [])
      })
      .catch(() => { if (!cancelled) setModels([]) })
    return () => { cancelled = true }
  }, [])

  const update = (patch: Partial<ProjectSetupDefaults>) => onChange({ ...safeValue, ...patch })
  const supportsUltraWide = (safeValue.video_model || '').toLowerCase().startsWith('minimax_h3')
  const aspectOptions = PROJECT_SETUP_ASPECT_RATIOS.filter(opt => opt.value !== '21:9' || supportsUltraWide)

  const videoModels = models.filter(m => {
    if (!isVideoModel(m)) return false
    if (!filterDirectorCapable) return true
    // A model that has at least one "compatible: true" Director
    // capability is usable for at least one pipeline. Without this
    // check, models that the backend blocks for every pipeline type
    // would silently show as a project option and the user would
    // hit the "model not supported" wall at first generation.
    return Boolean(m.director && Object.values(m.director).some(value => value && typeof value === 'object' && 'compatible' in (value as object) && (value as { compatible?: boolean }).compatible))
  })
  const imageModels = models.filter(m => isImageModel(m))

  const sectionCls = compact ? 'space-y-2' : 'space-y-3'

  return (
    <div className={`text-sm ${compact ? 'space-y-3' : 'space-y-4'}`}>
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
                className={`p-3 rounded-lg border text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
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
        <div className="flex flex-wrap items-center gap-4">
          <label className={`flex items-center gap-1.5 select-none ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={Boolean(safeValue.seamless)}
              disabled={disabled}
              onChange={e => update({ seamless: e.target.checked })}
              className="accent-accent-blue w-3 h-3"
            />
            <span className="text-xs text-text-secondary">Seamless</span>
            <span className="text-2xs text-text-muted">(continuous sliding window)</span>
          </label>
          <label className={`flex items-center gap-1.5 select-none ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={Boolean(safeValue.auto_mode)}
              disabled={disabled}
              onChange={e => update({ auto_mode: e.target.checked })}
              className="accent-red-500 w-3 h-3"
            />
            <span className={`text-xs ${safeValue.auto_mode ? 'text-red-400' : 'text-text-secondary'}`}>Auto</span>
            <span className="text-2xs text-text-muted">(skip review steps)</span>
          </label>
        </div>
      </fieldset>

      {/* Models — picked once at project creation so every take
          starts from a known baseline. Empty string means "use whatever
          the Studio already has", which lets the form stay usable when
          the model catalog isn't loaded yet (offline / first paint). */}
      <fieldset className={sectionCls} aria-label="Default models">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Models</legend>
        <div className="flex gap-2">
          <div className="flex-1">
            <FormSelect
              label="Video model"
              value={safeValue.video_model || ''}
              onChange={next => update({ video_model: next })}
              options={[
                { value: '', label: 'Use last selected' },
                ...videoModels.map(m => ({ value: m.model_type, label: m.name || m.model_type })),
              ]}
              disabled={disabled}
            />
          </div>
          <div className="flex-1">
            <FormSelect
              label="Image model"
              value={safeValue.image_model || ''}
              onChange={next => update({ image_model: next })}
              options={[
                { value: '', label: 'Use last selected' },
                ...imageModels.map(m => ({ value: m.model_type, label: m.name || m.model_type })),
              ]}
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

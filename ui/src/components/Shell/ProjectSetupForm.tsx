/* eslint-disable react-refresh/only-export-components -- shared options between
   ProjectSetup form chips and the Director right-column override live here
   so the two surfaces stay in lockstep. */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Sparkles, Layers } from 'lucide-react'
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

/** Architectures that produce audio (used when music_source = generate). */
const AUDIO_ARCHITECTURE_PREFIXES = ['ace', 'musicgen', 'audioldm', 'tts']

function isVideoModel(model: ApiModel): boolean {
  const arch = (model.architecture || '').toLowerCase()
  return VIDEO_ARCHITECTURE_PREFIXES.some(prefix => arch.startsWith(prefix))
}
function isImageModel(model: ApiModel): boolean {
  const arch = (model.architecture || '').toLowerCase()
  return IMAGE_ARCHITECTURE_PREFIXES.some(prefix => arch.startsWith(prefix))
}
function isAudioModel(model: ApiModel): boolean {
  const arch = (model.architecture || '').toLowerCase()
  return AUDIO_ARCHITECTURE_PREFIXES.some(prefix => arch.startsWith(prefix))
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
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [lorasOpen, setLorasOpen] = useState(false)

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
      {/* Output — aspect + resolution. Always visible because every
          project needs a render format and "use whatever was last"
          is the worst possible default for a fresh project. */}
      <fieldset className={sectionCls} aria-label="Output format">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Output format</legend>
        <div>
          <span className="text-xs text-text-secondary block mb-1.5">Aspect ratio</span>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Aspect ratio">
            {aspectOptions.map(opt => (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={safeValue.aspect_ratio === opt.value}
                onClick={() => update({ aspect_ratio: opt.value })}
                disabled={disabled}
                className={`px-2.5 py-1.5 rounded-lg border text-xs transition-all ${
                  safeValue.aspect_ratio === opt.value
                    ? 'border-accent-blue bg-accent-blue/10 text-text-primary'
                    : 'border-border text-text-muted hover:border-border-light hover:text-text-secondary'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <span className="font-medium">{opt.label}</span>
                <span className="ml-1 text-2xs opacity-60">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="text-xs text-text-secondary block mb-1.5">Resolution</span>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Resolution">
            {PROJECT_SETUP_RESOLUTIONS.map(opt => (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={safeValue.resolution === opt.value}
                onClick={() => update({ resolution: opt.value })}
                disabled={disabled}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                  safeValue.resolution === opt.value
                    ? 'border-accent-blue bg-accent-blue/10 text-text-primary'
                    : 'border-border text-text-muted hover:border-border-light hover:text-text-secondary'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {opt.label}
              </button>
            ))}
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
      </fieldset>

      {/* Audio — source shape (upload vs generate) and the music model
          used when source = generate. Skipped entirely from
          short-film story-driven projects where audio is created
          from voice references instead of a song. */}
      <fieldset className={sectionCls} aria-label="Audio defaults">
        <legend className="text-2xs uppercase tracking-wider text-text-muted mb-1">Audio</legend>
        <div className="flex gap-1.5 p-1 bg-bg-tertiary rounded-lg border border-border">
          {(['upload', 'generate'] as const).map(opt => (
            <button
              key={opt}
              type="button"
              onClick={() => update({ music_source: opt })}
              disabled={disabled}
              className={`flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-all ${
                safeValue.music_source === opt
                  ? 'bg-accent-blue text-white'
                  : 'text-text-secondary hover:text-text-primary'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {opt === 'upload' ? 'Upload a track' : 'Generate a track'}
            </button>
          ))}
        </div>
        {safeValue.music_source === 'generate' && (
          <FormSelect
            label="Music model"
            value={safeValue.music_model || ''}
            onChange={next => update({ music_model: next })}
            options={[
              { value: '', label: 'Use default music model' },
              ...models
                .filter(m => isAudioModel(m) || (m.name || '').toLowerCase().includes('music'))
                .map(m => ({ value: m.model_type, label: m.name || m.model_type })),
            ]}
            disabled={disabled}
          />
        )}
      </fieldset>

      {/* Default LoRAs — collapsed by default; the per-card LoRA
          pickers keep existing in Director so a power user can still
          activate one ad-hoc. */}
      <CollapsibleSection
        title="Default LoRAs"
        description="Apply these LoRAs to every Director generation in this project."
        icon={Layers}
        open={lorasOpen}
        onToggle={() => setLorasOpen(!lorasOpen)}
      >
        <p className="text-2xs text-text-muted leading-relaxed">
          Default LoRAs land in this section when the Studio's checkbox-driven picker is
          ready to handle the JSON shape. For now, use the Director side (right column)
          to activate LoRAs per take; the default remains the project-creator's choice.
        </p>
        <p className="text-2xs text-text-muted/70 leading-relaxed mt-1.5">
          Current selection:&nbsp;
          <code className="text-text-secondary">
            {countLoras(safeValue.default_image_loras)} image,&nbsp;
            {countLoras(safeValue.default_video_loras)} video
          </code>
        </p>
      </CollapsibleSection>

      {/* Advanced — collapsed by default so the average project creator
          never sees scary knobs. Existing-project editing unlocks it
          for users who already know what they're tweaking. */}
      <CollapsibleSection
        title="Advanced defaults"
        description="Spatial upsampling, film grain, inference steps, H3 turbo mode. Applied to every generation unless overridden per-take."
        icon={Sparkles}
        open={advancedOpen}
        onToggle={() => setAdvancedOpen(!advancedOpen)}
      >
        <p className="text-2xs text-text-muted leading-relaxed">
          Advanced defaults live as a free-form JSON blob today. Each future knob will
          get its own picker here; until then, power users can hand-edit this project's
          <code className="text-text-secondary mx-1">outputs/&lt;project&gt;/setup.json</code>
          and refresh the page.
        </p>
      </CollapsibleSection>
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

function CollapsibleSection({
  title, description, icon: Icon, open, onToggle, children,
}: {
  title: string
  description: string
  icon: typeof ChevronDown
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <fieldset className="border border-border/40 rounded-lg">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <span className="flex items-center gap-1.5">
          <Icon size={12} className="text-text-secondary" />
          <span className="text-xs text-text-secondary">{title}</span>
        </span>
        {open ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
      </button>
      <p className="px-3 pb-2 text-2xs text-text-muted leading-relaxed">{description}</p>
      {open && (
        <div className="px-3 pb-3 space-y-2 border-t border-border/40 pt-2.5">
          {children}
        </div>
      )}
    </fieldset>
  )
}

function countLoras(record: unknown): number {
  if (!record || typeof record !== 'object') return 0
  const value = (record as Record<string, unknown>).activated_loras
  return Array.isArray(value) ? value.length : 0
}

/** Compact summary used in the Project card chip ("16:9 · 720p · LTX-2"). */
export function ProjectSetupSummary({
  setup, videoModelLabel, imageModelLabel,
}: {
  setup?: ProjectSetupDefaults
  videoModelLabel?: string
  imageModelLabel?: string
}): string {
  if (!setup) return 'Default settings'
  const parts: string[] = []
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

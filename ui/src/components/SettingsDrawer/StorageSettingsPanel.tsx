import { useEffect, useState } from 'react'
import { FolderOpen, RotateCcw, Save, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useStore } from '../../stores/useStore'

/**
 * Storage settings: where new project workspaces are created on disk.
 *
 * Defaults to the OS-native user Videos folder (``~/Videos`` on Linux
 * and macOS, ``%USERPROFILE%\\Videos`` on Windows) so generated media
 * lands in the same place as the user's other videos, photos and
 * backups. A user can override the path here — Maestro validates that
 * the chosen folder exists and is writable before persisting.
 *
 * Empty input reverts to the default; the backend then falls back to
 * the OS-native Videos folder on the next call. The path is stored in
 * ``services.projects_root_path`` inside the Maestro server config.
 */
export function StorageSettingsPanel() {
  const projectsRoot = useStore(s => s.projectsRoot)
  const loadProjectsRoot = useStore(s => s.loadProjectsRoot)
  const setProjectsRoot = useStore(s => s.setProjectsRoot)

  // Local draft of the path. Decoupled from the store so the user can
  // type freely without round-tripping every keystroke to the backend.
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  // Hydrate once on mount. The drawer may be opened and closed many
  // times without unmounting; the store keeps the previous value.
  useEffect(() => {
    if (projectsRoot === null) loadProjectsRoot()
  }, [projectsRoot, loadProjectsRoot])

  // Sync the local draft when the backend value resolves. We key on
  // the persisted string rather than the whole object so the user's
  // in-flight typing isn't clobbered after they save (which mutates
  // the object identity but leaves the string stable until the next
  // external change).
  const configuredPath = projectsRoot?.configured_path
  useEffect(() => {
    if (configuredPath !== undefined) setDraft(configuredPath)
  }, [configuredPath])

  const effective = projectsRoot?.effective_path ?? ''
  const isDefault = !draft.trim()
  const isDirty = draft.trim() !== (projectsRoot?.configured_path ?? '')

  const onSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await setProjectsRoot(draft.trim())
      setSavedAt(Date.now())
      // Clear the draft flag so the "Saved" badge stops showing after
      // a moment — keeps the UI from claiming "just saved" forever.
      setTimeout(() => setSavedAt(prev => prev === savedAt ? null : prev), 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save projects root')
    } finally {
      setSaving(false)
    }
  }

  const onReset = () => {
    setDraft('')
    setError(null)
  }

  return (
    <section className="settings-panel">
      <header>
        <h2>Storage</h2>
        <p>Choose where Maestro creates new project folders. The default
          lives in your system Videos folder so generated media is found
          by your file manager, gallery apps and backup pipelines.</p>
      </header>

      <div className="settings-card">
        <label className="settings-row">
          <span className="settings-row-label">
            <FolderOpen size={16} aria-hidden="true" />
            Projects folder
          </span>
          <div className="settings-row-control">
            <input
              type="text"
              className="settings-text-input"
              value={draft}
              onChange={e => { setDraft(e.target.value); setError(null) }}
              placeholder={projectsRoot?.default_path ?? 'outputs'}
              spellCheck={false}
              autoComplete="off"
              aria-label="Projects root path"
            />
            <div className="settings-row-actions">
              {!isDefault && (
                <button
                  type="button"
                  className="ghost"
                  onClick={onReset}
                  disabled={saving}
                  aria-label="Reset to default"
                  title="Clear the custom path and use the OS-default folder"
                >
                  <RotateCcw size={15} aria-hidden="true" /> Default
                </button>
              )}
              <button
                type="button"
                className="primary"
                onClick={onSave}
                disabled={saving || !isDirty}
                aria-label="Save projects folder"
              >
                <Save size={15} aria-hidden="true" /> {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </label>

        {error && (
          <p className="settings-feedback error" role="alert">
            <AlertCircle size={15} aria-hidden="true" /> {error}
          </p>
        )}

        {!error && savedAt && (
          <p className="settings-feedback success" role="status">
            <CheckCircle2 size={15} aria-hidden="true" /> Saved. New
            projects will be created under this folder.
          </p>
        )}

        <p className="settings-row-hint">
          Leave the field empty to use the OS-default Videos folder.
          Maestro validates that the chosen folder exists and is writable
          before saving. Existing projects are not moved automatically —
          switch the path here and use your file manager to relocate
          them if you want a single folder for everything.
        </p>
      </div>

      <div className="settings-card settings-card-muted">
        <h3>Effective location</h3>
        <dl className="settings-definitions">
          <div>
            <dt>Effective path</dt>
            <dd>
              <code>{effective || '—'}</code>
            </dd>
          </div>
          <div>
            <dt>Default fallback</dt>
            <dd>
              <code>{projectsRoot?.default_path ?? '—'}</code>
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              {projectsRoot?.exists === false && (
                <span className="settings-feedback error">
                  <AlertCircle size={15} aria-hidden="true" /> Path does
                  not exist on disk
                </span>
              )}
              {projectsRoot?.exists && projectsRoot?.writable === false && (
                <span className="settings-feedback error">
                  <AlertCircle size={15} aria-hidden="true" /> Path is
                  not writable
                </span>
              )}
              {projectsRoot?.exists && projectsRoot?.writable && (
                <span className="settings-feedback success">
                  <CheckCircle2 size={15} aria-hidden="true" /> Exists and
                  is writable
                </span>
              )}
              {!projectsRoot && 'Loading…'}
            </dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

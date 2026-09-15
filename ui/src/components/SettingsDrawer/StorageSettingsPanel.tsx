import { useEffect, useState } from 'react'
import { FolderOpen, RotateCcw, Save, AlertCircle, CheckCircle2, HardDrive } from 'lucide-react'
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
 *
 * Layout: single-column because the content is intrinsically sequential
 * (input + status). Uses the shared ``.settings-panel`` primitives so
 * it matches the typography and spacing of every other Configurations
 * tab.
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

  useEffect(() => {
    // Hydrate once on mount. The drawer may be opened and closed many
    // times without unmounting; the store keeps the previous value.
    if (projectsRoot === null) loadProjectsRoot()
  }, [projectsRoot, loadProjectsRoot])

  // Sync the local draft when the backend value resolves. Keying on
  // the configured string (not the whole object) keeps the user's
  // in-flight typing from being clobbered after they save.
  const configuredPath = projectsRoot?.configured_path
  useEffect(() => {
    if (configuredPath !== undefined) setDraft(configuredPath)
  }, [configuredPath])

  const isDirty = draft.trim() !== (projectsRoot?.configured_path ?? '')
  const isEmpty = !draft.trim()

  const onSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await setProjectsRoot(draft.trim())
      setSavedAt(Date.now())
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
    <section className="settings-panel" aria-label="Storage settings">
      <header className="settings-panel-header">
        <h2><FolderOpen size={18} aria-hidden="true" /> Storage</h2>
        <p>Choose where Maestro creates new project folders. The
          default lives in your system Videos folder so generated
          media is found by your file manager, gallery apps and
          backup pipelines.</p>
      </header>

      <div className="settings-group">
        <div className="settings-group-header">
          <h3>Projects folder</h3>
        </div>

        <div className="settings-card">
          <div className="settings-row">
            <label className="settings-row-label" htmlFor="projects-root-path">
              <FolderOpen size={16} aria-hidden="true" />
              Projects root
            </label>
            <div className="settings-row-control">
              <input
                id="projects-root-path"
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
                <button
                  type="button"
                  className="settings-button settings-button-ghost"
                  onClick={onReset}
                  disabled={saving || isEmpty}
                  aria-label="Reset to default"
                  title="Clear the custom path and use the OS-default folder"
                >
                  <RotateCcw size={15} aria-hidden="true" /> Default
                </button>
                <button
                  type="button"
                  className="settings-button settings-button-primary"
                  onClick={onSave}
                  disabled={saving || !isDirty}
                  aria-label="Save projects folder"
                >
                  <Save size={15} aria-hidden="true" /> {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          </div>

          {error && (
            <p className="settings-feedback error" role="alert">
              <AlertCircle size={15} aria-hidden="true" /> {error}
            </p>
          )}

          {!error && savedAt && (
            <p className="settings-feedback success" role="status">
              <CheckCircle2 size={15} aria-hidden="true" /> Saved.
              New projects will be created under this folder.
            </p>
          )}

          <p className="settings-row-hint">
            Leave the field empty to use the OS-default Videos folder.
            Maestro validates that the chosen folder exists and is
            writable before saving. Existing projects are not moved
            automatically — switch the path here and use your file
            manager to relocate them if you want a single folder
            for everything.
          </p>
        </div>
      </div>

      <div className="settings-group">
        <div className="settings-group-header">
          <h3>Effective location</h3>
          <p>Where Maestro currently creates new workspaces.</p>
        </div>
        <div className="settings-card settings-card-muted">
          <dl className="settings-definitions">
            <div>
              <dt>Effective path</dt>
              <dd>
                <code>{projectsRoot?.effective_path ?? '—'}</code>
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
                {!projectsRoot && 'Loading…'}
                {projectsRoot?.exists === false && (
                  <span className="settings-feedback error">
                    <AlertCircle size={15} aria-hidden="true" /> Path
                    does not exist on disk
                  </span>
                )}
                {projectsRoot?.exists && projectsRoot?.writable === false && (
                  <span className="settings-feedback error">
                    <AlertCircle size={15} aria-hidden="true" /> Path
                    is not writable
                  </span>
                )}
                {projectsRoot?.exists && projectsRoot?.writable && (
                  <span className="settings-feedback success">
                    <CheckCircle2 size={15} aria-hidden="true" /> Exists
                    and is writable
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="settings-group">
        <div className="settings-group-header">
          <h3>Storage Manager</h3>
          <p>Disk usage, duplicate reclaim and cleanup utilities. Opens a
            full-screen dashboard.</p>
        </div>
        <div className="settings-card">
          <button
            type="button"
            onClick={() => useStore.getState().setStorageDashboardOpen(true)}
            className="settings-button settings-button-ghost"
            style={{ width: '100%', justifyContent: 'flex-start' }}
          >
            <HardDrive size={13} className="text-accent-blue" aria-hidden="true" />
            <span className="flex-1 text-left">Open Storage Manager</span>
            <span className="text-2xs text-text-muted">usage, duplicates, cleanup</span>
          </button>
        </div>
      </div>
    </section>
  )
}

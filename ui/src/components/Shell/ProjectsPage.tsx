import { useState } from 'react'
import { ArrowRight, Check, Clapperboard, Copy, Film, FolderOpen, Images, Loader2, Pin, PinOff, Plus, Search, Settings, Trash2 } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { useWorkspaceSlice } from '../../stores/workspaceSelectors'
import type { AppSection, ProjectSetupDefaults } from '../../types'
import { DEFAULT_PROJECT_SETUP } from '../../types'
import { saveWorkspaceSetup, uploadWorkspaceCover, deleteWorkspaceCover, workspaceCoverUrl, type Workspace } from '../../api/client'
import { ProjectSetupForm, ProjectSetupSummary, PROJECT_SETUP_TEMPLATES } from './ProjectSetupForm'

/**
 * Projects page — one-to-one with workspaces on the backend.
 *
 * Each project IS a workspace: a folder under `outputs/` that stores all
 * the generated media, Editor projects and Director productions scoped
 * to that project. Creating a project creates its workspace folder;
 * deleting a project removes the folder and everything inside.
 *
 * The implicit `default` workspace (the root `outputs/` directory) is
 * intentionally hidden — it exists on the backend for backward compat
 * with pre-projects generations, but it's not a user-facing concept.
 * Showing it would let users "open" a catch-all bucket and defeat the
 * per-project organization this page exists to enforce.
 *
 * Project setup (aspect ratio, resolution, models, workflow, audio,
 * LoRAs, advanced) lives in this page. The New project dialog collects
 * the choices up front so the Director opens with project defaults
 * already applied; the Edit setup affordance on each card edits the
 * stored setup.json for an existing project. Runtime overrides happen
 * inside the Director's right column and only flow into
 * `director_ui_snapshot` (per-take), keeping the project setup clean.
 */
export function ProjectsPage() {
  const workspaces = useWorkspaceSlice('workspaces')
  const active = useWorkspaceSlice('activeWorkspace')
  const createWorkspace = useStore(s => s.createWorkspace)
  const switchWorkspace = useStore(s => s.switchWorkspace)
  const deleteWorkspace = useStore(s => s.deleteWorkspace)
  const saveSetupAction = useStore(s => s.saveWorkspaceSetup)
  const navigate = useStore(s => s.setAppSection)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [setup, setSetup] = useState<ProjectSetupDefaults>(DEFAULT_PROJECT_SETUP)
  const [destination, setDestination] = useState<AppSection>('director')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  // Cover image picked in the dialog but not uploaded yet (the New
  // project workspace doesn't exist until submit). Uploaded as part of
  // create/saveEdit, then cleared.
  const [pendingCover, setPendingCover] = useState<File | null>(null)
  // Cover filename the dialog started with — used to detect a removal
  // that must also delete the stored file on save.
  const [initialCover, setInitialCover] = useState('')

  const userProjects = workspaces
    .filter(w => w.name !== 'default')
    .sort((a, b) => {
      const aPinned = Boolean(a.setup?.pinned), bPinned = Boolean(b.setup?.pinned)
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  const hasProjects = userProjects.length > 0
  const visible = userProjects.filter(w => w.name.toLowerCase().includes(query.toLowerCase()))

  const open = async (workspace: string, section: AppSection) => {
    setBusy(workspace); setError(null)
    try {
      await switchWorkspace(workspace)
      if (useStore.getState().activeWorkspace !== workspace) throw new Error('Could not open this project. Please try again.')
      navigate(section)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not open project.') }
    finally { setBusy(null) }
  }
  const create = async () => {
    const value = name.trim().replace(/\s+/g, '-')
    if (!value) return
    setBusy('new'); setError(null)
    try {
      // createWorkspace hits POST /api/v1/workspaces which creates the
      // folder under outputs/ AND sets it as the active workspace in a
      // single round-trip — same operation, two effects. We then route
      // the user to Director so the new project is immediately usable.
      // After the folder exists we persist the ProjectSetup; the form
      // values flow into Director fields via loadWorkspaceSetup on next
      // mount via the store. Done sequentially so a failed save never
      // strands a project on disk in an unexpected shape.
      await createWorkspace(value)
      // A picked cover can only be uploaded now that the folder
      // exists — merge the stored filename into the setup payload.
      let nextSetup = setup
      if (pendingCover) {
        const { cover_image } = await uploadWorkspaceCover(value, pendingCover)
        nextSetup = { ...nextSetup, cover_image }
      }
      await saveSetupAction(nextSetup)
      setCreating(false); setName('')
      setSetup(DEFAULT_PROJECT_SETUP)
      setPendingCover(null)
      setInitialCover('')
      setDestination('director')
      navigate(destination)
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create project.') }
    finally { setBusy(null) }
  }
  const openDuplicate = (workspace: Workspace) => {
    setError(null)
    // The duplicate gets a fresh folder without the original's cover
    // file, so the reference must not carry over either.
    setSetup({ ...DEFAULT_PROJECT_SETUP, ...(workspace.setup || {}), pinned: false, cover_image: '' })
    setPendingCover(null)
    setInitialCover('')
    setName(`${workspace.name.trim().replace(/\s+/g, '-')}-copy`)
    setDestination('director')
    setCreating(true)
  }
  const remove = async () => {
    if (!deleting) return
    setBusy(deleting); setError(null)
    try {
      // deleteWorkspace hits DELETE /api/v1/workspaces/<name> which
      // removes the folder and all files inside. The backend also
      // auto-switches to 'default' if the deleted workspace was active;
      // the store handles that transition by routing back to Projects.
      await deleteWorkspace(deleting)
      setDeleting(null)
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not delete project.') }
    finally { setBusy(null) }
  }
  const saveEdit = async () => {
    if (!editing) return
    setBusy(editing); setError(null)
    try {
      // Edit setup mutates the workspace's setup.json without changing
      // its folder; useStore.saveWorkspaceSetup routes through
      // applyWorkspaceSetup too, which only runs when the active
      // workspace matches. Editing a non-active workspace still
      // persists; the change applies on the next switch.
      let nextSetup = setup
      if (pendingCover) {
        const { cover_image } = await uploadWorkspaceCover(editing, pendingCover)
        nextSetup = { ...nextSetup, cover_image }
      } else if (initialCover && !nextSetup.cover_image) {
        // Cover was removed in the dialog — delete the stored file too
        // (best-effort; the reference is already cleared above).
        await deleteWorkspaceCover(editing).catch(() => undefined)
      }
      if (editing === active) {
        await saveSetupAction(nextSetup)
      } else {
        await saveWorkspaceSetup(editing, nextSetup)
      }
      await useStore.getState().loadWorkspaces()
      setEditing(null)
      setPendingCover(null)
      setInitialCover('')
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save project setup.') }
    finally { setBusy(null) }
  }
  const openEdit = (workspace: string) => {
    const card = workspaces.find(w => w.name === workspace)
    setSetup(card?.setup ?? DEFAULT_PROJECT_SETUP)
    setPendingCover(null)
    setInitialCover(card?.setup?.cover_image || '')
    setEditing(workspace)
  }
  const togglePin = async (workspace: Workspace) => {
    const busyKey = `pin-${workspace.name}`
    setBusy(busyKey); setError(null)
    try {
      const next = { ...(workspace.setup || {}), pinned: !workspace.setup?.pinned }
      if (workspace.name === active) await saveSetupAction(next as ProjectSetupDefaults)
      else await saveWorkspaceSetup(workspace.name, next)
      await useStore.getState().loadWorkspaces()
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not update pin.') }
    finally { setBusy(null) }
  }
  const openCreate = () => {
    setError(null)
    setSetup(DEFAULT_PROJECT_SETUP)
    setPendingCover(null)
    setInitialCover('')
    setName('')
    setDestination('director')
    setCreating(true)
  }
  return (
    <div className="section-scroll">
      <div className="section-container">
        <div className="projects-toolbar">
          <label className="shell-search"><Search size={15} /><input aria-label="Search projects" placeholder="Search projects…" value={query} onChange={e => setQuery(e.target.value)} /></label>
          <div className="projects-toolbar-end">
            <span className="text-xs text-text-muted">{userProjects.length} {userProjects.length === 1 ? 'project' : 'projects'}</span>
            <button className="shell-primary-button" onClick={openCreate}><Plus size={16} />New project</button>
          </div>
        </div>
        {error && <p role="alert" className="my-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-400">{error}</p>}
        {!hasProjects && !query && (
          <div className="shell-empty">
            <FolderOpen size={40} strokeWidth={1.5} />
            <h2>Create your first project</h2>
            <p>Projects keep your media, edits and Director productions organized. Pick a name and the technical defaults — Director uses them for every scene and you can change them anytime from the Edit setup menu on each card.</p>
          </div>
        )}
        {hasProjects && visible.length === 0 && (
          <div className="shell-empty"><FolderOpen size={32} /><h2>No matching projects</h2><p>Try a different name.</p></div>
        )}
        <div className="projects-grid">
          {visible.map(workspace => (
            <article key={workspace.name} className={`project-card ${workspace.name === active ? 'is-current' : ''}`}>
              {workspace.setup?.cover_image && (
                <img
                  src={workspaceCoverUrl(workspace.name, workspace.setup.cover_image)}
                  alt={`${workspace.name} cover`}
                  loading="lazy"
                  className="project-cover"
                  onError={e => { e.currentTarget.style.display = 'none' }}
                />
              )}
              <div className="flex items-start justify-between gap-3">
                <div className="project-icon"><FolderOpen size={24} strokeWidth={1.5} /></div>
                <div className="flex items-center gap-1.5">
                  {workspace.setup?.pinned && <Pin size={12} className="text-accent-blue" />}
                  {workspace.name === active && <span className="project-current"><Check size={12} />Active</span>}
                </div>
              </div>
              <h2 title={workspace.name}>{workspace.name}</h2>
              {workspace.setup?.description && (
                <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">{workspace.setup.description}</p>
              )}
              <p className="text-xs text-text-muted">{workspace.file_count ?? 0} media {(workspace.file_count ?? 0) === 1 ? 'file' : 'files'}</p>
              <p className="text-2xs text-text-secondary leading-relaxed" title={ProjectSetupSummary({ setup: workspace.setup })}>
                {ProjectSetupSummary({ setup: workspace.setup })}
              </p>
              {workspace.setup?.tags && workspace.setup.tags.length > 0 && (
                <p className="flex flex-wrap gap-1">
                  {workspace.setup.tags.map(tag => (
                    <span key={tag} className="rounded bg-bg-tertiary px-1.5 py-0.5 text-2xs text-text-muted">{tag}</span>
                  ))}
                </p>
              )}
              <p className="project-card-path" title={workspace.path}>{workspace.path}</p>
              <div className="project-card-actions">
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'director')} className="project-open">
                  {busy === workspace.name ? <Loader2 size={14} className="animate-spin" /> : <Clapperboard size={14} />}Open Director<ArrowRight size={14} />
                </button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'editor')} title={`Edit ${workspace.name}`} aria-label={`Edit ${workspace.name}`} className="shell-icon-button"><Film size={15} /></button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'medias')} title={`Browse ${workspace.name}`} aria-label={`Browse ${workspace.name}`} className="shell-icon-button"><Images size={15} /></button>
                <button disabled={busy !== null} onClick={() => openDuplicate(workspace)} title={`Duplicate ${workspace.name} setup`} aria-label={`Duplicate ${workspace.name} setup`} className="shell-icon-button"><Copy size={14} /></button>
                <button disabled={busy !== null} onClick={() => void togglePin(workspace)} title={workspace.setup?.pinned ? 'Unpin project' : 'Pin project'} aria-label={workspace.setup?.pinned ? 'Unpin project' : 'Pin project'} className="shell-icon-button">{busy === `pin-${workspace.name}` ? <Loader2 size={14} className="animate-spin" /> : workspace.setup?.pinned ? <PinOff size={14} /> : <Pin size={14} />}</button>
                <button disabled={busy !== null} onClick={() => openEdit(workspace.name)} title={`Edit ${workspace.name} setup`} aria-label={`Edit ${workspace.name} setup`} className="shell-icon-button"><Settings size={14} /></button>
                <button disabled={busy !== null} onClick={() => setDeleting(workspace.name)} title={`Delete ${workspace.name}`} aria-label={`Delete ${workspace.name}`} className="shell-icon-button hover:text-red-400"><Trash2 size={14} /></button>
              </div>
            </article>
          ))}
        </div>
      </div>
      {/* New project / Edit setup / Delete dialog. Each uses its own
          contextual content; the modal chrome stays shared so the
          keyboard escape and Tab trap logic isn't repeated. */}
      {(creating || editing || deleting) && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4" onClick={() => { if (!busy) { setCreating(false); setEditing(null); setDeleting(null) } }}>
          <form role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" className="w-full max-w-xl max-h-[88vh] overflow-y-auto rounded-2xl border border-border bg-bg-secondary p-6 shadow-2xl" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); void (deleting ? remove() : creating ? create() : saveEdit()) }} onKeyDown={e => {
              if (e.key === 'Escape' && !busy) { setCreating(false); setEditing(null); setDeleting(null) }
              if (e.key === 'Tab') {
                const controls = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('input:not(:disabled), select:not(:disabled), button:not(:disabled)'))
                const first = controls[0], last = controls[controls.length - 1]
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
                if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
              }
            }}>
            <h2 id="project-dialog-title" className="mb-3 text-lg font-semibold">
              {deleting ? `Delete ${deleting}?` : creating ? 'New project' : `Edit ${editing} setup`}
            </h2>
            {deleting ? (
              <>
                <p className="text-sm text-text-secondary">This permanently deletes the project's workspace folder and <strong>all media files, Editor projects and Director productions</strong> inside it.</p>
                <p className="mt-2 text-xs text-text-muted">Folder: <code className="text-text-secondary">{deleting}</code></p>
              </>
            ) : creating ? (
              <>
                <div>
                  <span className="text-xs text-text-secondary block mb-1.5">Start from a template</span>
                  <div className="flex flex-wrap gap-1.5">
                    {PROJECT_SETUP_TEMPLATES.map(tmpl => {
                      const activeT = setup.aspect_ratio === tmpl.setup.aspect_ratio && setup.resolution === tmpl.setup.resolution
                      return (
                        <button
                          key={tmpl.value}
                          type="button"
                          onClick={() => setSetup({ ...DEFAULT_PROJECT_SETUP, ...tmpl.setup })}
                          disabled={busy !== null}
                          className={`px-2.5 py-1.5 rounded-lg border text-xs transition-all ${
                            activeT
                              ? 'border-accent-blue bg-accent-blue/10 text-text-primary'
                              : 'border-border text-text-muted hover:border-border-light hover:text-text-secondary'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          <span className="font-medium">{tmpl.label}</span>
                          <span className="ml-1 text-2xs opacity-60">{tmpl.desc}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
                <label className="block mt-5 text-xs text-text-secondary">Project name<input autoFocus required value={name} onChange={e => setName(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-bg-primary px-3 py-2.5 text-sm text-text-primary" placeholder="my-new-film" /></label>
                <p className="mt-2 text-xs text-text-muted">A new folder named <code className="text-text-secondary">{name.trim().replace(/\s+/g, '-') || 'project-name'}</code> will be created under <code className="text-text-secondary">outputs/</code>.</p>
                <div className="mt-4 flex items-center gap-1.5">
                  <span className="text-xs text-text-secondary">Open in</span>
                  {([
                    { value: 'director', label: 'Director' },
                    { value: 'editor', label: 'Editor' },
                    { value: 'medias', label: 'Media' },
                  ] as const).map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      disabled={busy !== null}
                      onClick={() => setDestination(opt.value)}
                      className={`px-2.5 py-1 rounded-lg border text-xs transition-all ${
                        destination === opt.value
                          ? 'border-accent-blue bg-accent-blue/10 text-text-primary'
                          : 'border-border text-text-muted hover:border-border-light hover:text-text-secondary'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <div className="mt-5 border-t border-border/40 pt-4">
                  <ProjectSetupForm value={setup} onChange={setSetup} workspaceName={null} onPendingCover={setPendingCover} />
                </div>
              </>
            ) : (
              <>
                <div>
                  <ProjectSetupForm value={setup} onChange={setSetup} compact workspaceName={editing} onPendingCover={setPendingCover} />
                </div>
              </>
            )}
            {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" autoFocus={Boolean(deleting)} disabled={busy !== null} className="shell-secondary-button" onClick={() => { setCreating(false); setEditing(null); setDeleting(null) }}>Cancel</button>
              <button disabled={busy !== null || (!deleting && !creating && !editing) || (creating && !name.trim())} className="shell-primary-button">
                {busy ? 'Working…' : deleting ? 'Delete project' : creating ? 'Create project' : 'Save setup'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

/* Re-exports intentionally not repeated here so ESLint's react-refresh
 * rule doesn't fire. Tests and sister files import `shortModelLabel`
 * directly from `./ProjectSetupForm`. */

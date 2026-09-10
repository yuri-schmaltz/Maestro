import { useState } from 'react'
import { ArrowRight, Check, Clapperboard, Film, FolderOpen, Images, Loader2, Plus, Search, Trash2 } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import type { AppSection } from '../../types'

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
 */
export function ProjectsPage() {
  const workspaces = useStore(s => s.workspaces)
  const active = useStore(s => s.activeWorkspace)
  const createWorkspace = useStore(s => s.createWorkspace)
  const switchWorkspace = useStore(s => s.switchWorkspace)
  const deleteWorkspace = useStore(s => s.deleteWorkspace)
  const navigate = useStore(s => s.setAppSection)
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const userProjects = workspaces.filter(w => w.name !== 'default')
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
      await createWorkspace(value)
      setCreating(false); setName('')
      navigate('director')
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create project.') }
    finally { setBusy(null) }
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
  return (
    <div className="section-scroll">
      <div className="section-container">
        <div className="projects-toolbar">
          <label className="shell-search"><Search size={15} /><input aria-label="Search projects" placeholder="Search projects…" value={query} onChange={e => setQuery(e.target.value)} /></label>
          <div className="projects-toolbar-end">
            <span className="text-xs text-text-muted">{userProjects.length} {userProjects.length === 1 ? 'project' : 'projects'}</span>
            <button className="shell-primary-button" onClick={() => { setError(null); setCreating(true) }}><Plus size={16} />New project</button>
          </div>
        </div>
        {error && <p role="alert" className="my-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-400">{error}</p>}
        {!hasProjects && !query && (
          <div className="shell-empty">
            <FolderOpen size={40} strokeWidth={1.5} />
            <h2>Create your first project</h2>
            <p>Projects keep your media, edits and Director productions organized. Pick a name to get started — you can rename or delete it later.</p>
          </div>
        )}
        {hasProjects && visible.length === 0 && (
          <div className="shell-empty"><FolderOpen size={32} /><h2>No matching projects</h2><p>Try a different name.</p></div>
        )}
        <div className="projects-grid">
          {visible.map(workspace => (
            <article key={workspace.name} className={`project-card ${workspace.name === active ? 'is-current' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="project-icon"><FolderOpen size={24} strokeWidth={1.5} /></div>
                {workspace.name === active && <span className="project-current"><Check size={12} />Active</span>}
              </div>
              <h2 title={workspace.name}>{workspace.name}</h2>
              <p className="text-xs text-text-muted">{workspace.file_count ?? 0} media {(workspace.file_count ?? 0) === 1 ? 'file' : 'files'}</p>
              <p className="project-card-path" title={workspace.path}>{workspace.path}</p>
              <div className="project-card-actions">
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'director')} className="project-open">
                  {busy === workspace.name ? <Loader2 size={14} className="animate-spin" /> : <Clapperboard size={14} />}Open Director<ArrowRight size={14} />
                </button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'editor')} title={`Edit ${workspace.name}`} aria-label={`Edit ${workspace.name}`} className="shell-icon-button"><Film size={15} /></button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'medias')} title={`Browse ${workspace.name}`} aria-label={`Browse ${workspace.name}`} className="shell-icon-button"><Images size={15} /></button>
                <button disabled={busy !== null} onClick={() => setDeleting(workspace.name)} title={`Delete ${workspace.name}`} aria-label={`Delete ${workspace.name}`} className="shell-icon-button hover:text-red-400"><Trash2 size={14} /></button>
              </div>
            </article>
          ))}
        </div>
      </div>
      {(creating || deleting) && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4" onClick={() => { if (!busy) { setCreating(false); setDeleting(null) } }}>
          <form role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" className="w-full max-w-md rounded-2xl border border-border bg-bg-secondary p-6 shadow-2xl" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); void (deleting ? remove() : create()) }} onKeyDown={e => {
              if (e.key === 'Escape' && !busy) { setCreating(false); setDeleting(null) }
              if (e.key === 'Tab') {
                const controls = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('input:not(:disabled), button:not(:disabled)'))
                const first = controls[0], last = controls[controls.length - 1]
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
                if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
              }
            }}>
            <h2 id="project-dialog-title" className="mb-3 text-lg font-semibold">{deleting ? `Delete ${deleting}?` : 'New project'}</h2>
            {deleting ? (
              <>
                <p className="text-sm text-text-secondary">This permanently deletes the project's workspace folder and <strong>all media files, Editor projects and Director productions</strong> inside it.</p>
                <p className="mt-2 text-xs text-text-muted">Folder: <code className="text-text-secondary">{deleting}</code></p>
              </>
            ) : (
              <>
                <label className="block text-xs text-text-secondary">Project name<input autoFocus required value={name} onChange={e => setName(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-bg-primary px-3 py-2.5 text-sm text-text-primary" placeholder="my-new-film" /></label>
                <p className="mt-2 text-xs text-text-muted">A new folder named <code className="text-text-secondary">{name.trim().replace(/\s+/g, '-') || 'project-name'}</code> will be created under <code className="text-text-secondary">outputs/</code>.</p>
              </>
            )}
            {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
            <div className="mt-6 flex justify-end gap-2"><button type="button" autoFocus={Boolean(deleting)} disabled={busy !== null} className="shell-secondary-button" onClick={() => { setCreating(false); setDeleting(null) }}>Cancel</button><button disabled={busy !== null || (!deleting && !name.trim())} className="shell-primary-button">{busy ? 'Working…' : deleting ? 'Delete project' : 'Create project'}</button></div>
          </form>
        </div>
      )}
    </div>
  )
}

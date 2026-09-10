import { useState } from 'react'
import { ArrowRight, Check, Clapperboard, Film, FolderOpen, Images, Loader2, Plus, Search, Trash2 } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import type { AppSection } from '../../types'

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
    try { await createWorkspace(value); setCreating(false); setName('') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create project.') }
    finally { setBusy(null) }
  }
  const remove = async () => {
    if (!deleting) return
    setBusy(deleting); setError(null)
    try { await deleteWorkspace(deleting); setDeleting(null) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not delete project.') }
    finally { setBusy(null) }
  }
  const visible = workspaces.filter(w => w.name.toLowerCase().includes(query.toLowerCase()))
  return (
    <div className="section-scroll">
      <div className="section-container">
        <div className="section-heading">
          <div><p className="section-eyebrow">Your workspace</p><h1>Projects</h1><p>Organize your productions. Pick a project to plan, create and edit.</p></div>
          <button className="shell-primary-button" onClick={() => { setError(null); setCreating(true) }}><Plus size={16} />New project</button>
        </div>
        <div className="projects-toolbar">
          <label className="shell-search"><Search size={15} /><input aria-label="Search projects" placeholder="Search projects…" value={query} onChange={e => setQuery(e.target.value)} /></label>
          <span className="text-xs text-text-muted">{workspaces.length} {workspaces.length === 1 ? 'project' : 'projects'}</span>
        </div>
        {error && <p role="alert" className="my-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-400">{error}</p>}
        <div className="projects-grid">
          {visible.map(workspace => (
            <article key={workspace.name} className={`project-card ${workspace.name === active ? 'is-current' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="project-icon"><FolderOpen size={24} strokeWidth={1.5} /></div>
                {workspace.name === active && <span className="project-current"><Check size={12} />Active</span>}
              </div>
              <h2 title={workspace.name}>{workspace.name}</h2>
              <p className="text-xs text-text-muted">{workspace.file_count ?? 0} media {(workspace.file_count ?? 0) === 1 ? 'file' : 'files'}</p>
              <div className="project-card-actions">
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'director')} className="project-open">
                  {busy === workspace.name ? <Loader2 size={14} className="animate-spin" /> : <Clapperboard size={14} />}Open Director<ArrowRight size={14} />
                </button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'editor')} title={`Edit ${workspace.name}`} aria-label={`Edit ${workspace.name}`} className="shell-icon-button"><Film size={15} /></button>
                <button disabled={busy !== null} onClick={() => void open(workspace.name, 'medias')} title={`Browse ${workspace.name}`} aria-label={`Browse ${workspace.name}`} className="shell-icon-button"><Images size={15} /></button>
                {workspace.name !== 'default' && <button disabled={busy !== null} onClick={() => setDeleting(workspace.name)} title={`Delete ${workspace.name}`} aria-label={`Delete ${workspace.name}`} className="shell-icon-button hover:text-red-400"><Trash2 size={14} /></button>}
              </div>
            </article>
          ))}
        </div>
        {visible.length === 0 && <div className="shell-empty"><FolderOpen size={32} /><h2>{query ? 'No matching projects' : 'Your next production starts here'}</h2><p>{query ? 'Try a different name.' : 'Create a project to keep your media and edits organized.'}</p></div>}
        <button onClick={() => useStore.getState().setDashboardOpen(true)} className="mt-8 flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary"><Clapperboard size={14} />Browse saved Director productions<ArrowRight size={14} /></button>
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
            {deleting ? <p className="text-sm text-text-secondary">This permanently deletes the project and its media files.</p> : <label className="block text-xs text-text-secondary">Project name<input autoFocus required value={name} onChange={e => setName(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-bg-primary px-3 py-2.5 text-sm text-text-primary" placeholder="my-new-film" /></label>}
            {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
            <div className="mt-6 flex justify-end gap-2"><button type="button" autoFocus={Boolean(deleting)} disabled={busy !== null} className="shell-secondary-button" onClick={() => { setCreating(false); setDeleting(null) }}>Cancel</button><button disabled={busy !== null || (!deleting && !name.trim())} className="shell-primary-button">{busy ? 'Working…' : deleting ? 'Delete project' : 'Create project'}</button></div>
          </form>
        </div>
      )}
    </div>
  )
}

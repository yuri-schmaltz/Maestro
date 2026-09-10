import { FolderOpen, Clapperboard, Film, Images, SlidersHorizontal } from 'lucide-react'
import { MaestroBrand } from '../AppModeNavigation'
import { GlobalQueuePopover } from '../GlobalQueuePopover'
import { useStore } from '../../stores/useStore'
import type { AppSection } from '../../types'

const sections = [
  { id: 'projects', label: 'Projects', icon: FolderOpen },
  { id: 'director', label: 'Director', icon: Clapperboard },
  { id: 'editor', label: 'Editor', icon: Film },
  { id: 'medias', label: 'Medias', icon: Images },
  { id: 'configurations', label: 'Configurations', icon: SlidersHorizontal },
] as const

export function ApplicationHeader() {
  const active = useStore(s => s.appSection)
  const navigate = useStore(s => s.setAppSection)
  const select = (id: AppSection) => navigate(id)
  return (
    <header className="application-header" data-testid="application-header">
      <div className="application-brand"><MaestroBrand /></div>
      <nav className="application-navigation" aria-label="Main navigation">
        <div role="tablist" aria-label="Application sections" className="application-tabs">
          {sections.map(({ id, label, icon: Icon }, index) => (
            <button key={id} id={`tab-${id}`} type="button" role="tab"
              aria-selected={active === id} aria-controls={`panel-${id}`} tabIndex={active === id ? 0 : -1}
              className={`application-tab ${active === id ? 'is-active' : ''}`}
              onClick={() => select(id)}
              onKeyDown={event => {
                const next = event.key === 'ArrowRight' ? (index + 1) % sections.length
                  : event.key === 'ArrowLeft' ? (index + sections.length - 1) % sections.length
                    : event.key === 'Home' ? 0 : event.key === 'End' ? sections.length - 1 : -1
                if (next < 0) return
                event.preventDefault()
                select(sections[next].id)
                document.getElementById(`tab-${sections[next].id}`)?.focus()
              }}>
              <Icon size={16} aria-hidden="true" /><span>{label}</span>
            </button>
          ))}
        </div>
      </nav>
      <div className="application-actions"><GlobalQueuePopover /></div>
    </header>
  )
}

import { Cpu, Bell, Cable, BookOpen } from 'lucide-react'
import { useStore } from '../../stores/useStore'
import { SystemSettingsPanel } from './SystemSettingsPanel'
import { ServicesSettingsPanel } from './ServicesSettingsPanel'
import { NotificationSettingsPanel } from './NotificationSettingsPanel'
import { StyleBiblesSettingsPanel } from './StyleBiblesSettingsPanel'

const tabs = [
  { id: 'performance', label: 'Performance', description: 'Hardware, models and storage', icon: Cpu },
  { id: 'integrations', label: 'Integrations', description: 'Language models and services', icon: Cable },
  { id: 'style_bibles', label: 'Style Bibles', description: 'Director character & environment anchors', icon: BookOpen },
  { id: 'notifications', label: 'Notifications', description: 'Alerts, sounds and delivery', icon: Bell },
] as const

export function SettingsDrawer() {
  const active = useStore(s => s.settingsTab)
  const select = useStore(s => s.setSettingsTab)
  return (
    <div className="section-scroll">
      <div className="section-container">
        <div className="configurations-layout">
          <nav className="configurations-navigation" aria-label="Configuration categories">
            {tabs.map(({ id, label, description, icon: Icon }) => <button key={id} onClick={() => select(id)} aria-current={active === id ? 'page' : undefined} className={active === id ? 'is-active' : ''}><Icon size={17} /><span><strong>{label}</strong><small>{description}</small></span></button>)}
          </nav>
          <div className="configurations-content">
            {active === 'performance' && <SystemSettingsPanel />}
            {active === 'integrations' && <ServicesSettingsPanel />}
            {active === 'style_bibles' && <StyleBiblesSettingsPanel />}
            {active === 'notifications' && <NotificationSettingsPanel />}
          </div>
        </div>
      </div>
    </div>
  )
}

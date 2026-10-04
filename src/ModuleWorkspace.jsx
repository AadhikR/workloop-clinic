import { useId, useRef, useState } from 'react'

export default function ModuleWorkspace({ label, views }) {
  const prefix = useId()
  const tabs = useRef([])
  const [active, setActive] = useState(views[0].id)
  const [visited, setVisited] = useState([views[0].id])
  const select = (index) => {
    const id = views[index].id
    setActive(id)
    setVisited((current) => current.includes(id) ? current : [...current, id])
  }
  return <div className="module-workspace">
    <div className="tabs module-view-tabs" role="tablist" aria-label={label}>
      {views.map((view, index) => <button key={view.id} ref={(element) => { tabs.current[index] = element }} type="button" role="tab" id={`${prefix}-${view.id}-tab`} aria-controls={`${prefix}-${view.id}-panel`} aria-selected={active === view.id} tabIndex={active === view.id ? 0 : -1} className={`tab-btn${active === view.id ? ' active' : ''}`} onClick={() => select(index)} onKeyDown={(event) => {
        const next = event.key === 'ArrowRight' ? (index + 1) % views.length : event.key === 'ArrowLeft' ? (index - 1 + views.length) % views.length : event.key === 'Home' ? 0 : event.key === 'End' ? views.length - 1 : null
        if (next === null) return
        event.preventDefault()
        select(next)
        tabs.current[next]?.focus()
      }}>{view.label}</button>)}
    </div>
    {views.filter((view) => visited.includes(view.id)).map((view) => <div key={view.id} id={`${prefix}-${view.id}-panel`} role="tabpanel" aria-labelledby={`${prefix}-${view.id}-tab`} hidden={active !== view.id} className="portal-route module-view-panel">{view.content}</div>)}
  </div>
}

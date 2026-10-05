import { useId } from 'react'
import PortalDialog from './PortalDialog.jsx'

export function StatusPill({ value, children }) {
  const status = String(value ?? 'unknown').toLowerCase().replaceAll(' ', '_')
  return <span className="status-pill" data-status={status}>{children ?? String(value ?? 'Not recorded').replaceAll('_', ' ')}</span>
}

export function SummaryCards({ items }) {
  return <div className="stats-grid module-summary-grid">{items.map((item) => <div className="stat-card" key={item.label}><div className="stat-label">{item.label}</div><div className={`stat-value${item.tone ? ` text-${item.tone}` : ''}`}>{item.value}</div>{item.detail && <div className="stat-sub">{item.detail}</div>}</div>)}</div>
}

export function FilterTabs({ label, options, value, onChange }) {
  return <div className="tabs filter-tabs" role="tablist" aria-label={label}>{options.map((option, index) => <button key={option.value} type="button" role="tab" aria-selected={value === option.value} tabIndex={value === option.value ? 0 : -1} className={`tab-btn${value === option.value ? ' active' : ''}`} onClick={() => onChange(option.value)} onKeyDown={(event) => {
    const next = event.key === 'ArrowRight' ? (index + 1) % options.length : event.key === 'ArrowLeft' ? (index - 1 + options.length) % options.length : event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : null
    if (next === null) return
    event.preventDefault()
    onChange(options[next].value)
    event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]?.focus()
  }}>{option.label}{option.count !== undefined && <span className="tab-count">{option.count}</span>}</button>)}</div>
}

export function FormDialog({ title, open, onClose, children, wide = false }) {
  const id = useId()
  if (!open) return null
  return <PortalDialog labelledBy={id} onClose={onClose}><div className={`portal-form-dialog${wide ? ' wide' : ''}`}><div className="modal-header"><h3 id={id}>{title}</h3><button type="button" className="btn btn-ghost btn-icon" aria-label={`Close ${title.toLowerCase()}`} onClick={onClose}>×</button></div><div className="modal-body">{children}</div></div></PortalDialog>
}

export function PortalTable({ children, className = '', label = 'Records', ...props }) {
  return <div className="table-wrap portal-table-wrap" role="region" aria-label={label} tabIndex={0}><table className={className} {...props}>{children}</table></div>
}

export function ConfirmDialog({ title, open, onClose, onConfirm, busy, children, confirmLabel = 'Confirm' }) {
  return <FormDialog title={title} open={open} onClose={() => { if (!busy) onClose() }}><div className="confirmation-copy">{children}</div><div className="modal-footer"><button type="button" className="btn btn-outline" disabled={busy} onClick={onClose}>Cancel</button><button type="button" className="btn btn-danger" disabled={busy} onClick={onConfirm}>{busy ? 'Working...' : confirmLabel}</button></div></FormDialog>
}

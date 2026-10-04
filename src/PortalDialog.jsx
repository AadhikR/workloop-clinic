import { useEffect, useRef } from 'react'

export default function PortalDialog({ children, labelledBy, onClose, drawer = false }) {
  const dialogRef = useRef(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])
  useEffect(() => {
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const dialog = dialogRef.current
    const focusable = () => [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')].filter((element) => element.checkVisibility())
    focusable()[0]?.focus()
    const handleKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current() }
      if (event.key !== 'Tab') return
      const targets = focusable()
      const first = targets[0]
      const last = targets.at(-1)
      if (!first) { event.preventDefault(); return }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    dialog.addEventListener('keydown', handleKey)
    return () => {
      dialog.removeEventListener('keydown', handleKey)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [])
  return <div className={`modal-overlay${drawer ? ' payroll-drawer-backdrop' : ''}`} role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget) onClose()
  }}><section ref={dialogRef} className={`modal${drawer ? ' payroll-detail-drawer' : ''}`} role="dialog" aria-modal="true" aria-labelledby={labelledBy}>{children}</section></div>
}

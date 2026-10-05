import { useCallback, useEffect, useState } from 'react'
import { ConfirmDialog } from './PortalUi.jsx'
import { readRetainedRecords, setRecordArchived } from './portalProjectionsApi.js'

export function RetainedRemoval({ authentication, branchId, kind, record, onChanged, disabled }) {
  const [attempt, setAttempt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  return <><button type="button" className="btn btn-danger btn-sm" disabled={disabled || busy} onClick={() => { setMessage(''); setAttempt({ key: crypto.randomUUID() }) }}>Remove</button>
    <ConfirmDialog title="Remove record" open={attempt !== null} busy={busy} onClose={() => { if (!busy) setAttempt(null) }} confirmLabel="Remove" onConfirm={async () => {
      setBusy(true); setMessage('')
      try {
        await setRecordArchived(authentication, branchId, kind, record, true, attempt.key)
        setAttempt(null)
        await onChanged().catch(() => setMessage('Record removed. Refresh to see the current register.'))
      } catch { setMessage('The record could not be removed. Its state may have changed. Refresh before retrying.') }
      finally { setBusy(false) }
    }}><p>Remove this record from the active register? The source record, files, and audit remain available for restoration.</p>{message && <p role="alert">{message}</p>}</ConfirmDialog>
    {!attempt && message && <p role="status">{message}</p>}
  </>
}

export default function RetainedRecords({ authentication, branchId, kind, onChanged }) {
  const [state, setState] = useState({ status: 'loading', items: [] })
  const [selection, setSelection] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const load = useCallback(async () => {
    try { setState({ status: 'ready', items: await readRetainedRecords(authentication, branchId, kind) }) }
    catch { setState({ status: 'error', items: [] }) }
  }, [authentication, branchId, kind])
  useEffect(() => { const pending = setTimeout(load, 0); return () => clearTimeout(pending) }, [load])
  return <details className="retained-records"><summary>Removed records</summary>
    {state.status === 'loading' && <p role="status">Loading retained records...</p>}
    {state.status === 'error' && <p role="alert">Retained records are unavailable. <button type="button" onClick={load}>Retry</button></p>}
    {state.status === 'ready' && (state.items.length === 0 ? <p>No removed records.</p> : <div className="table-wrap"><table><thead><tr><th>Record</th><th>Status</th><th>Updated</th><th>Actions</th></tr></thead><tbody>{state.items.map((record) => <tr key={record.id}><td>{record.label}</td><td>{record.status}</td><td>{new Date(record.updatedAt).toLocaleString('en-AE', { timeZone: 'Asia/Dubai' })}</td><td><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setMessage(''); setSelection({ record, key: crypto.randomUUID() }) }}>Restore</button></td></tr>)}</tbody></table></div>)}
    <ConfirmDialog title="Restore record" open={selection !== null} busy={busy} onClose={() => { if (!busy) setSelection(null) }} confirmLabel="Restore" onConfirm={async () => {
      setBusy(true); setMessage('')
      try {
        await setRecordArchived(authentication, branchId, kind, selection.record, false, selection.key)
        setSelection(null); await load()
        await onChanged().catch(() => setMessage('Record restored. Refresh to see the current register.'))
      } catch { setMessage('The record could not be restored. Its state may have changed.') }
      finally { setBusy(false) }
    }}><p>Restore this retained record to the active register?</p>{selection && <p>{selection.record.label}</p>}{message && <p role="alert">{message}</p>}</ConfirmDialog>
    {!selection && message && <p role="status">{message}</p>}
  </details>
}

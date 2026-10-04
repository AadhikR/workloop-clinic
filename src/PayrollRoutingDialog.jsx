import { useEffect, useState } from 'react'
import Dialog from './PortalDialog.jsx'
import { readPayrollRouting, changePayrollRouting } from './payrollRoutingApi.js'

export default function PayrollRoutingDialog({ authentication, branchId, onClose, onSaved }) {
  const [snapshot, setSnapshot] = useState(null)
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(null)
  useEffect(() => {
    let active = true
    readPayrollRouting(authentication, branchId).then((value) => {
      if (active) { setSnapshot(value); setCode(value.branch.defaultBankRoutingCode) }
    }).catch(() => { if (active) setMessage('Routing settings are unavailable.') })
    return () => { active = false }
  }, [authentication, branchId])
  const submit = async (event) => {
    event.preventDefault()
    const request = attempt?.code === code ? attempt : { code, key: crypto.randomUUID() }
    setAttempt(request)
    setBusy(true)
    setMessage('')
    try {
      const result = await changePayrollRouting(authentication, snapshot, code, request.key)
      await onSaved(result)
      onClose()
    } catch (error) {
      setMessage(error.code === 'state_conflict' ? 'The branch or a payroll draft changed. Close and reopen this dialog to review the current drafts.' : error.message || 'Routing code could not be saved. Retry with the same values.')
    } finally { setBusy(false) }
  }
  return <Dialog labelledBy="routing-dialog-title" onClose={() => { if (!busy) onClose() }}>
    <form onSubmit={submit}><div className="modal-header"><h3 id="routing-dialog-title">Change payroll routing code</h3><button type="button" aria-label="Close routing settings" onClick={onClose} disabled={busy}>×</button></div>
      <div className="modal-body">{snapshot ? <><p>Update the default for {snapshot.branch.name} and {snapshot.drafts.length} draft payroll runs in one save. Approved and paid payrolls stay locked.</p><label>Bank routing code<input required pattern="[0-9]{9}" maxLength={9} inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value)} /></label><ul>{snapshot.drafts.map((draft) => <li key={draft.id}>Draft {draft.id.slice(-8)} · {draft.expectedUpdatedAt}</li>)}</ul></> : <p>Loading routing settings...</p>}{message && <p role="alert">{message}</p>}</div>
      <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose} disabled={busy}>Cancel</button><button type="submit" className="btn btn-primary" disabled={!snapshot || busy}>{busy ? 'Saving...' : 'Save routing code'}</button></div></form>
  </Dialog>
}

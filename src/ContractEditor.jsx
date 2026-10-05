import { useCallback, useEffect, useRef, useState } from 'react'
import { readEmployee } from './employeeApi.js'
import { readAllEmployeeContracts, readCurrentEmployeeContract, recordEmployeeContract } from './recordsBenefitsApi.js'
import { PortalTable, StatusPill } from './PortalUi.jsx'
import { downloadEmploymentContractPdf } from './renderedOutputApi.js'
import { openPdf } from './outputDelivery.js'

const labels = { new: 'New contract', renew: 'Renew contract', convert: 'Convert contract', 'not-renewed': 'Not renewing' }

export default function ContractEditor({ authentication, branchId, employeeId }) {
  const [state, setState] = useState({ status: 'loading', items: [], current: null, employee: null })
  const [action, setAction] = useState(null)
  const [form, setForm] = useState({ contractType: 'Limited', startDate: '', endDate: '', notes: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const retry = useRef(null)
  const load = useCallback(async () => {
    try {
      const [items, current, employee] = await Promise.all([
        readAllEmployeeContracts(authentication, branchId, employeeId),
        readCurrentEmployeeContract(authentication, branchId, employeeId),
        readEmployee(authentication, branchId, employeeId),
      ])
      if ((items[0]?.id ?? null) !== current.latestContractEventId) throw new Error('Contract source changed')
      setState({ status: 'ready', items, current, employee })
    } catch { setState({ status: 'error', items: [], current: null, employee: null }) }
  }, [authentication, branchId, employeeId])
  useEffect(() => { const timer = setTimeout(load, 0); return () => clearTimeout(timer) }, [load])
  const start = (kind) => {
    const contractType = kind === 'convert' ? state.current.currentContractType === 'Limited' ? 'Unlimited' : 'Limited' : state.current.currentContractType
    setAction(kind); setError(''); setMessage('')
    setForm({ contractType, startDate: kind === 'renew' ? state.current.currentContractEndDate ?? '' : state.employee.employmentStartDate ?? '', endDate: '', notes: '' })
  }
  const save = async (event) => {
    event.preventDefault()
    const values = action === 'not-renewed' ? { notes: form.notes, expected: state.current }
      : { ...form, startDate: form.startDate || null, endDate: form.contractType === 'Limited' ? form.endDate : null, expected: state.current }
    const fingerprint = JSON.stringify([branchId, employeeId, action, values])
    const attempt = retry.current?.fingerprint === fingerprint ? retry.current : { fingerprint, key: crypto.randomUUID() }
    retry.current = attempt; setBusy(true); setError(''); setMessage('')
    try {
      await recordEmployeeContract(authentication, branchId, employeeId, action, values, attempt.key)
      retry.current = null; setAction(null); setMessage('Contract action recorded.'); await load()
    } catch { setError('The contract action could not be saved. Your entries have been kept. Refresh the contract if its current state changed.') }
    finally { setBusy(false) }
  }
  return <section className="contract-editor" aria-label="Employment contracts"><h3>Employment contracts</h3>
    {state.status === 'loading' && <p role="status">Loading contracts...</p>}
    {state.status === 'error' && <p role="alert">Contracts are unavailable. <button type="button" onClick={load}>Retry contracts</button></p>}
    {message && <p role="status">{message}</p>}
    {state.status === 'ready' && <>
      <div className="card"><dl className="profile-details"><div><dt>Contract type</dt><dd>{state.current.currentContractType}</dd></div><div><dt>Contract end date</dt><dd>{state.current.currentContractEndDate ?? 'Open ended'}</dd></div><div><dt>Employment start</dt><dd>{state.employee.employmentStartDate ?? 'Not recorded'}</dd></div></dl><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { openPdf(await downloadEmploymentContractPdf(authentication, branchId, employeeId)) } catch { setError('The contract letter is unavailable. No document was opened.') } finally { setBusy(false) } }}>Print letter</button></div>
      {!action && error && <p role="alert">{error}</p>}
      {!action && <div className="module-actions">{state.items.length === 0 ? <button type="button" className="btn btn-primary" onClick={() => start('new')}>New contract</button> : <>
        <button type="button" className="btn btn-primary" onClick={() => start('renew')}>Renew contract</button>
        <button type="button" className="btn btn-outline" onClick={() => start('convert')}>Convert to {state.current.currentContractType === 'Limited' ? 'Unlimited' : 'Limited'}</button>
        <button type="button" className="btn btn-danger" onClick={() => start('not-renewed')}>Not renewing</button>
      </>}</div>}
      {action && <form className="restoration-form" onSubmit={save}><h4>{labels[action]}</h4>
        {action === 'not-renewed' && <p>This records non-renewal intent. Employee status and offboarding require their own actions.</p>}
        <fieldset disabled={busy}><div className="employee-form-grid">
          {action !== 'not-renewed' && <>
            <label>Contract type<select disabled={action !== 'new'} value={form.contractType} onChange={(event) => setForm({ ...form, contractType: event.target.value, endDate: '' })}><option>Limited</option><option>Unlimited</option></select></label>
            <label>Start date<input type="date" required={form.contractType === 'Limited'} value={form.startDate} onChange={(event) => setForm({ ...form, startDate: event.target.value })} /></label>
            {form.contractType === 'Limited' && <label>End date<input required type="date" min={form.startDate} value={form.endDate} onChange={(event) => setForm({ ...form, endDate: event.target.value })} /></label>}
          </>}
          <label>Contract notes<textarea maxLength={1000} value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
        </div></fieldset>
        {error && <p role="alert">{error}</p>}
        <div className="module-actions"><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : action === 'not-renewed' ? 'Confirm non-renewal' : 'Confirm contract'}</button><button type="button" className="btn btn-outline" disabled={busy} onClick={() => { setAction(null); setError('') }}>Cancel</button></div>
      </form>}
      <h4>Contract history · {state.items.length}</h4>
      <PortalTable label="Contract history"><thead><tr><th>Action</th><th>Type</th><th>Start date</th><th>End date</th><th>Recorded by</th><th>Notes</th><th>Date</th></tr></thead><tbody>{state.items.map((item) => <tr key={item.id}><td><StatusPill value={item.action} /></td><td>{item.contractType}</td><td>{item.startDate ?? 'Not recorded'}</td><td>{item.endDate ?? 'Open ended'}</td><td>{item.actorName ?? 'Unknown actor'}</td><td>{item.notes || 'None'}</td><td>{item.createdAt.slice(0, 10)}</td></tr>)}{state.items.length === 0 && <tr><td colSpan={7}><div className="empty-state">No contract actions recorded yet.</div></td></tr>}</tbody></PortalTable>
    </>}
  </section>
}

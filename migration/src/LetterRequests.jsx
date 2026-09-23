import { useCallback, useEffect, useState } from 'react'

import {
  decideRequest,
  letterTypeLabels,
  letterTypes,
  readOwnRequests,
  readPrintSource,
  readRequestQueue,
  submitRequest,
  validateSubmission,
} from './letterRequestsApi.js'

const emptyForm = {
  requestKind: 'letter', letterType: letterTypes[0], purpose: '', subject: '', details: '',
}

function Message({ children }) {
  return children ? <p role="status" aria-live="polite">{children}</p> : null
}

function Source({ source }) {
  if (source === null) return null
  return <div className="card"><h4>Completed request source</h4>
    <dl>
      <dt>Employee</dt><dd>{source.employeeName}</dd>
      <dt>Job title</dt><dd>{source.jobTitle || 'Not recorded'}</dd>
      <dt>Department</dt><dd>{source.department || 'Not recorded'}</dd>
      <dt>Branch</dt><dd>{source.branchName}</dd>
      <dt>Request</dt><dd>{source.letterType}</dd>
      <dt>Purpose or details</dt><dd>{source.purpose}</dd>
      {source.basicSalary !== null && <><dt>Basic salary</dt><dd>AED {source.basicSalary}</dd></>}
      {source.allowance !== null && <><dt>Allowance</dt><dd>AED {source.allowance}</dd></>}
    </dl>
    <p>Phase 12 will render printable documents from this source.</p>
  </div>
}

export default function LetterRequests({ account, authentication, branchId }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [source, setSource] = useState(null)

  const load = useCallback(async () => {
    const result = account.role === 'admin'
      ? await readRequestQueue(authentication, branchId)
      : await readOwnRequests(authentication)
    setItems(result)
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(() => {
      load().catch(() => setMessage('Requests are unavailable.'))
    }, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action(); setMessage(success); await load() }
    catch { setMessage('The request action could not be completed.') }
    finally { setBusy(false) }
  }

  const submit = (event) => {
    event.preventDefault()
    const error = validateSubmission(form)
    if (error) { setMessage(error); return }
    const body = form.requestKind === 'letter'
      ? { requestKind: 'letter', letterType: form.letterType, purpose: form.purpose.trim() }
      : { requestKind: 'custom', subject: form.subject.trim(), details: form.details.trim() }
    run(async () => {
      await submitRequest(authentication, body)
      setForm(emptyForm)
    }, 'Request submitted.')
  }

  const decide = (item, command) => {
    const reason = command === 'reject' ? globalThis.prompt('Rejection reason')?.trim() : ''
    if (command === 'reject' && !reason) return
    run(
      () => decideRequest(authentication, branchId, item, command, reason),
      command === 'complete' ? 'Request completed.' : 'Request rejected.',
    )
  }

  const showSource = async (item) => {
    setBusy(true); setMessage('')
    try {
      setSource(await readPrintSource(
        authentication, account.role === 'admin' ? branchId : null, item,
      ))
    } catch { setMessage('The completed request source is unavailable.') }
    finally { setBusy(false) }
  }

  return <section className="records-benefits" aria-labelledby="letter-requests-title">
    <h2 id="letter-requests-title">Letter and custom requests</h2>
    <Message>{message}</Message>
    {account.role !== 'admin' && <form className="expense-form" onSubmit={submit}>
      <label>Request kind<select value={form.requestKind} onChange={(event) => setForm({
        ...form, requestKind: event.target.value,
      })}><option value="letter">HR letter</option><option value="custom">Custom request</option></select></label>
      {form.requestKind === 'letter' ? <>
        <label>Letter type<select value={form.letterType} onChange={(event) => setForm({
          ...form, letterType: event.target.value,
        })}>{letterTypes.map((type) => <option key={type} value={type}>{letterTypeLabels[type]}</option>)}</select></label>
        <label>Purpose or addressee<input maxLength="500" value={form.purpose} onChange={(event) => setForm({
          ...form, purpose: event.target.value,
        })} /></label>
      </> : <>
        <label>Subject<input required minLength="3" maxLength="120" value={form.subject} onChange={(event) => setForm({
          ...form, subject: event.target.value,
        })} /></label>
        <label>Details<textarea required minLength="5" maxLength="2000" value={form.details} onChange={(event) => setForm({
          ...form, details: event.target.value,
        })} /></label>
      </>}
      <button type="submit" disabled={busy}>Submit request</button>
    </form>}
    <table className="expense-table"><thead><tr>
      {account.role === 'admin' && <th>Employee</th>}<th>Request</th><th>Details</th>
      <th>Requested</th><th>Status</th><th>Actions</th>
    </tr></thead><tbody>{items.map((item) => <tr key={item.id}>
      {account.role === 'admin' && <td>{item.employeeName}<small>{item.jobTitle}</small></td>}
      <td>{item.requestKind === 'letter' ? letterTypeLabels[item.letterType] : item.letterType}</td>
      <td>{item.purpose}{item.rejectionReason && <small>{item.rejectionReason}</small>}</td>
      <td>{item.requestedAt.slice(0, 10)}</td><td>{item.status}</td><td>
        {account.role === 'admin' && item.status === 'pending' && <>
          <button type="button" disabled={busy} onClick={() => decide(item, 'complete')}>Complete</button>
          <button type="button" className="danger" disabled={busy} onClick={() => decide(item, 'reject')}>Reject</button>
        </>}
        {item.status === 'completed' && <button type="button" disabled={busy} onClick={() => showSource(item)}>View source</button>}
      </td>
    </tr>)}</tbody></table>
    <Source source={source} />
  </section>
}

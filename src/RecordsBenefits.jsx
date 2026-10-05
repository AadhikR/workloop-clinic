import { useCallback, useEffect, useRef, useState } from 'react'
import EmployeePicker from './EmployeePicker.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'
import InsuranceEditor from './InsuranceEditor.jsx'

import ContractEditor from './ContractEditor.jsx'
import { readCollectionPages } from './collectionPages.js'
import { ConfirmDialog } from './PortalUi.jsx'

import {
  deleteEmployeeDocument,
  downloadEmployeeDocument,
  readEmployeeDocuments,
  readSelfEmployeeDocuments,
  readSelfInsurance,
  rejectEmployeeDocument,
  uploadEmployeeDocument,
  verifyEmployeeDocument,
} from './recordsBenefitsApi.js'

const documentTypes = [
  'Visa', 'Passport', 'Emirates ID', 'Labour Card', 'Work Permit', 'DHA Licence',
  'DOH Licence', 'MOH Licence', 'BLS Certificate', 'ACLS Certificate', 'PALS Certificate',
  'NRP Certificate', 'CME Certificate', 'Medical Fitness Certificate',
  'Educational Certificate', 'Professional License', 'NOC / Reference Letter', 'Other',
]

export function EmployeeDocuments({ account, authentication, branchId, employeeId }) {
  return <ScopedEmployeeDocuments key={`${account.role}:${branchId}:${employeeId ?? account.employeeId}`} account={account} authentication={authentication} branchId={branchId} employeeId={employeeId} />
}

function ScopedEmployeeDocuments({ account, authentication, branchId, employeeId }) {
  const [items, setItems] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({ documentType: 'Passport', documentNumber: '', expiryDate: '', notes: '' })
  const [loadState, setLoadState] = useState('loading')
  const [decision, setDecision] = useState(null)
  const [reason, setReason] = useState('')
  const [actionError, setActionError] = useState('')
  const retry = useRef(null)

  const load = useCallback(async () => {
    setLoadState('loading')
    try {
      const result = await readCollectionPages((cursor) => account.role === 'admin'
        ? readEmployeeDocuments(authentication, branchId, employeeId, { limit: 100, cursor })
        : readSelfEmployeeDocuments(authentication, { limit: 100, cursor }))
      setItems(result)
      setLoadState('ready')
    } catch { setItems([]); setLoadState('error') }
  }, [account.role, authentication, branchId, employeeId])

  useEffect(() => {
    if (account.role === 'admin' && !employeeId) return undefined
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [account.role, employeeId, load])

  const submit = async (event) => {
    event.preventDefault()
    if (file === null) return
    if (file.size > 10 * 1024 * 1024) {
      setMessage('Choose a PDF, JPG, or PNG file no larger than 10 MB.')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      await uploadEmployeeDocument(authentication, account.role === 'admin' ? branchId : null, {
        employeeId: account.role === 'admin' ? employeeId : null,
        ...form,
        expiryDate: form.expiryDate || null,
      }, file)
      setMessage('Employee document uploaded and queued for security scanning.')
      setFile(null)
      await load()
    } catch { setMessage('The employee document could not be uploaded.') }
    finally { setBusy(false) }
  }

  const action = async (kind, document) => {
    if (kind === 'reject' && !reason.trim()) { setActionError('Enter a rejection reason.'); return }
    const fingerprint = JSON.stringify([branchId, kind, document.id, document.updatedAt, kind === 'reject' ? reason.trim() : null])
    const attempt = retry.current?.fingerprint === fingerprint ? retry.current : { fingerprint, key: crypto.randomUUID() }
    retry.current = attempt
    setBusy(true)
    setMessage('')
    setActionError('')
    try {
      if (kind === 'verify') await verifyEmployeeDocument(authentication, branchId, document, attempt.key)
      if (kind === 'reject') {
        await rejectEmployeeDocument(authentication, branchId, document, reason.trim(), attempt.key)
      }
      if (kind === 'delete') {
        await deleteEmployeeDocument(authentication, account.role === 'admin' ? branchId : null, document, attempt.key)
      }
      if (kind === 'download') {
        const signed = await downloadEmployeeDocument(
          authentication, account.role === 'admin' ? branchId : null, document.id,
        )
        globalThis.open(signed.url, '_blank', 'noopener,noreferrer')
      }
      retry.current = null; setDecision(null); setReason('')
      await load()
    } catch { setActionError('The document action could not be completed. Your entries have been kept.') }
    finally { setBusy(false) }
  }

  if (account.role === 'admin' && !employeeId) return <p>Enter an employee ID to manage documents.</p>
  return <section aria-labelledby="employee-documents-title">
    <h3 id="employee-documents-title">{account.role === 'admin' ? 'Employee documents' : 'My Documents'}</h3>
    {loadState === 'loading' && <p role="status">Loading documents...</p>}
    {loadState === 'error' && <p role="alert">Documents are unavailable. <button type="button" onClick={load}>Retry</button></p>}
    {message && <p role="status">{message}</p>}
    {!decision && actionError && <p role="alert">{actionError}</p>}
    <form className="expense-form document-drop-zone" onSubmit={submit} aria-busy={busy}>
      <h4 className="form-section-title">Submit a Document</h4><p>Upload your credentials for HR review. Downloads become available after the security scan passes.</p>
      <label>Document type<select value={form.documentType} onChange={(event) => setForm({ ...form, documentType: event.target.value })}>{documentTypes.map((type) => <option key={type}>{type}</option>)}</select></label>
      <label>Document number<input required maxLength="120" value={form.documentNumber} onChange={(event) => setForm({ ...form, documentNumber: event.target.value })} /></label>
      <label>Expiry date<input type="date" min={new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })} value={form.expiryDate} onChange={(event) => setForm({ ...form, expiryDate: event.target.value })} /></label>
      <label>Notes<textarea maxLength="1000" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      <label>File<input required type="file" accept="application/pdf,image/png,image/jpeg" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span>PDF, JPG, or PNG up to 10 MB{file ? ` · ${file.name}` : ''}</span></label>
      {busy && <progress aria-label="Uploading document" />}
      <button type="submit" disabled={busy || loadState !== 'ready'}>{busy ? 'Uploading...' : 'Upload document'}</button>
    </form>
    {loadState === 'ready' && items.length === 0 && <div className="empty-state">No documents on file yet. Submit your credentials using the form above.</div>}
    <div className="table-wrap"><table className="expense-table"><thead><tr><th>Type</th><th>File</th><th>Status</th><th>Expiry</th><th>Submitted</th><th>Actions</th></tr></thead>
      <tbody>{items.map((document) => <tr key={document.id}>
        <td>{document.documentType}</td><td>{document.fileName}</td>
        <td>{document.status.replaceAll('_', ' ')}{document.rejectionReason && <small>{document.rejectionReason}</small>}</td>
        <td>{document.expiryDate ?? 'None'}{document.expiryDate && document.expiryDate < new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }) && <span className="status-pill" data-status="expired">Expired</span>}</td><td>{document.uploadedAt.slice(0, 10)}</td><td><div className="expense-actions">
          <button type="button" disabled={busy} onClick={() => action('download', document)}>Download</button>
          {account.role === 'admin' && document.status === 'pending_verification' && <>
            <button type="button" disabled={busy} onClick={() => action('verify', document)}>Verify</button>
            <button type="button" className="danger" disabled={busy} onClick={() => { setDecision({ kind: 'reject', document }); setReason(''); setActionError('') }}>Reject</button>
          </>}
          {['pending_verification', 'rejected'].includes(document.status) && <button type="button" className="danger" disabled={busy} onClick={() => { setDecision({ kind: 'delete', document }); setActionError('') }}>Remove</button>}
        </div></td>
      </tr>)}</tbody>
    </table></div>
    <ConfirmDialog title={decision?.kind === 'reject' ? 'Reject employee document' : 'Remove employee document'} open={decision !== null} busy={busy} onClose={() => { if (!busy) setDecision(null) }} confirmLabel={decision?.kind === 'reject' ? 'Reject document' : 'Remove document'} onConfirm={() => action(decision.kind, decision.document)}><p>{decision?.document.fileName}</p>{decision?.kind === 'reject' ? <label>Rejection reason<textarea required maxLength={1000} disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} /></label> : <p>Remove this unverified document? The server retains the cleanup record.</p>}{actionError && <p role="alert">{actionError}</p>}</ConfirmDialog>
  </section>
}

export function SelfInsurance({ authentication }) {
  const [coverage, setCoverage] = useState(undefined)
  const [error, setError] = useState(false)
  const load = useCallback(async () => {
    setError(false)
    try { setCoverage(await readSelfInsurance(authentication)) }
    catch { setError(true) }
  }, [authentication])
  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])
  return <section aria-labelledby="self-insurance-title"><h3 id="self-insurance-title">My insurance</h3>
    {error && <p role="alert">Insurance coverage is unavailable. <button type="button" onClick={load}>Retry</button></p>}
    {!error && coverage === undefined && <p>Loading insurance coverage...</p>}
    {coverage === null && <p>No current insurance coverage is available.</p>}
    {coverage && <dl><div><dt>Insurer</dt><dd>{coverage.insurerName}</dd></div><div><dt>Tier</dt><dd>{coverage.tierName}</dd></div><div><dt>Effective</dt><dd>{coverage.effectiveDate}</dd></div><div><dt>Expiry</dt><dd>{coverage.expiryDate ?? 'None'}</dd></div></dl>}
  </section>
}

export function AdminInsurance(props) { return <InsuranceEditor key={`${props.branchId}:${props.employeeId ?? 'policies'}`} {...props} /> }

export function ContractHistory(props) { return <ContractEditor key={`${props.branchId}:${props.employeeId}`} {...props} /> }

export function EmployeeRecordsEditor({ account, authentication, branchId, employeeId, view }) {
  if (view === 'documents') return <EmployeeDocuments account={account} authentication={authentication} branchId={branchId} employeeId={employeeId} />
  if (view === 'insurance') return <AdminInsurance authentication={authentication} branchId={branchId} employeeId={employeeId} />
  if (view === 'contracts') return <ContractHistory authentication={authentication} branchId={branchId} employeeId={employeeId} />
  return <ModuleWorkspace label="Employee record tabs" views={[
    { id: 'documents', label: 'Documents', content: <EmployeeDocuments account={account} authentication={authentication} branchId={branchId} employeeId={employeeId} /> },
    { id: 'insurance', label: 'Insurance', content: <AdminInsurance authentication={authentication} branchId={branchId} employeeId={employeeId} /> },
    { id: 'contracts', label: 'Contracts', content: <ContractHistory authentication={authentication} branchId={branchId} employeeId={employeeId} /> },
  ]} />
}

export default function RecordsBenefits({ account, authentication, branchId, documentsOnly = false, selectedEmployeeId = null }) {
  const [employeeId, setEmployeeId] = useState('')
  const effectiveEmployeeId = selectedEmployeeId ?? employeeId
  return <section aria-labelledby="records-benefits-title"><h2 id="records-benefits-title">{documentsOnly ? 'Documents' : 'Records and benefits'}</h2>
    {account.role === 'admin' && selectedEmployeeId === null && <EmployeePicker authentication={authentication} branchId={branchId} value={employeeId} onChange={setEmployeeId} />}
    {documentsOnly ? <EmployeeDocuments account={account} authentication={authentication} branchId={branchId} employeeId={effectiveEmployeeId} /> : <ModuleWorkspace label="Record views" views={[
      { id: 'documents', label: 'Documents', content: <EmployeeDocuments account={account} authentication={authentication} branchId={branchId} employeeId={effectiveEmployeeId} /> },
      { id: 'insurance', label: 'Insurance', content: account.role === 'admin' ? <AdminInsurance authentication={authentication} branchId={branchId} employeeId={effectiveEmployeeId} /> : <SelfInsurance authentication={authentication} /> },
      ...(account.role === 'admin' ? [{ id: 'contracts', label: 'Contracts', content: <ContractHistory authentication={authentication} branchId={branchId} employeeId={effectiveEmployeeId} /> }] : []),
    ]} />}
  </section>
}

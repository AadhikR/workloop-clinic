import { useCallback, useEffect, useState } from 'react'

import { readEmployee } from './employeeApi.js'

import {
  createInsuranceDependant,
  deleteInsuranceDependant,
  deleteEmployeeDocument,
  deleteInsurancePolicy,
  downloadEmployeeDocument,
  readEmployeeContracts,
  readEmployeeDocuments,
  readInsurancePolicies,
  readInsuranceDependants,
  readSelfEmployeeDocuments,
  readSelfInsurance,
  recordEmployeeContract,
  rejectEmployeeDocument,
  replaceEmployeeCoverage,
  saveInsurancePolicy,
  updateInsuranceDependant,
  uploadEmployeeDocument,
  verifyEmployeeDocument,
} from './recordsBenefitsApi.js'

const documentTypes = [
  'Visa', 'Passport', 'Emirates ID', 'Labour Card', 'Work Permit', 'DHA Licence',
  'DOH Licence', 'MOH Licence', 'BLS Certificate', 'ACLS Certificate', 'PALS Certificate',
  'NRP Certificate', 'CME Certificate', 'Medical Fitness Certificate',
  'Educational Certificate', 'Professional License', 'NOC / Reference Letter', 'Other',
]

function EmployeeDocuments({ account, authentication, branchId, employeeId }) {
  const [items, setItems] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({ documentType: 'Passport', documentNumber: '', expiryDate: '', notes: '' })

  const load = useCallback(async () => {
    try {
      const result = account.role === 'admin'
        ? await readEmployeeDocuments(authentication, branchId, employeeId)
        : await readSelfEmployeeDocuments(authentication)
      setItems(result.items)
    } catch { setItems([]) }
  }, [account.role, authentication, branchId, employeeId])

  useEffect(() => {
    if (account.role === 'admin' && !employeeId) return undefined
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [account.role, employeeId, load])

  const submit = async (event) => {
    event.preventDefault()
    if (file === null) return
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
    setBusy(true)
    setMessage('')
    try {
      if (kind === 'verify') await verifyEmployeeDocument(authentication, branchId, document)
      if (kind === 'reject') {
        const reason = globalThis.prompt('Reason for rejection')?.trim()
        if (!reason) return
        await rejectEmployeeDocument(authentication, branchId, document, reason)
      }
      if (kind === 'delete') {
        await deleteEmployeeDocument(authentication, account.role === 'admin' ? branchId : null, document)
      }
      if (kind === 'download') {
        const signed = await downloadEmployeeDocument(
          authentication, account.role === 'admin' ? branchId : null, document.id,
        )
        globalThis.open(signed.url, '_blank', 'noopener,noreferrer')
      }
      await load()
    } catch { setMessage('The document action could not be completed.') }
    finally { setBusy(false) }
  }

  if (account.role === 'admin' && !employeeId) return <p>Enter an employee ID to manage documents.</p>
  return <section aria-labelledby="employee-documents-title">
    <h3 id="employee-documents-title">Employee documents</h3>
    {message && <p role="status">{message}</p>}
    <form className="expense-form" onSubmit={submit}>
      <label>Document type<select value={form.documentType} onChange={(event) => setForm({ ...form, documentType: event.target.value })}>{documentTypes.map((type) => <option key={type}>{type}</option>)}</select></label>
      <label>Document number<input required maxLength="120" value={form.documentNumber} onChange={(event) => setForm({ ...form, documentNumber: event.target.value })} /></label>
      <label>Expiry date<input type="date" value={form.expiryDate} onChange={(event) => setForm({ ...form, expiryDate: event.target.value })} /></label>
      <label>Notes<textarea maxLength="1000" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      <label>File<input required type="file" accept="application/pdf,image/png,image/jpeg" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      <button type="submit" disabled={busy}>Upload document</button>
    </form>
    <table className="expense-table"><thead><tr><th>Type</th><th>File</th><th>Status</th><th>Expiry</th><th>Actions</th></tr></thead>
      <tbody>{items.map((document) => <tr key={document.id}>
        <td>{document.documentType}</td><td>{document.fileName}</td>
        <td>{document.status.replaceAll('_', ' ')}{document.rejectionReason && <small>{document.rejectionReason}</small>}</td>
        <td>{document.expiryDate ?? 'None'}</td><td><div className="expense-actions">
          <button type="button" disabled={busy} onClick={() => action('download', document)}>Download</button>
          {account.role === 'admin' && document.status === 'pending_verification' && <>
            <button type="button" disabled={busy} onClick={() => action('verify', document)}>Verify</button>
            <button type="button" className="danger" disabled={busy} onClick={() => action('reject', document)}>Reject</button>
          </>}
          {['pending_verification', 'rejected'].includes(document.status) && <button type="button" className="danger" disabled={busy} onClick={() => action('delete', document)}>Remove</button>}
        </div></td>
      </tr>)}</tbody>
    </table>
  </section>
}

function SelfInsurance({ authentication }) {
  const [coverage, setCoverage] = useState(undefined)
  useEffect(() => {
    readSelfInsurance(authentication).then(setCoverage).catch(() => setCoverage(null))
  }, [authentication])
  return <section aria-labelledby="self-insurance-title"><h3 id="self-insurance-title">My insurance</h3>
    {coverage === undefined && <p>Loading insurance coverage...</p>}
    {coverage === null && <p>No current insurance coverage is available.</p>}
    {coverage && <dl><div><dt>Insurer</dt><dd>{coverage.insurerName}</dd></div><div><dt>Tier</dt><dd>{coverage.tierName}</dd></div><div><dt>Effective</dt><dd>{coverage.effectiveDate}</dd></div><div><dt>Expiry</dt><dd>{coverage.expiryDate ?? 'None'}</dd></div></dl>}
  </section>
}

function AdminInsurance({ authentication, branchId, employeeId }) {
  const empty = { insurerName: '', policyNumber: '', tierName: '', annualPremium: '0.00', renewalDate: '', brokerName: '', brokerContact: '', notes: '' }
  const emptyCoverage = { policyId: '', memberId: '', cardNumber: '', effectiveDate: '', expiryDate: '', tierName: '', expectedUpdatedAt: '' }
  const emptyDependant = { name: '', relationship: '', dateOfBirth: '', cardNumber: '' }
  const [policies, setPolicies] = useState([])
  const [form, setForm] = useState(empty)
  const [editingPolicy, setEditingPolicy] = useState(null)
  const [coverage, setCoverage] = useState(emptyCoverage)
  const [dependants, setDependants] = useState([])
  const [dependantForm, setDependantForm] = useState(emptyDependant)
  const [editingDependant, setEditingDependant] = useState(null)
  const [message, setMessage] = useState('')
  const load = useCallback(() => readInsurancePolicies(authentication, branchId).then((result) => setPolicies(result.items)).catch(() => setPolicies([])), [authentication, branchId])
  const loadDependants = useCallback(() => employeeId
    ? readInsuranceDependants(authentication, branchId, employeeId).then((result) => setDependants(result.items)).catch(() => setDependants([]))
    : setDependants([]), [authentication, branchId, employeeId])
  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])
  useEffect(() => {
    const pending = globalThis.setTimeout(loadDependants, 0)
    return () => globalThis.clearTimeout(pending)
  }, [loadDependants])

  const submit = async (event) => {
    event.preventDefault()
    try {
      await saveInsurancePolicy(
        authentication,
        branchId,
        { ...form, renewalDate: form.renewalDate || null },
        editingPolicy,
      )
      setForm(empty); setEditingPolicy(null); setMessage(editingPolicy ? 'Insurance policy updated.' : 'Insurance policy created.'); await load()
    } catch { setMessage('The insurance policy could not be saved.') }
  }

  const assign = async (event) => {
    event.preventDefault()
    if (!employeeId || !coverage.policyId) return
    try {
      const result = await replaceEmployeeCoverage(authentication, branchId, employeeId, {
        ...coverage,
        expiryDate: coverage.expiryDate || null,
        expectedUpdatedAt: coverage.expectedUpdatedAt || null,
      })
      setCoverage({
        policyId: result.policyId, memberId: result.memberId, cardNumber: result.cardNumber,
        effectiveDate: result.effectiveDate, expiryDate: result.expiryDate ?? '',
        tierName: result.tierName, expectedUpdatedAt: result.updatedAt,
      })
      setMessage('Employee coverage saved. The version field has been refreshed.')
    } catch { setMessage('Coverage could not be saved. Check the current version before replacing it.') }
  }

  const saveDependant = async (event) => {
    event.preventDefault()
    if (!employeeId) return
    const values = { ...dependantForm, dateOfBirth: dependantForm.dateOfBirth || null }
    try {
      if (editingDependant) {
        await updateInsuranceDependant(authentication, branchId, editingDependant, values)
      } else {
        await createInsuranceDependant(authentication, branchId, employeeId, values)
      }
      setDependantForm(emptyDependant); setEditingDependant(null); await loadDependants()
      setMessage('Insurance dependant saved.')
    } catch { setMessage('The insurance dependant could not be saved.') }
  }

  return <section aria-labelledby="insurance-admin-title"><h3 id="insurance-admin-title">Insurance administration</h3>
    {message && <p role="status">{message}</p>}
    <form className="expense-form" onSubmit={submit}>
      <label>Insurer<input required maxLength="180" value={form.insurerName} onChange={(event) => setForm({ ...form, insurerName: event.target.value })} /></label>
      <label>Policy number<input required maxLength="120" value={form.policyNumber} onChange={(event) => setForm({ ...form, policyNumber: event.target.value })} /></label>
      <label>Tier<input required maxLength="120" value={form.tierName} onChange={(event) => setForm({ ...form, tierName: event.target.value })} /></label>
      <label>Annual premium<input required pattern="(?:0|[1-9][0-9]{0,9})\.[0-9]{2}" value={form.annualPremium} onChange={(event) => setForm({ ...form, annualPremium: event.target.value })} /></label>
      <label>Renewal date<input type="date" value={form.renewalDate} onChange={(event) => setForm({ ...form, renewalDate: event.target.value })} /></label>
      <button type="submit">{editingPolicy ? 'Update policy' : 'Create policy'}</button>
      {editingPolicy && <button type="button" className="secondary" onClick={() => { setEditingPolicy(null); setForm(empty) }}>Cancel edit</button>}
    </form>
    <ul>{policies.map((policy) => <li key={policy.id}>{policy.insurerName} · {policy.tierName} · AED {policy.annualPremium} <button type="button" onClick={() => { setEditingPolicy(policy); setForm({ insurerName: policy.insurerName, policyNumber: policy.policyNumber, tierName: policy.tierName, annualPremium: policy.annualPremium, renewalDate: policy.renewalDate ?? '', brokerName: policy.brokerName, brokerContact: policy.brokerContact, notes: policy.notes }) }}>Edit</button> <button type="button" className="danger" onClick={() => deleteInsurancePolicy(authentication, branchId, policy).then(load).catch(() => setMessage('The policy is still in use or changed.'))}>Delete</button></li>)}</ul>
    {employeeId && <>
      <h4>Employee coverage</h4>
      <form className="expense-form" onSubmit={assign}>
        <label>Policy<select required value={coverage.policyId} onChange={(event) => { const policy = policies.find((item) => item.id === event.target.value); setCoverage({ ...coverage, policyId: event.target.value, tierName: policy?.tierName ?? coverage.tierName }) }}><option value="">Choose policy</option>{policies.map((policy) => <option key={policy.id} value={policy.id}>{policy.insurerName} · {policy.tierName}</option>)}</select></label>
        <label>Member ID<input required maxLength="120" value={coverage.memberId} onChange={(event) => setCoverage({ ...coverage, memberId: event.target.value })} /></label>
        <label>Card number<input maxLength="120" value={coverage.cardNumber} onChange={(event) => setCoverage({ ...coverage, cardNumber: event.target.value })} /></label>
        <label>Effective date<input required type="date" value={coverage.effectiveDate} onChange={(event) => setCoverage({ ...coverage, effectiveDate: event.target.value })} /></label>
        <label>Expiry date<input type="date" value={coverage.expiryDate} onChange={(event) => setCoverage({ ...coverage, expiryDate: event.target.value })} /></label>
        <label>Tier<input required maxLength="120" value={coverage.tierName} onChange={(event) => setCoverage({ ...coverage, tierName: event.target.value })} /></label>
        <label>Current coverage version<input placeholder="Leave blank for first assignment" value={coverage.expectedUpdatedAt} onChange={(event) => setCoverage({ ...coverage, expectedUpdatedAt: event.target.value.trim() })} /></label>
        <button type="submit">Save coverage</button>
      </form>
      <h4>Dependants</h4>
      <form className="expense-form" onSubmit={saveDependant}>
        <label>Name<input required maxLength="180" value={dependantForm.name} onChange={(event) => setDependantForm({ ...dependantForm, name: event.target.value })} /></label>
        <label>Relationship<input required maxLength="120" value={dependantForm.relationship} onChange={(event) => setDependantForm({ ...dependantForm, relationship: event.target.value })} /></label>
        <label>Date of birth<input type="date" value={dependantForm.dateOfBirth} onChange={(event) => setDependantForm({ ...dependantForm, dateOfBirth: event.target.value })} /></label>
        <label>Card number<input maxLength="120" value={dependantForm.cardNumber} onChange={(event) => setDependantForm({ ...dependantForm, cardNumber: event.target.value })} /></label>
        <button type="submit">{editingDependant ? 'Update dependant' : 'Add dependant'}</button>
      </form>
      <ul>{dependants.map((dependant) => <li key={dependant.id}>{dependant.name} · {dependant.relationship} <button type="button" onClick={() => { setEditingDependant(dependant); setDependantForm({ name: dependant.name, relationship: dependant.relationship, dateOfBirth: dependant.dateOfBirth ?? '', cardNumber: dependant.cardNumber }) }}>Edit</button> <button type="button" className="danger" onClick={() => deleteInsuranceDependant(authentication, branchId, dependant).then(loadDependants).catch(() => setMessage('The dependant changed and was not removed.'))}>Delete</button></li>)}</ul>
    </>}
  </section>
}

function ContractHistory({ authentication, branchId, employeeId }) {
  const [items, setItems] = useState([])
  const [employee, setEmployee] = useState(null)
  const [message, setMessage] = useState('')
  const load = useCallback(async () => {
    if (!employeeId) { setItems([]); setEmployee(null); return }
    try {
      const [contracts, selectedEmployee] = await Promise.all([
        readEmployeeContracts(authentication, branchId, employeeId),
        readEmployee(authentication, branchId, employeeId),
      ])
      setItems(contracts.items); setEmployee(selectedEmployee)
    } catch { setItems([]); setEmployee(null) }
  }, [authentication, branchId, employeeId])
  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const record = async (action) => {
    const latest = items[0] ?? null
    const currentType = latest?.contractType ?? globalThis.prompt('Current contract type: Limited or Unlimited')
    const currentEnd = latest?.endDate ?? null
    const employeeUpdatedAt = employee?.updatedAt
    if (!employeeUpdatedAt || !currentType) return
    const expected = { employeeUpdatedAt, currentContractType: currentType, currentContractEndDate: currentEnd, latestContractEventId: latest?.id ?? null }
    let values = { notes: '', expected }
    if (action !== 'not-renewed') {
      const contractType = action === 'convert' ? (currentType === 'Limited' ? 'Unlimited' : 'Limited') : currentType
      const startDate = globalThis.prompt('Contract start date (YYYY-MM-DD)')?.trim()
      const endDate = contractType === 'Limited' ? globalThis.prompt('Contract end date (YYYY-MM-DD)')?.trim() : null
      if (!startDate || contractType === 'Limited' && !endDate) return
      values = { contractType, startDate, endDate, notes: '', expected }
    }
    try { await recordEmployeeContract(authentication, branchId, employeeId, action, values); await load() }
    catch { setMessage('The contract state changed or the command was invalid.') }
  }

  if (!employeeId) return <p>Enter an employee ID to manage contracts.</p>
  return <section aria-labelledby="contracts-title"><h3 id="contracts-title">Employment contracts</h3>
    {message && <p role="status">{message}</p>}
    <div className="actions"><button type="button" onClick={() => record('new')}>New</button><button type="button" onClick={() => record('renew')}>Renew</button><button type="button" onClick={() => record('convert')}>Convert</button><button type="button" onClick={() => record('not-renewed')}>Not renewed</button></div>
    <ul>{items.map((contract) => <li key={contract.id}>{contract.action.replaceAll('_', ' ')} · {contract.contractType} · {contract.startDate ?? 'No start'} to {contract.endDate ?? 'Open ended'}</li>)}</ul>
  </section>
}

export default function RecordsBenefits({ account, authentication, branchId }) {
  const [employeeId, setEmployeeId] = useState('')
  return <section aria-labelledby="records-benefits-title"><h2 id="records-benefits-title">Records and benefits</h2>
    {account.role === 'admin' && <label>Employee ID<input value={employeeId} onChange={(event) => setEmployeeId(event.target.value.trim())} placeholder="UUID" /></label>}
    <EmployeeDocuments account={account} authentication={authentication} branchId={branchId} employeeId={employeeId} />
    {account.role === 'admin'
      ? <><AdminInsurance authentication={authentication} branchId={branchId} employeeId={employeeId} /><ContractHistory authentication={authentication} branchId={branchId} employeeId={employeeId} /></>
      : <SelfInsurance authentication={authentication} />}
  </section>
}

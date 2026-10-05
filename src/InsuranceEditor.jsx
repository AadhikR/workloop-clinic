import { useCallback, useEffect, useRef, useState } from 'react'
import { ConfirmDialog, PortalTable, StatusPill } from './PortalUi.jsx'
import {
  createInsuranceDependant, deleteInsuranceDependant, deleteInsurancePolicy,
  readAllInsurancePolicies, readInsuranceDependants, readEmployeeCoverage,
  replaceEmployeeCoverage, saveInsurancePolicy, updateInsuranceDependant,
} from './recordsBenefitsApi.js'
import { readCollectionPages } from './collectionPages.js'

const emptyPolicy = { insurerName: '', policyNumber: '', tierName: '', annualPremium: '0.00', renewalDate: '', brokerName: '', brokerContact: '', notes: '' }
const emptyCoverage = { policyId: '', memberId: '', cardNumber: '', effectiveDate: '', expiryDate: '', tierName: '', expectedUpdatedAt: null }
const emptyDependant = { name: '', relationship: '', dateOfBirth: '', cardNumber: '' }
function renewalStatus(date) {
  if (!date) return 'none'
  const days = Math.ceil((Date.parse(`${date}T00:00:00+04:00`) - Date.now()) / 86400000)
  return days < 0 ? 'expired' : days <= 60 ? 'expiring' : 'valid'
}

export default function InsuranceEditor({ authentication, branchId, employeeId, policiesOnly = false }) {
  const scope = `${branchId}:${employeeId ?? 'policies'}`
  const [state, setState] = useState({ status: 'loading', policies: [], dependants: [] })
  const [form, setForm] = useState(emptyPolicy)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [coverage, setCoverage] = useState(emptyCoverage)
  const [dependantForm, setDependantForm] = useState(emptyDependant)
  const [editingDependant, setEditingDependant] = useState(null)
  const [removal, setRemoval] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const retry = useRef(null)
  const load = useCallback(async () => {
    try {
      const [policies, current, dependants] = await Promise.all([
        readAllInsurancePolicies(authentication, branchId),
        employeeId ? readEmployeeCoverage(authentication, branchId, employeeId) : null,
        employeeId ? readCollectionPages((cursor) => readInsuranceDependants(authentication, branchId, employeeId, { limit: 100, cursor })) : [],
      ])
      setState({ scope, status: 'ready', policies, dependants })
      setCoverage(current ? { policyId: current.policyId, memberId: current.memberId, cardNumber: current.cardNumber, effectiveDate: current.effectiveDate, expiryDate: current.expiryDate ?? '', tierName: current.tierName, expectedUpdatedAt: current.updatedAt } : emptyCoverage)
    } catch { setState({ scope, status: 'error', policies: [], dependants: [] }) }
  }, [authentication, branchId, employeeId, scope])
  useEffect(() => { const timer = setTimeout(load, 0); return () => clearTimeout(timer) }, [load])
  const view = state.scope === scope ? state : { status: 'loading', policies: [], dependants: [] }
  async function mutate(kind, values, operation, success, onSaved) {
    const fingerprint = JSON.stringify([scope, kind, values])
    const attempt = retry.current?.fingerprint === fingerprint ? retry.current : { fingerprint, key: crypto.randomUUID() }
    retry.current = attempt; setBusy(true); setError(''); setMessage('')
    try {
      await operation(attempt.key)
      retry.current = null; onSaved?.(); setMessage(success)
      await load()
    } catch { setError('The insurance change could not be saved. Your entries have been kept. Refresh if the record has changed.') }
    finally { setBusy(false) }
  }
  return <section className="insurance-editor" aria-label={policiesOnly ? 'Medical insurance policies' : 'Insurance administration'}>
    <div className="card-header"><h3>{policiesOnly ? 'Medical insurance policies' : 'Insurance administration'}</h3><button type="button" className="btn btn-primary btn-sm" disabled={busy || view.status !== 'ready'} onClick={() => { setEditing(null); setForm(emptyPolicy); setShowForm(true); setError('') }}>Add Policy</button></div>
    {view.status === 'loading' && <p role="status">Loading insurance records...</p>}
    {view.status === 'error' && <p role="alert">Insurance records are unavailable. <button type="button" onClick={load}>Retry insurance</button></p>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    {showForm && <form className="restoration-form insurance-policy-form" onSubmit={(event) => { event.preventDefault(); const values = { ...form, renewalDate: form.renewalDate || null }; return mutate('policy', [editing?.id, editing?.updatedAt, values], (key) => saveInsurancePolicy(authentication, branchId, values, editing, key), editing ? 'Insurance policy updated.' : 'Insurance policy created.', () => { setShowForm(false); setEditing(null); setForm(emptyPolicy) }) }}>
      <h4>{editing ? `Edit ${editing.insurerName}` : 'New insurance policy'}</h4>
      <fieldset disabled={busy}><div className="employee-form-grid">
        <label>Insurer<input required maxLength={180} value={form.insurerName} onChange={(event) => setForm({ ...form, insurerName: event.target.value })} /></label>
        <label>Policy number<input required maxLength={120} value={form.policyNumber} onChange={(event) => setForm({ ...form, policyNumber: event.target.value })} /></label>
        <label>Tier<input required maxLength={120} value={form.tierName} onChange={(event) => setForm({ ...form, tierName: event.target.value })} /></label>
        <label>Annual premium<input required pattern="(?:0|[1-9][0-9]{0,9})\.[0-9]{2}" value={form.annualPremium} onChange={(event) => setForm({ ...form, annualPremium: event.target.value })} /></label>
        <label>Renewal date<input type="date" value={form.renewalDate} onChange={(event) => setForm({ ...form, renewalDate: event.target.value })} /></label>
        <label>Broker name<input maxLength={180} value={form.brokerName} onChange={(event) => setForm({ ...form, brokerName: event.target.value })} /></label>
        <label>Broker contact<input maxLength={500} value={form.brokerContact} onChange={(event) => setForm({ ...form, brokerContact: event.target.value })} /></label>
        <label>Policy notes<textarea maxLength={1000} value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      </div></fieldset>
      <div className="module-actions"><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : editing ? 'Update policy' : 'Create policy'}</button><button type="button" className="btn btn-outline" disabled={busy} onClick={() => { setShowForm(false); setEditing(null); setError('') }}>Cancel edit</button></div>
    </form>}
    {view.status === 'ready' && <PortalTable label="Insurance policies"><thead><tr><th>Insurer</th><th>Policy number</th><th>Tier</th><th>Annual premium</th><th>Renewal date</th><th>Broker</th><th>Actions</th></tr></thead><tbody>{view.policies.map((policy) => <tr key={policy.id}><td>{policy.insurerName}{policy.notes && <small>{policy.notes}</small>}</td><td>{policy.policyNumber}</td><td>{policy.tierName}</td><td>AED {policy.annualPremium}</td><td>{policy.renewalDate ?? 'No renewal date'}<StatusPill value={renewalStatus(policy.renewalDate)} /></td><td>{policy.brokerName || 'Not recorded'}<small>{policy.brokerContact}</small></td><td><div className="module-actions"><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setEditing(policy); setForm({ ...emptyPolicy, ...Object.fromEntries(Object.keys(emptyPolicy).map((key) => [key, policy[key] ?? ''])) }); setShowForm(true); setError('') }}>Edit policy</button><button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => { setRemoval({ kind: 'policy', record: policy }); setError('') }}>Delete policy</button></div></td></tr>)}{view.policies.length === 0 && <tr><td colSpan={7}><div className="empty-state">No insurance policies configured. Add a policy to assign coverage.</div></td></tr>}</tbody></PortalTable>}
    {!policiesOnly && employeeId && view.status === 'ready' && <>
      <h4>Employee coverage</h4>
      {!coverage.expectedUpdatedAt && <p>No employee coverage assigned.</p>}
      <form className="restoration-form" onSubmit={(event) => { event.preventDefault(); const values = { ...coverage, expiryDate: coverage.expiryDate || null }; return mutate('coverage', values, (key) => replaceEmployeeCoverage(authentication, branchId, employeeId, values, key), 'Employee coverage saved.') }}><fieldset disabled={busy}><div className="employee-form-grid">
        <label>Policy<select required value={coverage.policyId} onChange={(event) => { const policy = view.policies.find((item) => item.id === event.target.value); setCoverage({ ...coverage, policyId: event.target.value, tierName: policy?.tierName ?? coverage.tierName }) }}><option value="">Choose policy</option>{view.policies.map((policy) => <option key={policy.id} value={policy.id}>{policy.insurerName} · {policy.tierName}</option>)}</select></label>
        <label>Member ID<input required maxLength={120} value={coverage.memberId} onChange={(event) => setCoverage({ ...coverage, memberId: event.target.value })} /></label>
        <label>Card number<input maxLength={120} value={coverage.cardNumber} onChange={(event) => setCoverage({ ...coverage, cardNumber: event.target.value })} /></label>
        <label>Effective date<input required type="date" value={coverage.effectiveDate} onChange={(event) => setCoverage({ ...coverage, effectiveDate: event.target.value })} /></label>
        <label>Coverage expiry date<input type="date" value={coverage.expiryDate} onChange={(event) => setCoverage({ ...coverage, expiryDate: event.target.value })} /></label>
        <label>Coverage tier<input required maxLength={120} value={coverage.tierName} onChange={(event) => setCoverage({ ...coverage, tierName: event.target.value })} /></label>
      </div></fieldset><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : 'Save coverage'}</button></form>
      <h4>Dependants</h4>
      <form className="restoration-form" onSubmit={(event) => { event.preventDefault(); const values = { ...dependantForm, dateOfBirth: dependantForm.dateOfBirth || null }; return mutate('dependant', [editingDependant?.id, editingDependant?.updatedAt, values], (key) => editingDependant ? updateInsuranceDependant(authentication, branchId, editingDependant, values, key) : createInsuranceDependant(authentication, branchId, employeeId, values, key), 'Insurance dependant saved.', () => { setDependantForm(emptyDependant); setEditingDependant(null) }) }}><fieldset disabled={busy}><div className="employee-form-grid">
        <label>Dependant name<input required maxLength={180} value={dependantForm.name} onChange={(event) => setDependantForm({ ...dependantForm, name: event.target.value })} /></label>
        <label>Relationship<input required maxLength={120} value={dependantForm.relationship} onChange={(event) => setDependantForm({ ...dependantForm, relationship: event.target.value })} /></label>
        <label>Date of birth<input type="date" value={dependantForm.dateOfBirth} onChange={(event) => setDependantForm({ ...dependantForm, dateOfBirth: event.target.value })} /></label>
        <label>Dependant card number<input maxLength={120} value={dependantForm.cardNumber} onChange={(event) => setDependantForm({ ...dependantForm, cardNumber: event.target.value })} /></label>
      </div></fieldset><div className="module-actions"><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : editingDependant ? 'Update dependant' : 'Add dependant'}</button>{editingDependant && <button type="button" className="btn btn-outline" disabled={busy} onClick={() => { setEditingDependant(null); setDependantForm(emptyDependant) }}>Cancel edit</button>}</div></form>
      <PortalTable label="Insurance dependants"><thead><tr><th>Name</th><th>Relationship</th><th>Date of birth</th><th>Card number</th><th>Actions</th></tr></thead><tbody>{view.dependants.map((dependant) => <tr key={dependant.id}><td>{dependant.name}</td><td>{dependant.relationship}</td><td>{dependant.dateOfBirth ?? 'Not recorded'}</td><td>{dependant.cardNumber || 'Not recorded'}</td><td><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setEditingDependant(dependant); setDependantForm(Object.fromEntries(Object.keys(emptyDependant).map((key) => [key, dependant[key] ?? '']))) }}>Edit dependant</button><button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => { setRemoval({ kind: 'dependant', record: dependant }); setError('') }}>Delete dependant</button></td></tr>)}{view.dependants.length === 0 && <tr><td colSpan={5}>No dependants on this policy.</td></tr>}</tbody></PortalTable>
    </>}
    <ConfirmDialog title={removal?.kind === 'policy' ? 'Delete insurance policy' : 'Delete insurance dependant'} open={removal !== null} busy={busy} onClose={() => { if (!busy) setRemoval(null) }} confirmLabel="Delete" onConfirm={() => mutate('delete', [removal.kind, removal.record.id, removal.record.updatedAt], (key) => removal.kind === 'policy' ? deleteInsurancePolicy(authentication, branchId, removal.record, key) : deleteInsuranceDependant(authentication, branchId, removal.record, key), 'Insurance record deleted.', () => setRemoval(null))}><p>Delete {removal?.record.insurerName ?? removal?.record.name}? A policy assigned to employees cannot be deleted.</p>{error && <p role="alert">{error}</p>}</ConfirmDialog>
  </section>
}

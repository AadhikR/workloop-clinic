import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import EmployeePicker from './EmployeePicker.jsx'
import { readAllEmployees } from './employeeApi.js'
import { FilterTabs, FormDialog, PortalTable, StatusPill, SummaryCards } from './PortalUi.jsx'

import {
  assignAsset,
  changeAssetStatus,
  completeTraining,
  createCertification,
  createTraining,
  decideCertification,
  deleteAsset,
  deleteCertification,
  deleteCmeRequirement,
  deleteTraining,
  downloadEvidence,
  readAssets,
  readAssetHistory,
  readCertifications,
  readBranchCme,
  readSelfAssets,
  readSelfCme,
  readTraining,
  returnAsset,
  saveAsset,
  saveCmeRequirement,
  updateTraining,
  updateCertification,
  uploadEvidence,
} from './developmentAssetsApi.js'

const StaffDevelopment = lazy(() => import('./StaffDevelopment.jsx'))

const emptyAsset = {
  name: '', assetCode: '', category: 'other', brand: '', model: '', serialNumber: '',
  purchaseDate: null, purchaseCost: null, notes: '',
}
const emptyTraining = {
  trainingTitle: '', trainingType: 'external', provider: '', startDate: null, endDate: null,
  durationHours: null, notes: '', cost: '0.00', isCme: false,
}
const emptyCertification = {
  certificationName: '', issuingBody: '', certificateNo: '', issuedDate: null,
  expiryDate: null, notes: '',
}

function Status({ message }) {
  return message ? <p role="status">{message}</p> : null
}

function AssetWorkspace({ account, authentication, branchId }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState(emptyAsset)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadState, setLoadState] = useState('loading')
  const [history, setHistory] = useState([])
  const [tab, setTab] = useState('assets')
  const [filter, setFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [action, setAction] = useState(null)
  const [custody, setCustody] = useState({ employeeId: '', date: new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }), condition: 'good', notes: '' })

  const load = useCallback(async () => {
    setLoadState('loading')
    try {
      if (account.role === 'admin') {
        const records = []
        const seen = new Set()
        let cursor = null
        do {
          const result = await readAssets(authentication, branchId, { limit: 100, cursor })
          records.push(...result.items)
          cursor = result.page.hasMore ? result.page.nextCursor : null
          if (result.page.hasMore && (!cursor || seen.has(cursor))) throw new Error('Asset pagination is unavailable')
          seen.add(cursor)
        } while (cursor)
        setItems(records.sort((left, right) => left.assetCode.localeCompare(right.assetCode) || left.name.localeCompare(right.name)))
      } else setItems((await readSelfAssets(authentication)).items)
      if (account.role === 'admin') {
        const records = []
        const seen = new Set()
        let cursor = null
        do {
          const page = await readAssetHistory(authentication, branchId, { limit: 100, cursor })
          records.push(...page.items)
          cursor = page.page.hasMore ? page.page.nextCursor : null
          if (page.page.hasMore && (!cursor || seen.has(cursor))) throw new Error('Asset history pagination is unavailable')
          seen.add(cursor)
        } while (cursor)
        setHistory(records)
      }
      setLoadState('ready')
    } catch { setLoadState('error'); throw new Error('Asset service unavailable') }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(() => load().catch(() => {}), 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const run = async (action, success) => {
    setBusy(true)
    setMessage('')
    try { await action() }
    catch { setMessage('The asset action could not be completed.'); setBusy(false); return false }
    try { await load(); setMessage(success); return true }
    catch { setMessage(`${success} Reload to see the latest records.`); return true }
    finally { setBusy(false) }
  }

  const submit = (event) => {
    event.preventDefault()
    run(async () => {
      await saveAsset(authentication, branchId, form, editing)
      setForm(emptyAsset)
      setEditing(null)
      setShowForm(false)
    }, editing === null ? 'Asset saved.' : 'Asset updated.')
  }

  if (account.role !== 'admin') {
    return <section aria-labelledby="my-assets-title">
      <h3 id="my-assets-title">My assets</h3>
      <p>Current custody and retained assignment history.</p>
      {loadState === 'error' && <div className="alert alert-danger">Asset history is unavailable. <button type="button" onClick={() => load().catch(() => {})}>Retry</button></div>}
      <PortalTable label="My asset assignments" className="expense-table"><thead><tr><th>Asset</th><th>Assigned</th><th>Returned</th><th>Condition</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.id}><td>{item.assetName}<small>{item.assetCode}</small></td>
          <td>{item.assignedDate}</td><td>{item.returnDate ?? 'Current'}</td>
          <td>{item.conditionAtReturn ?? item.conditionAtHandover}</td></tr>)}</tbody>
      </PortalTable>
    </section>
  }

  const statuses = [['all', 'All'], ['available', 'Available'], ['assigned', 'Assigned'], ['under_repair', 'Under Repair'], ['retired', 'Retired'], ['lost', 'Lost']]
  const filtered = items.filter((item) => filter === 'all' || item.status === filter)
  const openCustody = (asset, kind) => {
    setCustody({ employeeId: '', date: new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }), condition: 'good', notes: '' })
    setAction({ asset, kind })
  }
  return <section className="restored-module asset-workspace" aria-labelledby="asset-inventory-title">
    <header className="restored-module-header"><div><h3 id="asset-inventory-title">Assets</h3><p>Manage the asset register and employee assignments.</p></div><div className="module-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => load().catch(() => {})}>Reload</button><button type="button" className="btn btn-primary" disabled={busy} onClick={() => { setEditing(null); setForm(emptyAsset); setShowForm(true) }}>Add Asset</button></div></header>
    <Status message={message} />
    <SummaryCards items={[{ label: 'Total', value: loadState === 'ready' ? items.length : 'Not available' }, ...[['Available', 'available'], ['Assigned', 'assigned'], ['Under Repair', 'under_repair']].map(([label, status]) => ({ label, value: loadState === 'ready' ? items.filter((item) => item.status === status).length : 'Not available' }))]} />
    <FilterTabs label="Asset views" options={[{ value: 'assets', label: 'Asset Register' }, { value: 'history', label: 'Assignment History' }]} value={tab} onChange={setTab} />
    {loadState === 'loading' && <p role="status">Loading asset records...</p>}
    {loadState === 'error' && <div className="alert alert-danger" role="alert">Asset records are unavailable. <button type="button" className="btn btn-outline" onClick={() => load().catch(() => {})}>Retry</button></div>}
    <FormDialog title={editing ? 'Edit asset' : 'Add asset'} open={showForm} onClose={() => { if (!busy) setShowForm(false) }}>
    <form className="expense-form restoration-form" onSubmit={submit}>
      <label>Name<input required maxLength="180" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
      <label>Asset code<input maxLength="120" value={form.assetCode} onChange={(event) => setForm({ ...form, assetCode: event.target.value.toUpperCase() })} /></label>
      <label>Category<input maxLength="120" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
      <label>Brand<input maxLength="120" value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></label>
      <label>Model<input maxLength="120" value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} /></label>
      <label>Serial number<input maxLength="180" value={form.serialNumber} onChange={(event) => setForm({ ...form, serialNumber: event.target.value })} /></label>
      <label>Purchase date<input type="date" value={form.purchaseDate ?? ''} onChange={(event) => setForm({ ...form, purchaseDate: event.target.value || null })} /></label>
      <label>Purchase cost<input inputMode="decimal" pattern="[0-9]+\.[0-9]{2}" value={form.purchaseCost ?? ''} onChange={(event) => setForm({ ...form, purchaseCost: event.target.value || null })} /></label>
      <label>Notes<textarea maxLength="1000" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      <button type="submit" disabled={busy}>{editing === null ? 'Add asset' : 'Update asset'}</button>
      {editing !== null && <button type="button" disabled={busy} onClick={() => { setEditing(null); setForm(emptyAsset) }}>Cancel edit</button>}
    </form>
    </FormDialog>
    {tab === 'assets' && <><FilterTabs label="Asset status" options={statuses.map(([value, label]) => ({ value, label, count: value === 'all' ? items.length : items.filter((item) => item.status === value).length }))} value={filter} onChange={setFilter} />
    <PortalTable label="Asset register" className="expense-table"><thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Brand / Model</th><th>Status</th><th>Assigned To</th><th>Since</th><th>Value</th><th>Actions</th></tr></thead>
      <tbody>{filtered.map((asset) => {
        const current = history.find((item) => item.assetId === asset.id && item.returnDate === null)
        return <tr key={asset.id}><td>{asset.assetCode || 'Not recorded'}</td><td><strong>{asset.name}</strong><small>{asset.serialNumber}</small></td><td>{asset.category}</td><td>{[asset.brand, asset.model].filter(Boolean).join(' · ') || 'Not recorded'}</td>
        <td><StatusPill value={asset.status} /></td><td>{current?.employeeName ?? 'Unassigned'}</td><td>{current?.assignedDate ?? 'Not assigned'}</td><td>{asset.purchaseCost === null ? 'Not recorded' : `AED ${Number(asset.purchaseCost).toLocaleString('en-AE', { minimumFractionDigits: 2 })}`}</td>
        <td><div className="expense-actions">
          <button type="button" disabled={busy} onClick={() => {
            setEditing(asset)
            setShowForm(true)
            setForm({
              name: asset.name, assetCode: asset.assetCode, category: asset.category,
              brand: asset.brand, model: asset.model, serialNumber: asset.serialNumber,
              purchaseDate: asset.purchaseDate, purchaseCost: asset.purchaseCost, notes: asset.notes,
            })
          }}>Edit</button>
          {asset.status === 'available' && <button type="button" disabled={busy} onClick={() => openCustody(asset, 'assign')}>Assign</button>}
          {asset.status === 'assigned' && <button type="button" disabled={busy} onClick={() => openCustody(asset, 'return')}>Return</button>}
          {asset.status === 'available' && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'under_repair'), 'Asset status changed.')}>Repair</button>}
          {asset.status === 'under_repair' && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'available'), 'Asset returned to service.')}>Return to service</button>}
          {['available', 'under_repair'].includes(asset.status) && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'retired'), 'Asset retired.')}>Retire</button>}
          {['available', 'under_repair'].includes(asset.status) && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'lost'), 'Asset marked lost.')}>Mark lost</button>}
          {asset.status !== 'assigned' && <button type="button" className="danger" disabled={busy} onClick={() => setAction({ asset, kind: 'remove' })}>Remove</button>}
        </div></td></tr>})}{loadState === 'ready' && filtered.length === 0 && <tr><td colSpan={9}><div className="empty-state"><h4>No assets found</h4><p>Add an asset or choose another status.</p></div></td></tr>}</tbody>
    </PortalTable></>}
    {tab === 'history' && <PortalTable label="Asset assignment history"><thead><tr><th>Asset</th><th>Employee</th><th>Assigned</th><th>Returned</th><th>Condition Out</th><th>Condition In</th><th>Notes</th></tr></thead><tbody>{history.map((item) => <tr key={item.id}><td><strong>{item.assetName}</strong><small>{item.assetCode}</small></td><td>{item.employeeName}</td><td>{item.assignedDate}</td><td>{item.returnDate ?? <StatusPill value="active" />}</td><td>{item.conditionAtHandover}</td><td>{item.conditionAtReturn ?? 'Not returned'}</td><td>{item.notes || 'None'}</td></tr>)}{loadState === 'ready' && history.length === 0 && <tr><td colSpan={7}><div className="empty-state">No assignment records yet.</div></td></tr>}</tbody></PortalTable>}
    <FormDialog title={action?.kind === 'assign' ? 'Assign asset' : action?.kind === 'return' ? 'Return asset' : 'Remove asset'} open={Boolean(action)} onClose={() => { if (!busy) setAction(null) }}>
      {action?.kind === 'remove' ? <><p>Remove {action.asset.name}? The server will block removal if retained assignments depend on it.</p><div className="modal-footer"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => setAction(null)}>Cancel</button><button type="button" className="btn btn-danger" disabled={busy} onClick={async () => { if (await run(() => deleteAsset(authentication, branchId, action.asset), 'Asset removed.')) setAction(null) }}>Remove asset</button></div></> : action && <form className="restoration-form" onSubmit={async (event) => {
        event.preventDefault()
        const saved = await run(() => action.kind === 'assign' ? assignAsset(authentication, branchId, action.asset, { employeeId: custody.employeeId, assignedDate: custody.date, conditionAtHandover: custody.condition, notes: custody.notes }) : returnAsset(authentication, branchId, action.asset, { returnDate: custody.date, conditionAtReturn: custody.condition, notes: custody.notes }), action.kind === 'assign' ? 'Asset assigned.' : 'Asset returned.')
        if (saved) setAction(null)
      }}><p>{action.asset.name}</p>{action.kind === 'assign' && <EmployeePicker authentication={authentication} branchId={branchId} value={custody.employeeId} onChange={(employeeId) => setCustody({ ...custody, employeeId })} required />}<label>{action.kind === 'assign' ? 'Assignment date' : 'Return date'}<input type="date" required value={custody.date} onChange={(event) => setCustody({ ...custody, date: event.target.value })} /></label><label>Condition<select value={custody.condition} onChange={(event) => setCustody({ ...custody, condition: event.target.value })}>{['good', 'fair', 'poor', 'damaged'].map((value) => <option key={value}>{value}</option>)}</select></label><label>Notes<textarea maxLength={1000} value={custody.notes} onChange={(event) => setCustody({ ...custody, notes: event.target.value })} /></label><button type="submit" className="btn btn-primary" disabled={busy || action.kind === 'assign' && !custody.employeeId}>{busy ? 'Saving...' : action.kind === 'assign' ? 'Assign asset' : 'Return asset'}</button><Status message={message} /></form>}
    </FormDialog>
  </section>
}

export function EvidenceActions({ authentication, branchId, kind, item, reload, busy, setBusy, setMessage }) {
  const choose = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setBusy(true)
    try { await uploadEvidence(authentication, branchId, kind, item, file); setMessage('Evidence uploaded for scanning.'); await reload() }
    catch { setMessage('The evidence could not be uploaded.') }
    finally { setBusy(false); event.target.value = '' }
  }
  const download = async () => {
    setBusy(true)
    try {
      const signed = await downloadEvidence(authentication, branchId, kind, item)
      globalThis.open(signed.url, '_blank', 'noopener,noreferrer')
    } catch { setMessage('Evidence is unavailable until its security scan passes.') }
    finally { setBusy(false) }
  }
  return <div className="expense-actions">
    {!item.hasEvidence && (kind === 'certification' ? ['pending_review', 'verified'].includes(item.status) : ['planned', 'in_progress', 'completed'].includes(item.status)) && <label className="evidence-picker">Upload evidence<input type="file" disabled={busy} accept="application/pdf,image/png,image/jpeg" onChange={choose} /></label>}
    {item.hasEvidence && <button type="button" disabled={busy} onClick={download}>Download</button>}
  </div>
}

function DevelopmentWorkspace({ account, authentication, branchId }) {
  const [employeeId, setEmployeeId] = useState('')
  const [training, setTraining] = useState([])
  const [certifications, setCertifications] = useState([])
  const [trainingForm, setTrainingForm] = useState(emptyTraining)
  const [editingTraining, setEditingTraining] = useState(null)
  const [editingCertification, setEditingCertification] = useState(null)
  const [formEmployeeId, setFormEmployeeId] = useState('')
  const [certificationForm, setCertificationForm] = useState(emptyCertification)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('training')
  const [showTrainingForm, setShowTrainingForm] = useState(false)
  const [showCertificationForm, setShowCertificationForm] = useState(false)
  const [filter, setFilter] = useState('all')
  const [loadState, setLoadState] = useState('loading')
  const [employees, setEmployees] = useState([])
  const [decision, setDecision] = useState(null)
  const [reason, setReason] = useState('')
  const [completion, setCompletion] = useState({ endDate: '', durationHours: '1.00', score: '', passed: true, isCme: false })
  const targetEmployee = employeeId.trim() || null

  const load = useCallback(async () => {
    setLoadState('loading')
    try {
      if (account.role === 'manager' && targetEmployee === null) {
        const [ownTraining, ownCertifications] = await Promise.all([
          readTraining(authentication, null, 'employee'),
          readCertifications(authentication, null, 'employee'),
        ])
        setTraining(ownTraining.items); setCertifications(ownCertifications.items); setLoadState('ready'); return
      }
      const [trainingResult, certificationResult] = await Promise.all([
        readTraining(authentication, branchId, account.role, targetEmployee),
        readCertifications(authentication, branchId, account.role, targetEmployee),
      ])
      setTraining(trainingResult.items); setCertifications(certificationResult.items)
      if (account.role === 'admin') setEmployees(await readAllEmployees(authentication, branchId))
      setLoadState('ready')
    } catch { setLoadState('error') }
  }, [account.role, authentication, branchId, targetEmployee])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action(); setMessage(success); await load(); return true }
    catch { setMessage('The development action could not be completed.'); return false }
    finally { setBusy(false) }
  }

  const addTraining = (event) => {
    event.preventDefault()
    run(async () => {
      if (editingTraining === null) {
        await createTraining(authentication, branchId, account.role, account.role === 'admin' ? formEmployeeId : targetEmployee, trainingForm)
      } else {
        await updateTraining(authentication, branchId, account.role, editingTraining, trainingForm)
      }
      setTrainingForm(emptyTraining)
      setEditingTraining(null)
      setShowTrainingForm(false)
    }, editingTraining === null ? 'Training record added.' : 'Training record updated.')
  }
  const addCertification = (event) => {
    event.preventDefault()
    run(async () => {
      if (editingCertification) await updateCertification(authentication, account.role === 'admin' ? branchId : null, editingCertification, certificationForm)
      else await createCertification(authentication, branchId, account.role, account.role === 'admin' ? formEmployeeId : targetEmployee, certificationForm)
      setCertificationForm(emptyCertification); setShowCertificationForm(false)
      setEditingCertification(null)
    }, editingCertification ? 'Certification edited and sent for review.' : 'Certification added.')
  }
  const canCreate = account.role !== 'admin' || Boolean(formEmployeeId)
  const openCreate = () => {
    setFormEmployeeId(targetEmployee ?? '')
    if (tab === 'training') { setEditingTraining(null); setTrainingForm(emptyTraining); setShowTrainingForm(true) }
    else { setEditingCertification(null); setCertificationForm(emptyCertification); setShowCertificationForm(true) }
  }
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })
  const expiryCutoff = new Date(`${today}T00:00:00Z`)
  expiryCutoff.setUTCDate(expiryCutoff.getUTCDate() + 60)
  const stats = tab === 'training' ? [
    { label: 'Total records', value: training.length },
    { label: 'Completed', value: training.filter((item) => item.status === 'completed').length },
    { label: 'In progress', value: training.filter((item) => item.status === 'in_progress').length },
    ...(account.role === 'admin' ? [{ label: 'Total cost', value: `AED ${training.reduce((sum, item) => sum + Number(item.cost), 0).toLocaleString('en-AE', { minimumFractionDigits: 2 })}` }] : []),
  ] : [
    { label: 'Total certifications', value: certifications.length },
    { label: 'Expired', value: certifications.filter((item) => item.expiryDate && item.expiryDate < today).length },
    { label: 'Expiring within 60 days', value: certifications.filter((item) => item.expiryDate && item.expiryDate >= today && item.expiryDate <= expiryCutoff.toISOString().slice(0, 10)).length },
    { label: 'Lifetime / no expiry', value: certifications.filter((item) => !item.expiryDate).length },
  ]

  const trainingRecords = training.filter((item) => filter === 'all' || item.status === filter)
  const certificationRecords = certifications.filter((item) => filter === 'all' || item.status === filter || filter === 'expired' && item.expiryDate && item.expiryDate < new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }))
  return <section className="restored-module development-workspace" aria-labelledby="development-title">
    <header className="restored-module-header"><div><h3 id="development-title">Training &amp; Certifications</h3><p>Training records, certifications, and annual CME tracking.</p></div>{tab !== 'cme' && <button type="button" className="btn btn-primary" disabled={busy} onClick={openCreate}>{tab === 'training' ? 'Add Training' : 'Add Certification'}</button>}</header><Status message={message} />
    <FilterTabs label="Development records" options={[{ value: 'training', label: 'Training' }, { value: 'certifications', label: 'Certifications' }, { value: 'cme', label: 'CME' }]} value={tab} onChange={(value) => { setTab(value); setFilter('all') }} />
    {tab !== 'cme' && <SummaryCards items={stats.map((item) => ({ ...item, value: loadState === 'ready' ? item.value : 'Not available' }))} />}
    {account.role !== 'employee' && tab !== 'cme' && <EmployeePicker authentication={authentication} branchId={branchId} role={account.role} value={employeeId} onChange={(value) => { setEmployeeId(value); setShowTrainingForm(false); setShowCertificationForm(false); setDecision(null); setMessage('') }} label={account.role === 'admin' ? 'Employee' : 'Training for'} emptyLabel={account.role === 'admin' ? 'All employees' : 'My training'} />}
    {tab !== 'cme' && <div className="restored-toolbar"><FilterTabs label={tab === 'training' ? 'Training status' : 'Certification status'} options={(tab === 'training' ? ['all', 'planned', 'in_progress', 'completed', 'cancelled'] : ['all', 'pending_review', 'verified', 'rejected', 'expired']).map((value) => ({ value, label: value.replaceAll('_', ' ') }))} value={filter} onChange={setFilter} /><button type="button" className="btn btn-outline" disabled={busy} onClick={load}>Reload</button></div>}
    {loadState === 'loading' && <p role="status">Loading development records...</p>}
    {loadState === 'error' && <div className="alert alert-danger" role="alert">Development records are unavailable. Reload to try again.</div>}
    <FormDialog title={editingTraining ? 'Edit training' : 'Add training'} open={showTrainingForm} onClose={() => { if (!busy) setShowTrainingForm(false) }}>
      <form className="expense-form restoration-form" onSubmit={addTraining}>
        <h4>{editingTraining === null ? 'Add planned training' : 'Edit planned training'}</h4>
        {account.role === 'admin' && !editingTraining && <EmployeePicker authentication={authentication} branchId={branchId} value={formEmployeeId} onChange={setFormEmployeeId} required />}
        <label>Title<input required maxLength="180" value={trainingForm.trainingTitle} onChange={(event) => setTrainingForm({ ...trainingForm, trainingTitle: event.target.value })} /></label>
        <label>Type<input required maxLength="120" value={trainingForm.trainingType} onChange={(event) => setTrainingForm({ ...trainingForm, trainingType: event.target.value })} /></label>
        <label>Provider<input maxLength="180" value={trainingForm.provider} onChange={(event) => setTrainingForm({ ...trainingForm, provider: event.target.value })} /></label>
        <label>Start date<input type="date" value={trainingForm.startDate ?? ''} onChange={(event) => setTrainingForm({ ...trainingForm, startDate: event.target.value || null })} /></label>
        <label>End date<input type="date" value={trainingForm.endDate ?? ''} onChange={(event) => setTrainingForm({ ...trainingForm, endDate: event.target.value || null })} /></label>
        <label>Duration hours<input inputMode="decimal" pattern="[0-9]+\.[0-9]{2}" value={trainingForm.durationHours ?? ''} onChange={(event) => setTrainingForm({ ...trainingForm, durationHours: event.target.value || null })} /></label>
        <label>Notes<textarea maxLength="1000" value={trainingForm.notes} onChange={(event) => setTrainingForm({ ...trainingForm, notes: event.target.value })} /></label>
        {account.role === 'admin' && <label>Cost<input required pattern="[0-9]+\.[0-9]{2}" value={trainingForm.cost} onChange={(event) => setTrainingForm({ ...trainingForm, cost: event.target.value })} /></label>}
        {account.role === 'admin' && <label className="checkbox-row"><input type="checkbox" checked={trainingForm.isCme} onChange={(event) => setTrainingForm({ ...trainingForm, isCme: event.target.checked })} />Counts toward CME</label>}
        <button type="submit" disabled={busy || !editingTraining && !canCreate}>{editingTraining === null ? 'Add training' : 'Update training'}</button>
        {editingTraining !== null && <button type="button" disabled={busy} onClick={() => { setEditingTraining(null); setTrainingForm(emptyTraining) }}>Cancel edit</button>}
        <Status message={message} />
      </form>
    </FormDialog>
    <FormDialog title={editingCertification ? 'Edit certification' : 'Add certification'} open={showCertificationForm} onClose={() => { if (!busy) setShowCertificationForm(false) }}>
      <form className="expense-form restoration-form" onSubmit={addCertification}>
        {editingCertification && <p>Saving edits returns this certification to review. Its evidence stays protected.</p>}
        {account.role === 'admin' && !editingCertification && <EmployeePicker authentication={authentication} branchId={branchId} value={formEmployeeId} onChange={setFormEmployeeId} required />}
        <label>Name<input required maxLength="180" value={certificationForm.certificationName} onChange={(event) => setCertificationForm({ ...certificationForm, certificationName: event.target.value })} /></label>
        <label>Issuing body<input required maxLength="180" value={certificationForm.issuingBody} onChange={(event) => setCertificationForm({ ...certificationForm, issuingBody: event.target.value })} /></label>
        <label>Certificate number<input maxLength="120" value={certificationForm.certificateNo} onChange={(event) => setCertificationForm({ ...certificationForm, certificateNo: event.target.value })} /></label>
        <label>Issue date<input type="date" value={certificationForm.issuedDate ?? ''} onChange={(event) => setCertificationForm({ ...certificationForm, issuedDate: event.target.value || null })} /></label>
        <label>Expiry date<input type="date" value={certificationForm.expiryDate ?? ''} onChange={(event) => setCertificationForm({ ...certificationForm, expiryDate: event.target.value || null })} /></label>
        <label>Notes<textarea maxLength="1000" value={certificationForm.notes} onChange={(event) => setCertificationForm({ ...certificationForm, notes: event.target.value })} /></label>
        <button type="submit" disabled={busy || !editingCertification && !canCreate}>{editingCertification ? 'Save certification' : 'Add certification'}</button><Status message={message} />
      </form>
    </FormDialog>
    {tab === 'training' && <><h4>Training records</h4>
    <PortalTable label="Training records" className="expense-table"><thead><tr>{account.role === 'admin' && <th>Employee</th>}<th>Training</th><th>Type</th><th>Dates</th><th>Status</th><th>Hours</th><th>Evidence</th><th>Actions</th></tr></thead>
      <tbody>{trainingRecords.map((record) => <tr key={record.id}>{account.role === 'admin' && <td>{employees.find((employee) => employee.id === record.employeeId)?.name ?? 'Employee unavailable'}</td>}<td>{record.trainingTitle}<small>{record.provider}</small></td><td>{record.trainingType}</td><td>{record.startDate ?? 'Not set'}<small>{record.endDate ?? 'Not set'}</small></td>
        <td><StatusPill value={record.status} /></td><td>{record.durationHours ?? 'Not set'}</td>
        <td>{record.hasEvidence ? record.fileName : 'None'}</td><td><EvidenceActions authentication={authentication} branchId={account.role === 'admin' ? branchId : null} kind="training" item={record} reload={load} busy={busy} setBusy={setBusy} setMessage={setMessage} />
          {record.status === 'planned' && <button type="button" disabled={busy} onClick={() => {
            setEditingTraining(record)
            setShowTrainingForm(true)
            setTrainingForm({
              trainingTitle: record.trainingTitle, trainingType: record.trainingType,
              provider: record.provider, startDate: record.startDate, endDate: record.endDate,
              durationHours: record.durationHours, notes: record.notes,
              cost: record.cost, isCme: record.isCme,
            })
          }}>Edit</button>}
          {(['planned', 'in_progress'].includes(record.status) || record.status === 'completed' && record.resultVerified === false) && (account.role === 'admin' || account.role === 'manager' && targetEmployee && targetEmployee !== account.employeeId) && <button type="button" disabled={busy} onClick={() => { setCompletion({ endDate: new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }), durationHours: record.durationHours ?? '1.00', score: '', passed: true, isCme: record.isCme }); setDecision({ kind: 'complete', item: record }) }}>Complete</button>}
          {record.status === 'planned' && <button type="button" className="danger" disabled={busy} onClick={() => setDecision({ kind: 'removeTraining', item: record })}>Remove</button>}</td></tr>)}{loadState === 'ready' && trainingRecords.length === 0 && <tr><td colSpan={account.role === 'admin' ? 8 : 7}><div className="empty-state">No training records found.</div></td></tr>}</tbody>
    </PortalTable></>}
    {tab === 'certifications' && <><h4>Certifications</h4>
    <PortalTable label="Certifications" className="expense-table"><thead><tr>{account.role === 'admin' && <th>Employee</th>}<th>Certification</th><th>Status</th><th>Expiry</th><th>Evidence</th><th>Actions</th></tr></thead>
      <tbody>{certificationRecords.map((certification) => <tr key={certification.id}>{account.role === 'admin' && <td>{employees.find((employee) => employee.id === certification.employeeId)?.name ?? 'Employee unavailable'}</td>}<td>{certification.certificationName}<small>{certification.issuingBody}</small></td>
        <td><StatusPill value={certification.status} /></td><td>{certification.expiryDate ?? 'None'}{certification.expiryDate && certification.expiryDate < new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }) && <StatusPill value="expired" />}</td><td>{certification.hasEvidence ? certification.fileName : 'None'}</td>
        <td><EvidenceActions authentication={authentication} branchId={account.role === 'admin' ? branchId : null} kind="certification" item={certification} reload={load} busy={busy} setBusy={setBusy} setMessage={setMessage} />
          {(account.role === 'admin' || certification.status !== 'verified') && <button type="button" disabled={busy} onClick={() => { setEditingCertification(certification); setCertificationForm({ certificationName: certification.certificationName, issuingBody: certification.issuingBody, certificateNo: certification.certificateNo, issuedDate: certification.issuedDate, expiryDate: certification.expiryDate, notes: certification.notes }); setShowCertificationForm(true) }}>Edit</button>}
          {account.role === 'admin' && certification.status === 'pending_review' && <>
            <button type="button" disabled={busy} onClick={() => run(() => decideCertification(authentication, branchId, certification, 'verify'), 'Certification verified.')}>Verify</button>
            <button type="button" disabled={busy} onClick={() => { setReason(''); setDecision({ kind: 'reject', item: certification }) }}>Reject</button></>}
          {certification.status !== 'verified' && <button type="button" className="danger" disabled={busy} onClick={() => setDecision({ kind: 'removeCertification', item: certification })}>Remove</button>}
        </td></tr>)}{loadState === 'ready' && certificationRecords.length === 0 && <tr><td colSpan={account.role === 'admin' ? 6 : 5}><div className="empty-state">No certification records found.</div></td></tr>}</tbody>
    </PortalTable></>}
    {tab === 'cme' && (account.role === 'admin'
      ? <BranchCme authentication={authentication} branchId={branchId} />
      : <CmeSummary authentication={authentication} />)}
    <FormDialog title={decision?.kind === 'complete' ? 'Complete training' : decision?.kind === 'reject' ? 'Reject certification' : 'Remove record'} open={Boolean(decision)} onClose={() => { if (!busy) setDecision(null) }}><form className="restoration-form" onSubmit={async (event) => {
      event.preventDefault()
      const saved = await run(() => decision.kind === 'complete' ? completeTraining(authentication, account.role === 'admin' ? branchId : null, decision.item, completion) : decision.kind === 'reject' ? decideCertification(authentication, branchId, decision.item, 'reject', reason.trim()) : decision.kind === 'removeTraining' ? deleteTraining(authentication, account.role === 'admin' ? branchId : null, decision.item) : deleteCertification(authentication, account.role === 'admin' ? branchId : null, decision.item), decision.kind === 'complete' ? 'Training completed.' : decision.kind === 'reject' ? 'Certification rejected.' : 'Record removed.')
      if (saved) setDecision(null)
    }}>{decision?.kind === 'complete' ? <><label>Completion date<input required type="date" value={completion.endDate} onChange={(event) => setCompletion({ ...completion, endDate: event.target.value })} /></label><label>Duration hours<input required pattern="[0-9]+\.[0-9]{2}" value={completion.durationHours} onChange={(event) => setCompletion({ ...completion, durationHours: event.target.value })} /></label><label>Score<input maxLength={120} value={completion.score} onChange={(event) => setCompletion({ ...completion, score: event.target.value })} /></label><label><input type="checkbox" checked={completion.passed} onChange={(event) => setCompletion({ ...completion, passed: event.target.checked })} />Passed</label><label><input type="checkbox" checked={completion.isCme} onChange={(event) => setCompletion({ ...completion, isCme: event.target.checked })} />Counts toward CME</label></> : decision?.kind === 'reject' ? <label>Reason<textarea required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label> : <p>Remove this record? This action requires confirmation from the server.</p>}<button type="submit" className={`btn ${decision?.kind === 'complete' ? 'btn-primary' : 'btn-danger'}`} disabled={busy}>{busy ? 'Saving...' : decision?.kind === 'complete' ? 'Complete training' : decision?.kind === 'reject' ? 'Reject certification' : 'Remove record'}</button><Status message={message} /></form></FormDialog>
  </section>
}

function BranchCme({ authentication, branchId }) {
  const [year, setYear] = useState(new Date().getUTCFullYear())
  const [state, setState] = useState({ status: 'loading', items: [] })
  const [target, setTarget] = useState(null)
  const [employeeId, setEmployeeId] = useState('')
  const [hours, setHours] = useState('25.0')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [remove, setRemove] = useState(false)
  const load = useCallback(async () => {
    try { setState({ status: 'ready', items: await readBranchCme(authentication, branchId, year) }) }
    catch { setState({ status: 'error', items: [] }) }
  }, [authentication, branchId, year])
  useEffect(() => { const pending = globalThis.setTimeout(load, 0); return () => globalThis.clearTimeout(pending) }, [load])
  const totalTarget = state.items.reduce((sum, item) => sum + Number(item.targetHours), 0)
  const achieved = state.items.reduce((sum, item) => sum + Number(item.achievedHours), 0)
  const open = (item = null) => { setTarget({ current: item?.requirement ?? null }); setEmployeeId(item?.employeeId ?? ''); setHours(item?.targetHours ?? '25.0'); setNotes(item?.requirement?.notes ?? ''); setMessage(''); setRemove(false) }
  const save = async () => {
    setBusy(true); setMessage('')
    try {
      if (remove) await deleteCmeRequirement(authentication, branchId, employeeId, year, target.current)
      else await saveCmeRequirement(authentication, branchId, employeeId, year, { requiredHours: hours, notes }, target.current)
      setTarget(null); await load()
    } catch { setMessage('The CME target could not be saved. Your entries have been kept.') }
    finally { setBusy(false) }
  }
  return <section className="restored-module"><div className="restored-toolbar"><label>Year<input type="number" min={1900} max={9999} value={year} onChange={(event) => { const value = Number(event.target.value); if (value >= 1900 && value <= 9999) { setYear(value); setState({ status: 'loading', items: [] }) } }} /></label><button type="button" className="btn btn-outline" onClick={load}>Reload CME</button><button type="button" className="btn btn-primary" onClick={() => open()}>Set Target</button></div>
    <SummaryCards items={[{ label: 'Staff with targets', value: state.items.filter((item) => Number(item.targetHours) > 0).length }, { label: 'Hours completed', value: achieved.toFixed(1), detail: `of ${totalTarget.toFixed(1)} target hours` }, { label: 'Below target', value: state.items.filter((item) => Number(item.gapHours) > 0).length }, { label: 'Overall compliance', value: totalTarget > 0 ? `${Math.round(achieved / totalTarget * 100)}%` : 'No target' }].map((item) => ({ ...item, value: state.status === 'ready' ? item.value : 'Not available', detail: state.status === 'ready' ? item.detail : null }))} />
    {state.status === 'error' && <p role="alert">CME tracking is unavailable. Reload to try again.</p>}{state.status === 'loading' && <p role="status">Loading CME tracking...</p>}
    <PortalTable label="CME targets"><thead><tr><th>Employee</th><th>Department</th><th>Target hours</th><th>Completed</th><th>In progress</th><th>Remaining</th><th>Progress</th><th>Actions</th></tr></thead><tbody>{state.items.map((item) => { const progress = Number(item.targetHours) > 0 ? Math.min(100, Math.round(Number(item.achievedHours) / Number(item.targetHours) * 100)) : 0; return <tr key={item.employeeId}><td><strong>{item.employeeName}</strong></td><td>{item.department}</td><td>{item.targetHours}h</td><td>{item.achievedHours}h</td><td>{item.inProgressHours}h</td><td>{Number(item.gapHours) > 0 ? `${item.gapHours}h` : Number(item.targetHours) > 0 ? 'Met' : 'No target'}</td><td><progress aria-label={`${item.employeeName} CME progress`} max={100} value={progress} /> {progress}%</td><td><button type="button" className="btn btn-outline btn-sm" onClick={() => open(item)}>Edit target</button>{item.requirement && <button type="button" className="btn btn-danger btn-sm" onClick={() => { open(item); setRemove(true) }}>Remove target</button>}</td></tr> })}{state.status === 'ready' && state.items.length === 0 && <tr><td colSpan={8}><div className="empty-state">No CME targets or training records for {year}.</div></td></tr>}</tbody></PortalTable>
    <FormDialog title={remove ? 'Remove CME target' : target?.current ? 'Edit CME target' : 'Set CME target'} open={Boolean(target)} onClose={() => { if (!busy) setTarget(null) }}><form className="restoration-form" onSubmit={(event) => { event.preventDefault(); save() }}>{remove ? <p>Remove this employee's target for {year}? Training records will be kept.</p> : <>{target?.current ? <p>{state.items.find((item) => item.employeeId === employeeId)?.employeeName} · {year}</p> : <EmployeePicker authentication={authentication} branchId={branchId} value={employeeId} onChange={(value) => { const item = state.items.find((entry) => entry.employeeId === value); setEmployeeId(value); setTarget({ current: item?.requirement ?? null }); setHours(item?.targetHours ?? '25.0'); setNotes(item?.requirement?.notes ?? '') }} required />}<label>Required hours<input required pattern="[0-9]+\.[0-9]" value={hours} onChange={(event) => setHours(event.target.value)} /></label><label>Notes<textarea maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label></>}<button type="submit" className={`btn ${remove ? 'btn-danger' : 'btn-primary'}`} disabled={busy || !employeeId}>{busy ? 'Saving...' : remove ? 'Remove target' : 'Save target'}</button><Status message={message} /></form></FormDialog>
  </section>
}

function CmeSummary({ authentication }) {
  const year = new Date().getUTCFullYear()
  const [summary, setSummary] = useState(null)
  useEffect(() => {
    let current = true
    readSelfCme(authentication, year).then((value) => { if (current) setSummary(value) }).catch(() => { if (current) setSummary(null) })
    return () => { current = false }
  }, [authentication, year])
  if (!summary) return <p>CME summary is unavailable.</p>
  return <section aria-labelledby="cme-summary-title"><h4 id="cme-summary-title">CME summary for {year}</h4>
    <p>Target: {summary.targetHours} hours · Achieved: {summary.achievedHours} hours · Gap: {summary.gapHours} hours</p></section>
}

export default function DevelopmentAssets({ account, assetsOnly = false, authentication, branchId, trainingOnly = false }) {
  const title = assetsOnly ? 'Assets' : trainingOnly ? 'Training' : 'Assets and professional development'
  return <section className="records-benefits restoration-group" aria-labelledby="development-assets-title">
    <h2 id="development-assets-title" className="sr-only">{title}</h2>
    {!trainingOnly && <AssetWorkspace account={account} authentication={authentication} branchId={branchId} />}
    {!assetsOnly && (account.role === 'admin' ? <DevelopmentWorkspace account={account} authentication={authentication} branchId={branchId} /> : <Suspense fallback={<p role="status">Loading training and certifications...</p>}><StaffDevelopment key={`${account.role}:${account.employeeId}`} account={account} authentication={authentication} /></Suspense>)}
  </section>
}

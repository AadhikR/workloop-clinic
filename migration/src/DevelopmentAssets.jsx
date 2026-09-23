import { useCallback, useEffect, useState } from 'react'

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
  readCertifications,
  readCmeRequirement,
  readSelfAssets,
  readSelfCme,
  readTraining,
  returnAsset,
  saveAsset,
  saveCmeRequirement,
  updateTraining,
  uploadEvidence,
} from './developmentAssetsApi.js'

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

  const load = useCallback(async () => {
    try {
      const result = account.role === 'admin'
        ? await readAssets(authentication, branchId)
        : await readSelfAssets(authentication)
      setItems(result.items)
    } catch { setItems([]) }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const run = async (action, success) => {
    setBusy(true)
    setMessage('')
    try { await action(); setMessage(success); await load() }
    catch { setMessage('The asset action could not be completed.') }
    finally { setBusy(false) }
  }

  const submit = (event) => {
    event.preventDefault()
    run(async () => {
      await saveAsset(authentication, branchId, form, editing)
      setForm(emptyAsset)
      setEditing(null)
    }, editing === null ? 'Asset saved.' : 'Asset updated.')
  }

  if (account.role !== 'admin') {
    return <section aria-labelledby="my-assets-title">
      <h3 id="my-assets-title">My assets</h3>
      <p>Current custody and retained assignment history.</p>
      <table className="expense-table"><thead><tr><th>Asset</th><th>Assigned</th><th>Returned</th><th>Condition</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.id}><td>{item.assetName}<small>{item.assetCode}</small></td>
          <td>{item.assignedDate}</td><td>{item.returnDate ?? 'Current'}</td>
          <td>{item.conditionAtReturn ?? item.conditionAtHandover}</td></tr>)}</tbody>
      </table>
    </section>
  }

  return <section aria-labelledby="asset-inventory-title">
    <h3 id="asset-inventory-title">Asset inventory</h3><Status message={message} />
    <form className="expense-form" onSubmit={submit}>
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
    <table className="expense-table"><thead><tr><th>Asset</th><th>Status</th><th>Cost</th><th>Actions</th></tr></thead>
      <tbody>{items.map((asset) => <tr key={asset.id}><td>{asset.name}<small>{asset.assetCode || asset.serialNumber}</small></td>
        <td>{asset.status.replaceAll('_', ' ')}</td><td>{asset.purchaseCost ?? 'Not recorded'}</td>
        <td><div className="expense-actions">
          <button type="button" disabled={busy} onClick={() => {
            setEditing(asset)
            setForm({
              name: asset.name, assetCode: asset.assetCode, category: asset.category,
              brand: asset.brand, model: asset.model, serialNumber: asset.serialNumber,
              purchaseDate: asset.purchaseDate, purchaseCost: asset.purchaseCost, notes: asset.notes,
            })
          }}>Edit</button>
          {asset.status === 'available' && <button type="button" disabled={busy} onClick={() => {
            const employeeId = globalThis.prompt('Employee ID')?.trim()
            if (employeeId) run(() => assignAsset(authentication, branchId, asset, { employeeId, conditionAtHandover: 'good', notes: '' }), 'Asset assigned.')
          }}>Assign</button>}
          {asset.status === 'assigned' && <button type="button" disabled={busy} onClick={() => run(() => returnAsset(authentication, branchId, asset, { conditionAtReturn: 'good', notes: '' }), 'Asset returned.')}>Return</button>}
          {asset.status === 'available' && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'under_repair'), 'Asset status changed.')}>Repair</button>}
          {asset.status === 'under_repair' && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'available'), 'Asset returned to service.')}>Return to service</button>}
          {['available', 'under_repair'].includes(asset.status) && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'retired'), 'Asset retired.')}>Retire</button>}
          {['available', 'under_repair'].includes(asset.status) && <button type="button" disabled={busy} onClick={() => run(() => changeAssetStatus(authentication, branchId, asset, 'lost'), 'Asset marked lost.')}>Mark lost</button>}
          {asset.status !== 'assigned' && <button type="button" className="danger" disabled={busy} onClick={() => run(() => deleteAsset(authentication, branchId, asset), 'Asset removed.')}>Remove</button>}
        </div></td></tr>)}</tbody>
    </table>
  </section>
}

function EvidenceActions({ authentication, branchId, kind, item, reload, busy, setBusy, setMessage }) {
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
    <label className="button">Upload evidence<input hidden type="file" disabled={busy} accept="application/pdf,image/png,image/jpeg" onChange={choose} /></label>
    {item.hasEvidence && <button type="button" disabled={busy} onClick={download}>Download</button>}
  </div>
}

function DevelopmentWorkspace({ account, authentication, branchId }) {
  const [employeeId, setEmployeeId] = useState('')
  const [training, setTraining] = useState([])
  const [certifications, setCertifications] = useState([])
  const [trainingForm, setTrainingForm] = useState(emptyTraining)
  const [editingTraining, setEditingTraining] = useState(null)
  const [certificationForm, setCertificationForm] = useState(emptyCertification)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const targetEmployee = employeeId.trim() || null

  const load = useCallback(async () => {
    if (account.role === 'admin' && targetEmployee === null) { setTraining([]); setCertifications([]); return }
    if (account.role === 'manager' && targetEmployee === null) {
      const [ownTraining, ownCertifications] = await Promise.all([
        readTraining(authentication, null, 'employee'),
        readCertifications(authentication, null, 'employee'),
      ])
      setTraining(ownTraining.items); setCertifications(ownCertifications.items); return
    }
    try {
      const [trainingResult, certificationResult] = await Promise.all([
        readTraining(authentication, branchId, account.role, targetEmployee),
        readCertifications(authentication, branchId, account.role, targetEmployee),
      ])
      setTraining(trainingResult.items); setCertifications(certificationResult.items)
    } catch { setTraining([]); setCertifications([]) }
  }, [account.role, authentication, branchId, targetEmployee])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action(); setMessage(success); await load() }
    catch { setMessage('The development action could not be completed.') }
    finally { setBusy(false) }
  }

  const addTraining = (event) => {
    event.preventDefault()
    run(async () => {
      if (editingTraining === null) {
        await createTraining(authentication, branchId, account.role, targetEmployee, trainingForm)
      } else {
        await updateTraining(authentication, branchId, account.role, editingTraining, trainingForm)
      }
      setTrainingForm(emptyTraining)
      setEditingTraining(null)
    }, editingTraining === null ? 'Training record added.' : 'Training record updated.')
  }
  const addCertification = (event) => {
    event.preventDefault()
    run(() => createCertification(authentication, branchId, account.role, targetEmployee, certificationForm), 'Certification added.')
      .then(() => setCertificationForm(emptyCertification))
  }
  const canCreate = account.role === 'employee' || account.role === 'manager' || targetEmployee !== null

  return <section aria-labelledby="development-title">
    <h3 id="development-title">Training, certifications, and CME</h3><Status message={message} />
    {account.role !== 'employee' && <label>{account.role === 'admin' ? 'Employee ID' : 'Direct report ID (leave blank for yourself)'}
      <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} /></label>}
    {canCreate && <div className="records-benefits-grid">
      <form className="expense-form" onSubmit={addTraining}>
        <h4>{editingTraining === null ? 'Add planned training' : 'Edit planned training'}</h4>
        <label>Title<input required maxLength="180" value={trainingForm.trainingTitle} onChange={(event) => setTrainingForm({ ...trainingForm, trainingTitle: event.target.value })} /></label>
        <label>Type<input required maxLength="120" value={trainingForm.trainingType} onChange={(event) => setTrainingForm({ ...trainingForm, trainingType: event.target.value })} /></label>
        <label>Provider<input maxLength="180" value={trainingForm.provider} onChange={(event) => setTrainingForm({ ...trainingForm, provider: event.target.value })} /></label>
        <label>Start date<input type="date" value={trainingForm.startDate ?? ''} onChange={(event) => setTrainingForm({ ...trainingForm, startDate: event.target.value || null })} /></label>
        <label>End date<input type="date" value={trainingForm.endDate ?? ''} onChange={(event) => setTrainingForm({ ...trainingForm, endDate: event.target.value || null })} /></label>
        {account.role === 'admin' && <label>Cost<input required pattern="[0-9]+\.[0-9]{2}" value={trainingForm.cost} onChange={(event) => setTrainingForm({ ...trainingForm, cost: event.target.value })} /></label>}
        <button type="submit" disabled={busy}>{editingTraining === null ? 'Add training' : 'Update training'}</button>
        {editingTraining !== null && <button type="button" disabled={busy} onClick={() => { setEditingTraining(null); setTrainingForm(emptyTraining) }}>Cancel edit</button>}
      </form>
      <form className="expense-form" onSubmit={addCertification}>
        <h4>Add certification</h4>
        <label>Name<input required maxLength="180" value={certificationForm.certificationName} onChange={(event) => setCertificationForm({ ...certificationForm, certificationName: event.target.value })} /></label>
        <label>Issuing body<input required maxLength="180" value={certificationForm.issuingBody} onChange={(event) => setCertificationForm({ ...certificationForm, issuingBody: event.target.value })} /></label>
        <label>Certificate number<input maxLength="120" value={certificationForm.certificateNo} onChange={(event) => setCertificationForm({ ...certificationForm, certificateNo: event.target.value })} /></label>
        <label>Issue date<input type="date" value={certificationForm.issuedDate ?? ''} onChange={(event) => setCertificationForm({ ...certificationForm, issuedDate: event.target.value || null })} /></label>
        <label>Expiry date<input type="date" value={certificationForm.expiryDate ?? ''} onChange={(event) => setCertificationForm({ ...certificationForm, expiryDate: event.target.value || null })} /></label>
        <button type="submit" disabled={busy}>Add certification</button>
      </form>
    </div>}
    <h4>Training records</h4>
    <table className="expense-table"><thead><tr><th>Training</th><th>Status</th><th>Hours</th><th>Evidence</th><th>Actions</th></tr></thead>
      <tbody>{training.map((record) => <tr key={record.id}><td>{record.trainingTitle}<small>{record.provider}</small></td>
        <td>{record.status.replaceAll('_', ' ')}</td><td>{record.durationHours ?? 'Not set'}</td>
        <td>{record.hasEvidence ? record.fileName : 'None'}</td><td><EvidenceActions authentication={authentication} branchId={account.role === 'admin' ? branchId : null} kind="training" item={record} reload={load} busy={busy} setBusy={setBusy} setMessage={setMessage} />
          {record.status === 'planned' && <button type="button" disabled={busy} onClick={() => {
            setEditingTraining(record)
            setTrainingForm({
              trainingTitle: record.trainingTitle, trainingType: record.trainingType,
              provider: record.provider, startDate: record.startDate, endDate: record.endDate,
              durationHours: record.durationHours, notes: record.notes,
              cost: record.cost, isCme: record.isCme,
            })
          }}>Edit</button>}
          {record.status !== 'completed' && account.role !== 'employee' && <button type="button" disabled={busy} onClick={() => run(() => completeTraining(authentication, account.role === 'admin' ? branchId : null, record, { endDate: new Date().toISOString().slice(0, 10), durationHours: record.durationHours ?? '1.00', score: '', passed: true, isCme: record.isCme }), 'Training completed.')}>Complete</button>}
          {record.status === 'planned' && <button type="button" className="danger" disabled={busy} onClick={() => run(() => deleteTraining(authentication, account.role === 'admin' ? branchId : null, record), 'Training removed.')}>Remove</button>}</td></tr>)}</tbody>
    </table>
    <h4>Certifications</h4>
    <table className="expense-table"><thead><tr><th>Certification</th><th>Status</th><th>Expiry</th><th>Evidence</th><th>Actions</th></tr></thead>
      <tbody>{certifications.map((certification) => <tr key={certification.id}><td>{certification.certificationName}<small>{certification.issuingBody}</small></td>
        <td>{certification.status.replaceAll('_', ' ')}</td><td>{certification.expiryDate ?? 'None'}</td><td>{certification.hasEvidence ? certification.fileName : 'None'}</td>
        <td><EvidenceActions authentication={authentication} branchId={account.role === 'admin' ? branchId : null} kind="certification" item={certification} reload={load} busy={busy} setBusy={setBusy} setMessage={setMessage} />
          {account.role === 'admin' && certification.status === 'pending_review' && <>
            <button type="button" disabled={busy} onClick={() => run(() => decideCertification(authentication, branchId, certification, 'verify'), 'Certification verified.')}>Verify</button>
            <button type="button" disabled={busy} onClick={() => {
              const reason = globalThis.prompt('Reason for rejection')?.trim()
              if (reason) run(() => decideCertification(authentication, branchId, certification, 'reject', reason), 'Certification rejected.')
            }}>Reject</button></>}
          {certification.status !== 'verified' && <button type="button" className="danger" disabled={busy} onClick={() => run(() => deleteCertification(authentication, account.role === 'admin' ? branchId : null, certification), 'Certification removed.')}>Remove</button>}
        </td></tr>)}</tbody>
    </table>
    {account.role === 'admin'
      ? targetEmployee && <CmeRequirement authentication={authentication} branchId={branchId} employeeId={targetEmployee} busy={busy} run={run} />
      : <CmeSummary authentication={authentication} />}
  </section>
}

function CmeRequirement({ authentication, branchId, employeeId, busy, run }) {
  const year = new Date().getUTCFullYear()
  const [requiredHours, setRequiredHours] = useState('25.0')
  const [current, setCurrent] = useState(null)
  useEffect(() => {
    let active = true
    readCmeRequirement(authentication, branchId, employeeId, year)
      .then((value) => {
        if (active) {
          setCurrent(value)
          setRequiredHours(value.requiredHours)
        }
      })
      .catch(() => {
        if (active) {
          setCurrent(null)
          setRequiredHours('25.0')
        }
      })
    return () => { active = false }
  }, [authentication, branchId, employeeId, year])
  return <form className="expense-form" onSubmit={(event) => {
    event.preventDefault()
    run(async () => {
      const saved = await saveCmeRequirement(
        authentication, branchId, employeeId, year, { requiredHours, notes: current?.notes ?? '' }, current,
      )
      setCurrent(saved)
      setRequiredHours(saved.requiredHours)
    }, 'CME requirement saved.')
  }}><h4>CME requirement for {year}</h4><label>Required hours<input required pattern="[0-9]+\.[0-9]" value={requiredHours} onChange={(event) => setRequiredHours(event.target.value)} /></label><button type="submit" disabled={busy}>Save requirement</button>
    {current !== null && <button type="button" className="danger" disabled={busy} onClick={() => run(async () => {
      await deleteCmeRequirement(authentication, branchId, employeeId, year, current)
      setCurrent(null)
      setRequiredHours('25.0')
    }, 'CME requirement removed.')}>Remove requirement</button>}
  </form>
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

export default function DevelopmentAssets({ account, authentication, branchId }) {
  return <section className="records-benefits" aria-labelledby="development-assets-title">
    <h2 id="development-assets-title">Assets and professional development</h2>
    <AssetWorkspace account={account} authentication={authentication} branchId={branchId} />
    <DevelopmentWorkspace account={account} authentication={authentication} branchId={branchId} />
  </section>
}

import { useCallback, useEffect, useRef, useState } from 'react'
import EmployeePicker from './EmployeePicker.jsx'
import { readDirectReports } from './employeeApi.js'
import { EvidenceActions } from './DevelopmentAssets.jsx'
import { FilterTabs, FormDialog, StatusPill, SummaryCards } from './PortalUi.jsx'
import {
  completeOwnTraining, completeTraining, createCertification, createTraining,
  deleteCertification, deleteTraining, readCertifications, readSelfCme, readTraining,
  transitionTraining, updateCertification, updateTraining,
} from './developmentAssetsApi.js'

const trainingDefaults = { trainingTitle: '', trainingType: 'external', provider: '', startDate: '', endDate: '', durationHours: '', notes: '' }
const certificateDefaults = { certificationName: '', issuingBody: '', certificateNo: '', issuedDate: '', expiryDate: '', notes: '' }
const dubaiToday = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })

function StaffRecords({ account, authentication, employeeId, own, names = {} }) {
  const [records, setRecords] = useState({ status: 'loading', training: [], certifications: [] })
  const [tab, setTab] = useState('training')
  const [action, setAction] = useState(null)
  const [values, setValues] = useState({})
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const generation = useRef(0)
  const retry = useRef(null)
  const load = useCallback(async () => {
    const token = ++generation.current
    setRecords({ status: 'loading', training: [], certifications: [] })
    try {
      const targets = own ? [null] : employeeId ? [employeeId] : (await readDirectReports(authentication)).data.map((item) => item.id)
      const results = await Promise.all(targets.map((target) => Promise.all([
        readTraining(authentication, null, own ? 'employee' : 'manager', target),
        readCertifications(authentication, null, own ? 'employee' : 'manager', target),
      ])))
      if (token === generation.current) setRecords({ status: 'ready', training: results.flatMap(([training]) => training.items), certifications: results.flatMap(([, certificates]) => certificates.items) })
    } catch { if (token === generation.current) setRecords({ status: 'error', training: [], certifications: [] }) }
  }, [authentication, employeeId, own])
  useEffect(() => { const pending = setTimeout(load, 0); return () => { clearTimeout(pending); generation.current += 1 } }, [load])
  const open = (kind, item = null) => {
    setMessage('')
    retry.current = null
    setAction({ kind, item })
    setValues(kind === 'complete' ? { endDate: dubaiToday(), durationHours: item.durationHours ?? '1.00', score: item.score ?? '', passed: item.passed ?? true, isCme: item.isCme }
      : kind === 'training' ? item ?? trainingDefaults : item ?? certificateDefaults)
  }
  const save = async (event) => {
    event.preventDefault(); setBusy(true); setMessage('')
    const { kind, item } = action
    const fingerprint = JSON.stringify({ kind, id: item?.id, version: item?.updatedAt, values })
    if (retry.current?.fingerprint !== fingerprint) retry.current = { fingerprint, key: crypto.randomUUID() }
    try {
      if (kind === 'training') {
        const payload = Object.fromEntries(Object.keys(trainingDefaults).map((key) => [key, ['startDate', 'endDate', 'durationHours'].includes(key) ? values[key] || null : values[key]]))
        if (item) await updateTraining(authentication, null, account.role, item, payload)
        else await createTraining(authentication, null, account.role, employeeId || values.employeeId, payload)
      } else if (kind === 'certificate') {
        const payload = Object.fromEntries(Object.keys(certificateDefaults).map((key) => [key, key.endsWith('Date') ? values[key] || null : values[key]]))
        if (item) await updateCertification(authentication, null, item, payload)
        else await createCertification(authentication, null, account.role, employeeId || values.employeeId, payload)
      } else if (kind === 'complete') {
        if (own) await completeOwnTraining(authentication, item, values, { idempotencyKey: retry.current.key })
        else await completeTraining(authentication, null, item, values)
      } else if (kind === 'removeTraining') await deleteTraining(authentication, null, item)
      else if (kind === 'removeCertificate') await deleteCertification(authentication, null, item)
      else await transitionTraining(authentication, null, item, kind, { idempotencyKey: retry.current.key })
      setAction(null); await load(); setMessage(kind === 'complete' && own ? 'Your result was saved. It earns no verified CME credit.' : 'Development record saved.')
    } catch { setMessage('The record could not be saved. Your entries have been kept. Reload if its status or reporting manager has changed.') }
    finally { setBusy(false) }
  }
  const field = (key, label, options = {}) => <label key={key}>{label}<input {...options} value={values[key] ?? ''} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>
  const items = records[tab]
  return <>
    <header className="restored-module-header"><div><h3>{own ? 'My Training & Certifications' : 'Team Training & Certifications'}</h3><p>Training results and credentials held by HR.</p></div><button type="button" className="btn btn-outline" disabled={busy} onClick={load}>Reload</button></header>
    {message && <p role={action ? 'alert' : 'status'}>{message}</p>}
    {!own && <FilterTabs label="Development records" value={tab} onChange={setTab} options={[{ value: 'training', label: 'Training' }, { value: 'certifications', label: 'Certifications' }]} />}
    {records.status === 'loading' && <p role="status">Loading development records...</p>}
    {records.status === 'error' && <p role="alert">Development records are unavailable. <button type="button" onClick={load}>Retry</button></p>}
    {records.status === 'ready' && <>
      <SummaryCards items={own ? [{ label: 'Training records', value: records.training.length }, { label: 'Completed', value: records.training.filter((item) => item.status === 'completed').length }, { label: 'Certifications', value: records.certifications.length }] : tab === 'training' ? [{ label: 'Training records', value: items.length }, { label: 'Completed', value: items.filter((item) => item.status === 'completed').length }, { label: 'In progress', value: items.filter((item) => item.status === 'in_progress').length }] : [{ label: 'Certifications', value: items.length }, { label: 'Expired', value: items.filter((item) => item.expiryDate && item.expiryDate < dubaiToday()).length }, { label: 'Pending review', value: items.filter((item) => item.status === 'pending_review').length }]} />
      {(own ? ['training', 'certifications'] : [tab]).map((recordTab) => { const sectionItems = records[recordTab]; return <section key={recordTab} aria-label={recordTab === 'training' ? 'Training records' : 'Certifications'}>
      <div className="restored-toolbar"><h4>{recordTab === 'training' ? 'Training records' : 'Certifications'}</h4><button type="button" className="btn btn-primary" disabled={busy} onClick={() => open(recordTab === 'training' ? 'training' : 'certificate')}>{recordTab === 'training' ? 'Add Training' : 'Add Certification'}</button></div>
      <div className="staff-records">{sectionItems.map((item) => <article className="employee-panel staff-record" key={item.id}>
        <header><div><h4>{item.trainingTitle ?? item.certificationName}</h4><p>{!own && names[item.employeeId] ? `${names[item.employeeId]} · ` : ''}{item.provider ?? item.issuingBody}</p></div><StatusPill value={item.status} /></header>
        {recordTab === 'training' ? <><p>{item.startDate ?? 'Start date not set'} to {item.endDate ?? 'End date not set'} · {item.durationHours ?? 'Hours not recorded'} hours</p>{item.status === 'completed' && <p>Result: {item.passed === null ? 'Not recorded' : item.passed ? 'Passed' : 'Not passed'}{item.score ? ` · ${item.score}` : ''}</p>}{item.resultVerified === false && <p className="alert alert-warning">Self-reported result. No verified CME credit.</p>}<p>{item.notes}</p></> : <><p>{item.certificateNo || 'Certificate number not recorded'} · Expiry {item.expiryDate ?? 'None'}</p>{item.expiryDate && item.expiryDate < dubaiToday() && <p className="alert alert-danger">This certification has expired.</p>}<p>{item.notes}</p></>}
        <EvidenceActions authentication={authentication} branchId={null} kind={recordTab === 'training' ? 'training' : 'certification'} item={item} reload={load} busy={busy} setBusy={setBusy} setMessage={setMessage} />
        <div className="module-actions">{recordTab === 'training' ? <>
          {item.status === 'planned' && <><button type="button" disabled={busy} onClick={() => open('training', item)}>Edit</button><button type="button" disabled={busy} onClick={() => open('start', item)}>Start training</button><button type="button" disabled={busy} onClick={() => open('removeTraining', item)}>Remove</button></>}
          {(['planned', 'in_progress'].includes(item.status) || !own && item.resultVerified === false && item.status === 'completed') && <button type="button" disabled={busy} onClick={() => open('complete', item)}>{own ? 'Record my result' : item.resultVerified === false && item.status === 'completed' ? 'Verify completion' : 'Complete training'}</button>}
          {['planned', 'in_progress'].includes(item.status) && <button type="button" disabled={busy} onClick={() => open('cancel', item)}>Cancel training</button>}
        </> : item.status !== 'verified' && <><button type="button" disabled={busy} onClick={() => open('certificate', item)}>Edit</button><button type="button" disabled={busy} onClick={() => open('removeCertificate', item)}>Remove</button></>}</div>
      </article>)}</div>{sectionItems.length === 0 && <div className="empty-state">No {recordTab === 'training' ? 'training records' : 'certifications'} on file yet.</div>}
      </section> })}
    </>}
    <FormDialog title={action?.kind === 'training' ? action.item ? 'Edit training' : 'Add training' : action?.kind === 'certificate' ? action.item ? 'Edit certification' : 'Add certification' : action?.kind === 'complete' ? own ? 'Record my result' : 'Complete training' : 'Confirm training action'} open={Boolean(action)} onClose={() => { if (!busy) setAction(null) }}>
      <form className="restoration-form" onSubmit={save}>
        {!own && !employeeId && !action?.item && ['training', 'certificate'].includes(action?.kind) && <EmployeePicker authentication={authentication} branchId={null} role="manager" required value={values.employeeId ?? ''} onChange={(value) => setValues({ ...values, employeeId: value })} label="Team member for new record" />}
        {action?.kind === 'training' ? <>{field('trainingTitle', 'Title', { required: true, maxLength: 180 })}{field('trainingType', 'Type', { required: true, maxLength: 120 })}{field('provider', 'Provider', { maxLength: 180 })}{field('startDate', 'Start date', { type: 'date' })}{field('endDate', 'End date', { type: 'date' })}{field('durationHours', 'Duration hours', { pattern: '[0-9]+\\.[0-9]{2}', inputMode: 'decimal' })}</> : action?.kind === 'certificate' ? <>{field('certificationName', 'Name', { required: true, maxLength: 180 })}{field('issuingBody', 'Issuing body', { required: true, maxLength: 180 })}{field('certificateNo', 'Certificate number', { maxLength: 120 })}{field('issuedDate', 'Issue date', { type: 'date' })}{field('expiryDate', 'Expiry date', { type: 'date' })}<p>HR verifies credentials. Edits return the certification to review.</p></> : action?.kind === 'complete' ? <>
          {own && <p>Your result is self-reported. HR or your current manager must verify completion before it can earn CME credit.</p>}{field('endDate', 'Completion date', { required: true, type: 'date', max: dubaiToday(), min: action.item.startDate ?? undefined })}{field('durationHours', 'Duration hours', { required: true, pattern: '[0-9]+\\.[0-9]{2}', inputMode: 'decimal' })}{field('score', 'Score', { maxLength: 120 })}<label className="checkbox-row"><input type="checkbox" checked={values.passed ?? true} onChange={(event) => setValues({ ...values, passed: event.target.checked })} />Passed</label>{!own && <label className="checkbox-row"><input type="checkbox" checked={values.isCme ?? false} onChange={(event) => setValues({ ...values, isCme: event.target.checked })} />Counts toward CME</label>}
        </> : <p>{action?.kind === 'start' ? 'Start' : action?.kind === 'cancel' ? 'Cancel' : 'Remove'} {action?.item.trainingTitle ?? action?.item.certificationName}?</p>}
        {['training', 'certificate'].includes(action?.kind) && <label>Notes<textarea maxLength={1000} value={values.notes ?? ''} onChange={(event) => setValues({ ...values, notes: event.target.value })} /></label>}
        {message && <p role="alert">{message}</p>}<button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : action?.kind === 'complete' && own ? 'Save my result' : 'Save record'}</button>
      </form>
    </FormDialog>
  </>
}

function PersonalCme({ authentication }) {
  const [state, setState] = useState({ status: 'loading' })
  useEffect(() => { let active = true; readSelfCme(authentication, Number(dubaiToday().slice(0, 4))).then((value) => { if (active) setState({ status: 'ready', value }) }).catch(() => { if (active) setState({ status: 'error' }) }); return () => { active = false } }, [authentication])
  return <section className="employee-panel"><h4>My CME summary</h4>{state.status === 'ready' ? <p>Target {state.value.targetHours} hours · Verified {state.value.achievedHours} hours · Remaining {state.value.gapHours} hours</p> : <p role={state.status === 'error' ? 'alert' : 'status'}>{state.status === 'error' ? 'CME summary is unavailable.' : 'Loading CME summary...'}</p>}</section>
}

export default function StaffDevelopment({ account, authentication }) {
  const [view, setView] = useState(account.role === 'manager' ? 'team' : 'my')
  const [employeeId, setEmployeeId] = useState('')
  const [names, setNames] = useState({})
  useEffect(() => { if (account.role !== 'manager') return undefined; let active = true; readDirectReports(authentication).then((result) => { if (active) setNames(Object.fromEntries(result.data.map((item) => [item.id, item.name]))) }).catch(() => { if (active) setNames({}) }); return () => { active = false } }, [account.role, authentication])
  return <section className="restored-module development-workspace">
    {account.role === 'manager' && <FilterTabs label="Training scope" value={view} onChange={(value) => { setView(value); setEmployeeId('') }} options={[{ value: 'team', label: 'Team Training' }, { value: 'my', label: 'My Training' }]} />}
    {view === 'team' && <EmployeePicker authentication={authentication} branchId={null} role="manager" value={employeeId} onChange={setEmployeeId} label="Team member" emptyLabel="All Reports" />}
    <StaffRecords key={`${view}:${employeeId}`} account={account} authentication={authentication} own={view === 'my'} names={names} employeeId={view === 'team' ? employeeId : null} />
    {view === 'my' && <PersonalCme authentication={authentication} />}
  </section>
}

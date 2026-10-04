import { useCallback, useEffect, useState } from 'react'
import { ConfirmDialog, FilterTabs, FormDialog, PortalTable, StatusPill, SummaryCards } from './PortalUi.jsx'
import EmployeePicker from './EmployeePicker.jsx'

import {
  appraisalCycleCommand,
  calibrateAppraisal,
  deleteAppraisalCycle,
  incidentCommand,
  rateAppraisalSection,
  readAppraisalCycles,
  readAppraisals,
  readIncidents,
  reviewAppraisal,
  saveAppraisalCycle,
  saveIncident,
} from './appraisalsIncidentsApi.js'

const emptyCycle = { name: '', reviewFrom: '', reviewTo: '' }
const emptyIncident = {
  incidentDate: new Date().toISOString().slice(0, 10), incidentTime: null, location: '',
  department: '', incidentType: 'other', severity: 'low', description: '',
  reportedById: null, involvedEmpId: null, immediateAction: '', notes: '',
}

function Message({ children }) {
  return children ? <p role="status" aria-live="polite">{children}</p> : null
}

function AppraisalRows({ appraisals, account, authentication, branchId, reload, run, readOnly = false }) {
  const [action, setAction] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [values, setValues] = useState({ rating: '3.0', comments: '', reviewerComments: '', developmentPlan: '' })
  const open = (kind, appraisal, section = null) => {
    setValues({ rating: section?.rating ?? appraisal.overallRating ?? '3.0', comments: section?.comments ?? '', reviewerComments: appraisal.reviewerComments ?? '', developmentPlan: appraisal.developmentPlan ?? '' })
    setAction({ kind, appraisal, section })
  }
  const selected = appraisals.find((item) => item.id === selectedId)
  if (appraisals.length === 0) return <div className="empty-state"><h3>No appraisals</h3><p>No appraisal results are available.</p></div>
  return <><PortalTable label="Appraisal reviews"><thead><tr><th>{account.role === 'employee' ? 'Cycle' : 'Employee'}</th><th>Review period</th><th>Overall rating</th><th>Status</th><th>Actions</th></tr></thead><tbody>{appraisals.map((appraisal) => <tr key={appraisal.id}><td><strong>{account.role === 'employee' ? appraisal.cycleName : appraisal.employeeName}</strong></td><td>{appraisal.reviewFrom} to {appraisal.reviewTo}</td><td>{appraisal.overallRating ? `${appraisal.overallRating} / 5.0` : 'Not rated'}</td><td><StatusPill value={appraisal.status} /></td><td><button type="button" className="btn btn-outline btn-sm" onClick={() => setSelectedId(appraisal.id)}>{account.role === 'employee' ? 'View' : appraisal.status === 'pending' ? 'Review' : 'View review'}</button></td></tr>)}</tbody></PortalTable>
    <FormDialog title={selected ? `Appraisal · ${selected.employeeName}` : 'Appraisal'} open={Boolean(selected)} wide onClose={() => setSelectedId(null)}>{selected && <div className="appraisal-detail">
    <p>{selected.cycleName} · {selected.reviewFrom} to {selected.reviewTo}</p><h4>Section results</h4><ul>{selected.sections.map((section) => <li key={section.id}>
      <span><strong>{section.sectionName}</strong><small>Weight {section.weight}%</small></span><span>{section.rating ?? 'Not rated'} / 5</span>{section.comments && <p>{section.comments}</p>}
      {!readOnly && account.role === 'manager' && selected.employeeId !== account.employeeId && selected.status === 'pending' && <button type="button" className="btn btn-outline btn-sm" onClick={() => open('rate', selected, section)}>Rate</button>}
    </li>)}</ul>
    <dl className="appraisal-summary"><div><dt>Reviewer comments</dt><dd>{selected.reviewerComments || 'None'}</dd></div><div><dt>Development plan</dt><dd>{selected.developmentPlan || 'None'}</dd></div><div><dt>Reviewed</dt><dd>{selected.reviewedAt ? new Date(selected.reviewedAt).toLocaleDateString() : 'Not reviewed'}</dd></div></dl>
    {!readOnly && account.role === 'admin' && selected.status === 'pending' && <button type="button" className="btn btn-primary" onClick={() => open('review', selected)}>Save review</button>}
    {!readOnly && account.role === 'admin' && selected.status === 'reviewed' && <button type="button" className="btn btn-outline" onClick={() => open('calibrate', selected)}>Calibrate</button>}
    </div>}</FormDialog><AppraisalAction action={action} values={values} setValues={setValues} onClose={() => setAction(null)} onSave={async () => {
    const saved = await run(() => action.kind === 'rate' ? rateAppraisalSection(authentication, action.appraisal, action.section, { rating: values.rating, comments: values.comments }) : action.kind === 'review' ? reviewAppraisal(authentication, branchId, action.appraisal, { reviewerComments: values.reviewerComments, developmentPlan: values.developmentPlan }) : calibrateAppraisal(authentication, branchId, action.appraisal, values.rating), action.kind === 'rate' ? 'Section rating saved.' : action.kind === 'review' ? 'Appraisal reviewed.' : 'Appraisal calibrated.')
    if (saved) { setAction(null); await reload().catch(() => {}) }
    return saved
  }} /></>
}

function AppraisalAction({ action, values, setValues, onClose, onSave }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  return <FormDialog title={action?.kind === 'rate' ? 'Rate section' : action?.kind === 'review' ? 'Review appraisal' : 'Calibrate appraisal'} open={Boolean(action)} onClose={() => { if (!saving) onClose() }}><form className="restoration-form" onSubmit={async (event) => { event.preventDefault(); setSaving(true); setError(''); try { if (!await onSave()) setError('The appraisal action could not be completed. Your entries have been kept.') } catch { setError('The appraisal could not be refreshed. Retry to see the latest result.') } finally { setSaving(false) } }}>
    <p>{action?.appraisal.employeeName}{action?.section ? ` · ${action.section.sectionName}` : ''}</p>
    {action?.kind !== 'review' && <fieldset className="rating-control"><legend>Rating</legend>{[1, 2, 3, 4, 5].map((rating) => <label key={rating}><input type="radio" name="section-rating" value={`${rating}.0`} checked={values.rating === `${rating}.0`} onChange={(event) => setValues({ ...values, rating: event.target.value })} /><span>{rating}</span></label>)}<label>Numeric rating<input type="number" min="1" max="5" step="0.1" required value={values.rating} onChange={(event) => setValues({ ...values, rating: event.target.value ? Number(event.target.value).toFixed(1) : '' })} /></label></fieldset>}
    {action?.kind === 'rate' && <label>Comments<textarea maxLength={10000} value={values.comments} onChange={(event) => setValues({ ...values, comments: event.target.value })} /></label>}
    {action?.kind === 'review' && <><label>Reviewer summary<textarea maxLength={10000} value={values.reviewerComments} onChange={(event) => setValues({ ...values, reviewerComments: event.target.value })} /></label><label>Development plan<textarea maxLength={10000} value={values.developmentPlan} onChange={(event) => setValues({ ...values, developmentPlan: event.target.value })} /></label></>}
    <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save review'}</button><Message>{error}</Message>
  </form></FormDialog>
}

function Appraisals({ account, authentication, branchId }) {
  const [cycles, setCycles] = useState([])
  const [appraisals, setAppraisals] = useState([])
  const [cycleForm, setCycleForm] = useState(emptyCycle)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [showCycleForm, setShowCycleForm] = useState(false)
  const [selectedCycleId, setSelectedCycleId] = useState(null)
  const [confirmAction, setConfirmAction] = useState(null)
  const [tab, setTab] = useState('cycles')
  const [loadState, setLoadState] = useState('loading')

  const load = useCallback(async () => {
    setLoadState('loading')
    try {
    if (account.role === 'admin') {
      setCycles(await readAppraisalCycles(authentication, branchId))
      setLoadState('ready')
      return
    }
    const own = await readAppraisals(authentication, 'employee')
    if (account.role === 'manager') {
      const reports = await readAppraisals(authentication, 'manager')
      setAppraisals([...reports, ...own])
    } else setAppraisals(own)
    setLoadState('ready')
    } catch (error) { setLoadState('error'); throw error }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    let current = true
    const pending = globalThis.setTimeout(() => {
      load().catch(() => { if (current) setMessage('Appraisals are unavailable.') })
    }, 0)
    return () => { current = false; globalThis.clearTimeout(pending) }
  }, [load])

  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action(); setMessage(success); return true }
    catch { setMessage('The appraisal action could not be completed.'); return false }
    finally { setBusy(false) }
  }

  if (account.role !== 'admin') return <section aria-labelledby="appraisals-title">
    <h3 id="appraisals-title">Appraisals</h3><Message>{message}</Message>
    {loadState === 'loading' ? <p role="status">Loading appraisals...</p> : loadState === 'error' ? <button type="button" className="btn btn-outline" onClick={() => load().catch(() => setMessage('Appraisals are unavailable.'))}>Retry</button> : <AppraisalRows appraisals={appraisals} account={account} authentication={authentication} branchId={branchId} reload={load} run={run} />}
  </section>

  const submitCycle = async (event) => {
    event.preventDefault()
    await run(async () => {
      await saveAppraisalCycle(authentication, branchId, cycleForm, editing)
      setCycleForm(emptyCycle); setEditing(null); await load()
      setShowCycleForm(false)
    }, editing === null ? 'Appraisal cycle created.' : 'Appraisal cycle updated.')
  }

  const selectedCycle = cycles.find((cycle) => cycle.id === selectedCycleId)
  const cycleReviews = selectedCycle?.appraisals ?? []
  const reviewed = cycleReviews.filter((item) => item.status !== 'pending')
  const average = reviewed.length ? (reviewed.reduce((sum, item) => sum + Number(item.overallRating), 0) / reviewed.length).toFixed(1) : 'Not rated'
  const command = async (cycle, kind, success) => {
    if (await run(() => appraisalCycleCommand(authentication, branchId, cycle, kind), success)) await load().catch(() => setMessage('The action was saved. Reload to see the updated cycle.'))
  }
  return <section className="restored-module" aria-labelledby="appraisals-title">
    <header className="restored-module-header"><h3 id="appraisals-title">Appraisal cycles</h3><div className="module-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => load().catch(() => setMessage('Appraisals are unavailable.'))}>Reload</button><button type="button" className="btn btn-primary" disabled={busy} onClick={() => { setEditing(null); setCycleForm(emptyCycle); setShowCycleForm(true) }}>New Cycle</button></div></header><Message>{message}</Message>
    <FilterTabs label="Appraisal views" options={[{ value: 'cycles', label: 'Cycles' }, { value: 'reviews', label: 'Reviews' }]} value={tab} onChange={setTab} />
    {loadState === 'loading' && <p role="status">Loading appraisal cycles...</p>}
    {loadState === 'error' && <div className="alert alert-danger" role="alert">Appraisal cycles are unavailable. Reload to try again.</div>}
    <FormDialog title={editing ? 'Edit appraisal cycle' : 'New appraisal cycle'} open={showCycleForm} onClose={() => { if (!busy) setShowCycleForm(false) }}>
    <form className="expense-form restoration-form" onSubmit={submitCycle}>
      <label>Name<input required maxLength="180" value={cycleForm.name} onChange={(event) => setCycleForm({ ...cycleForm, name: event.target.value })} /></label>
      <label>Review from<input required type="date" value={cycleForm.reviewFrom} onChange={(event) => setCycleForm({ ...cycleForm, reviewFrom: event.target.value })} /></label>
      <label>Review to<input required type="date" value={cycleForm.reviewTo} onChange={(event) => setCycleForm({ ...cycleForm, reviewTo: event.target.value })} /></label>
      <button type="submit" disabled={busy}>{editing === null ? 'Create cycle' : 'Save cycle'}</button>
    </form>
    </FormDialog>
    {tab === 'cycles' && <PortalTable label="Appraisal cycles"><thead><tr><th>Cycle name</th><th>Review period</th><th>Status</th><th>Actions</th></tr></thead><tbody>{cycles.map((cycle) => <tr key={cycle.id}><td><strong>{cycle.name}</strong></td><td>{cycle.reviewFrom} to {cycle.reviewTo}</td><td><StatusPill value={cycle.status} /></td><td><div className="module-actions"><button type="button" className="btn btn-outline btn-sm" onClick={() => { setSelectedCycleId(cycle.id); setTab('reviews') }}>Reviews</button>{cycle.status === 'draft' && <><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setEditing(cycle); setCycleForm({ name: cycle.name, reviewFrom: cycle.reviewFrom, reviewTo: cycle.reviewTo }); setShowCycleForm(true) }}>Edit</button><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => command(cycle, 'activate', 'Appraisal cycle activated.')}>Activate</button>{!cycle.appraisals.length && <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => setConfirmAction({ cycle, kind: 'remove' })}>Remove</button>}</>}</div></td></tr>)}{loadState === 'ready' && cycles.length === 0 && <tr><td colSpan={4}><div className="empty-state">No appraisal cycles yet. Create a cycle to start reviews.</div></td></tr>}</tbody></PortalTable>}
    {tab === 'reviews' && <>
      <div className="restored-toolbar"><label>Cycle<select value={selectedCycleId ?? ''} onChange={(event) => setSelectedCycleId(event.target.value || null)}><option value="">Select cycle</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name} · {cycle.status}</option>)}</select></label>{selectedCycle && <StatusPill value={selectedCycle.status} />}{selectedCycle?.status === 'active' && <div className="module-actions"><button type="button" className="btn btn-primary" disabled={busy} onClick={() => command(selectedCycle, 'generate', 'Missing appraisals generated.')}>Generate Appraisals</button><button type="button" className="btn btn-outline" disabled={busy} onClick={() => setConfirmAction({ cycle: selectedCycle, kind: 'close' })}>Close cycle</button></div>}</div>
      {selectedCycle ? <>
        <SummaryCards items={[{ label: 'Total', value: cycleReviews.length }, { label: 'Reviewed', value: reviewed.length }, { label: 'Pending', value: cycleReviews.length - reviewed.length }, { label: 'Average rating', value: average }]} />
        <AppraisalRows appraisals={cycleReviews} account={account} authentication={authentication} branchId={branchId} reload={load} run={run} readOnly={selectedCycle.status === 'closed'} />
      </> : <div className="empty-state">Select a cycle to view its reviews.</div>}
    </>}
    <ConfirmDialog title={confirmAction?.kind === 'close' ? 'Close cycle' : 'Remove cycle'} open={Boolean(confirmAction)} busy={busy} onClose={() => setConfirmAction(null)} confirmLabel={confirmAction?.kind === 'close' ? 'Close cycle' : 'Remove cycle'} onConfirm={async () => { const saved = await run(() => confirmAction.kind === 'close' ? appraisalCycleCommand(authentication, branchId, confirmAction.cycle, 'close') : deleteAppraisalCycle(authentication, branchId, confirmAction.cycle), confirmAction.kind === 'close' ? 'Appraisal cycle closed.' : 'Appraisal cycle removed.'); if (saved) { setConfirmAction(null); await load() } }}>Confirm this cycle action? Closing locks the completed review.</ConfirmDialog>
  </section>
}

function Incidents({ authentication, branchId }) {
  const [incidents, setIncidents] = useState([])
  const [form, setForm] = useState(emptyIncident)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [filter, setFilter] = useState('all')
  const [action, setAction] = useState(null)
  const [actionText, setActionText] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [loadState, setLoadState] = useState('loading')
  const load = useCallback(async () => {
    setLoadState('loading')
    try { setIncidents(await readIncidents(authentication, branchId)); setLoadState('ready') }
    catch (error) { setLoadState('error'); throw error }
  }, [authentication, branchId])
  useEffect(() => {
    const pending = globalThis.setTimeout(() => {
      load().catch(() => setMessage('Clinical incidents are unavailable.'))
    }, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])
  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action() }
    catch { setMessage('The clinical incident action could not be completed.'); setBusy(false); return false }
    try { await load(); setMessage(success); return true }
    catch { setMessage(`${success} Reload to see the latest reports.`); return true }
    finally { setBusy(false) }
  }
  const submit = (event) => {
    event.preventDefault()
    run(async () => {
      await saveIncident(authentication, branchId, form, editing)
      setForm(emptyIncident); setEditing(null)
      setShowForm(false)
    }, editing === null ? 'Clinical incident created.' : 'Clinical incident updated.')
  }
  const types = ['patient_safety', 'medication_error', 'injury', 'needlestick', 'infection', 'equipment', 'near_miss', 'workplace', 'other']
  const severity = ['low', 'moderate', 'high', 'critical']
  const filtered = incidents.filter((item) => (filter === 'all' || item.status === filter) && (severityFilter === 'all' || item.severity === severityFilter) && (typeFilter === 'all' || item.incidentType === typeFilter))
  const critical = incidents.filter((item) => ['critical', 'high'].includes(item.severity) && item.status !== 'closed').length
  return <section className="restored-module" aria-labelledby="incidents-title"><header className="restored-module-header"><div><h3 id="incidents-title">Incidents</h3><p>Record events, investigate causes, and track corrective action.</p></div><div className="module-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => load().catch(() => setMessage('Incidents are unavailable.'))}>Reload</button><button type="button" className="btn btn-primary" disabled={busy} onClick={() => { setEditing(null); setForm(emptyIncident); setShowForm(true) }}>Add Incident</button></div></header><Message>{message}</Message>
    <SummaryCards items={[{ label: 'Total reports', value: incidents.length }, { label: 'Open', value: incidents.filter((item) => item.status === 'open').length }, { label: 'Critical / high open', value: critical }, { label: 'This month', value: incidents.filter((item) => item.incidentDate.startsWith(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }).slice(0, 7))).length }].map((item) => ({ ...item, value: loadState === 'ready' ? item.value : 'Not available' }))} />
    {loadState === 'ready' && critical > 0 && <div className="alert alert-warning">{critical} critical or high-severity reports still need investigation or closure.</div>}
    <FilterTabs label="Incident status" options={['all', 'open', 'investigating', 'closed'].map((value) => ({ value, label: value, count: value === 'all' ? incidents.length : incidents.filter((item) => item.status === value).length }))} value={filter} onChange={setFilter} />
    <div className="restored-toolbar"><label>Severity<select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="all">All severities</option>{severity.map((value) => <option key={value}>{value}</option>)}</select></label><label>Incident type<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All types</option>{types.map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label></div>
    {loadState === 'loading' && <p role="status">Loading incident reports...</p>}{loadState === 'error' && <div className="alert alert-danger" role="alert">Incident reports are unavailable. Reload to try again.</div>}
    <FormDialog title={editing ? 'Edit incident' : 'Add incident'} open={showForm} wide onClose={() => { if (!busy) setShowForm(false) }}>
    <form className="expense-form restoration-form" onSubmit={submit}>
      <h4 className="form-section-title">Event facts</h4>
      <label>Date<input required type="date" value={form.incidentDate} onChange={(event) => setForm({ ...form, incidentDate: event.target.value })} /></label>
      <label>Time<input type="time" value={form.incidentTime?.slice(0, 5) ?? ''} onChange={(event) => setForm({ ...form, incidentTime: event.target.value || null })} /></label>
      <label>Type<select value={form.incidentType} onChange={(event) => setForm({ ...form, incidentType: event.target.value })}>
        {['patient_safety', 'medication_error', 'injury', 'needlestick', 'infection', 'equipment', 'near_miss', 'workplace', 'other'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
      </select></label>
      <label>Severity<select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
        {['low', 'moderate', 'high', 'critical'].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Location<input maxLength="180" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} /></label>
      <label>Department<input maxLength="180" value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })} /></label>
      <EmployeePicker authentication={authentication} branchId={branchId} value={form.reportedById ?? ''} onChange={(value) => setForm({ ...form, reportedById: value || null })} label="Reported by" emptyLabel="Not specified" />
      <EmployeePicker authentication={authentication} branchId={branchId} value={form.involvedEmpId ?? ''} onChange={(value) => setForm({ ...form, involvedEmpId: value || null })} label="Involved employee" emptyLabel="Not specified" />
      <label>Description<textarea required maxLength="10000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <h4 className="form-section-title">Immediate action and notes</h4>
      <label>Immediate action<textarea maxLength="10000" value={form.immediateAction} onChange={(event) => setForm({ ...form, immediateAction: event.target.value })} /></label>
      <label>Notes<textarea maxLength="10000" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      <button type="submit" disabled={busy}>{editing === null ? 'Record incident' : 'Save incident'}</button>
      <Message>{message}</Message>
    </form>
    </FormDialog>
    <PortalTable label="Incidents" className="expense-table"><thead><tr><th>Date</th><th>Type</th><th>Severity</th><th>Department</th><th>Location</th><th>Description</th><th>Reported by</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{filtered.map((incident) => <tr key={incident.id}><td>{incident.incidentDate}<small>{incident.incidentTime?.slice(0, 5)}</small></td>
        <td>{incident.incidentType.replaceAll('_', ' ')}</td><td><StatusPill value={incident.severity} /></td><td>{incident.department || 'Not recorded'}</td><td>{incident.location || 'Not recorded'}</td>
        <td><details><summary>{incident.description}</summary><dl><dt>Immediate action</dt><dd>{incident.immediateAction || 'Not recorded'}</dd><dt>Involved employee</dt><dd>{incident.involvedEmployeeName || 'Not specified'}</dd><dt>Root cause</dt><dd>{incident.rootCause || 'Not recorded'}</dd><dt>Corrective action</dt><dd>{incident.correctiveAction || 'Not recorded'}</dd><dt>Closed date</dt><dd>{incident.closedDate || 'Not closed'}</dd><dt>Notes</dt><dd>{incident.notes || 'None'}</dd></dl></details></td><td>{incident.reportedByName || 'Not specified'}</td><td><StatusPill value={incident.status} /></td><td><div className="module-actions">
          {incident.status === 'open' && <><button type="button" disabled={busy} onClick={() => {
            setEditing(incident); setForm({
              incidentDate: incident.incidentDate, incidentTime: incident.incidentTime,
              location: incident.location, department: incident.department,
              incidentType: incident.incidentType, severity: incident.severity,
              description: incident.description, reportedById: incident.reportedById,
              involvedEmpId: incident.involvedEmpId, immediateAction: incident.immediateAction,
              notes: incident.notes,
            })
            setShowForm(true)
          }}>Edit</button><button type="button" disabled={busy} onClick={() => {
            setActionText(''); setAction({ incident, kind: 'investigate' })
          }}>Investigate</button></>}
          {incident.status === 'investigating' && <><button type="button" disabled={busy} onClick={() => {
            setActionText(''); setAction({ incident, kind: 'corrective-action' })
          }}>Corrective action</button><button type="button" disabled={busy} onClick={() => { setActionText(''); setAction({ incident, kind: 'close' }) }}>Close</button></>}
        </div></td></tr>)}{loadState === 'ready' && filtered.length === 0 && <tr><td colSpan={9}><div className="empty-state">No incidents match these filters.</div></td></tr>}</tbody></PortalTable>
    <FormDialog title={action?.kind === 'investigate' ? 'Investigate incident' : action?.kind === 'corrective-action' ? 'Corrective action' : 'Close incident'} open={Boolean(action)} onClose={() => { if (!busy) setAction(null) }}><form className="restoration-form" onSubmit={async (event) => { event.preventDefault(); const payload = action.kind === 'investigate' ? { rootCause: actionText.trim() } : action.kind === 'corrective-action' ? { correctiveAction: actionText.trim() } : {}; if (await run(() => incidentCommand(authentication, branchId, action.incident, action.kind, payload), action.kind === 'close' ? 'Incident closed.' : 'Incident action saved.')) setAction(null) }}>{action?.kind === 'close' ? <p>Close this incident? The server records the closure date and locks the incident.</p> : <label>{action?.kind === 'investigate' ? 'Root cause' : 'Corrective action'}<textarea required maxLength={10000} value={actionText} onChange={(event) => setActionText(event.target.value)} /></label>}<button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : 'Confirm action'}</button><Message>{message}</Message></form></FormDialog>
  </section>
}

export default function AppraisalsIncidents({ account, authentication, branchId, view = 'all' }) {
  const showAppraisals = view !== 'incidents'
  const showIncidents = account.role === 'admin' && view !== 'appraisals'
  const title = showAppraisals && showIncidents
    ? 'Appraisals and clinical incidents'
    : showIncidents ? 'Incidents' : 'Appraisals'
  return <section className="records-benefits restoration-group" aria-labelledby="appraisals-incidents-title">
    <h2 id="appraisals-incidents-title" className="sr-only">{title}</h2>
    {showAppraisals && <Appraisals account={account} authentication={authentication} branchId={branchId} />}
    {showIncidents && <Incidents authentication={authentication} branchId={branchId} />}
  </section>
}

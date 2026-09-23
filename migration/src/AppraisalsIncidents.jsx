import { useCallback, useEffect, useState } from 'react'

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

function AppraisalRows({ appraisals, account, authentication, branchId, reload, run }) {
  return <div className="records-benefits-grid">{appraisals.map((appraisal) => <article key={appraisal.id}>
    <h4>{appraisal.employeeName}</h4>
    <p>{appraisal.cycleName} · {appraisal.status.replaceAll('_', ' ')} · Rating {appraisal.overallRating ?? 'pending'}</p>
    <ul>{appraisal.sections.map((section) => <li key={section.id}>
      {section.sectionName}: {section.rating ?? 'not rated'}
      {account.role === 'manager' && appraisal.status === 'pending' && <button type="button" onClick={() => {
        const value = globalThis.prompt(`Rating for ${section.sectionName} (1.0 to 5.0)`)?.trim()
        if (value) run(() => rateAppraisalSection(authentication, appraisal, section, {
          rating: value, comments: '',
        }), 'Section rating saved.').then(reload)
      }}>Rate</button>}
    </li>)}</ul>
    {account.role === 'admin' && appraisal.status === 'pending' && <button type="button" onClick={() => run(
      () => reviewAppraisal(authentication, branchId, appraisal, {
        reviewerComments: globalThis.prompt('Reviewer comments')?.trim() ?? '',
        developmentPlan: globalThis.prompt('Development plan')?.trim() ?? '',
      }), 'Appraisal reviewed.',
    ).then(reload)}>Review</button>}
    {account.role === 'admin' && appraisal.status === 'reviewed' && <button type="button" onClick={() => {
      const value = globalThis.prompt('Final calibrated rating (1.0 to 5.0)', appraisal.overallRating)?.trim()
      if (value) run(() => calibrateAppraisal(authentication, branchId, appraisal, value), 'Appraisal calibrated.').then(reload)
    }}>Calibrate</button>}
  </article>)}</div>
}

function Appraisals({ account, authentication, branchId }) {
  const [cycles, setCycles] = useState([])
  const [appraisals, setAppraisals] = useState([])
  const [cycleForm, setCycleForm] = useState(emptyCycle)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (account.role === 'admin') {
      setCycles(await readAppraisalCycles(authentication, branchId))
      return
    }
    const own = await readAppraisals(authentication, 'employee')
    if (account.role === 'manager') {
      const reports = await readAppraisals(authentication, 'manager')
      setAppraisals([...reports, ...own])
    } else setAppraisals(own)
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
    try { await action(); setMessage(success) }
    catch { setMessage('The appraisal action could not be completed.') }
    finally { setBusy(false) }
  }

  if (account.role !== 'admin') return <section aria-labelledby="appraisals-title">
    <h3 id="appraisals-title">Appraisals</h3><Message>{message}</Message>
    <AppraisalRows appraisals={appraisals} account={account} authentication={authentication} branchId={branchId} reload={load} run={run} />
  </section>

  const submitCycle = async (event) => {
    event.preventDefault()
    await run(async () => {
      await saveAppraisalCycle(authentication, branchId, cycleForm, editing)
      setCycleForm(emptyCycle); setEditing(null); await load()
    }, editing === null ? 'Appraisal cycle created.' : 'Appraisal cycle updated.')
  }

  return <section aria-labelledby="appraisals-title">
    <h3 id="appraisals-title">Appraisal cycles</h3><Message>{message}</Message>
    <form className="expense-form" onSubmit={submitCycle}>
      <label>Name<input required maxLength="180" value={cycleForm.name} onChange={(event) => setCycleForm({ ...cycleForm, name: event.target.value })} /></label>
      <label>Review from<input required type="date" value={cycleForm.reviewFrom} onChange={(event) => setCycleForm({ ...cycleForm, reviewFrom: event.target.value })} /></label>
      <label>Review to<input required type="date" value={cycleForm.reviewTo} onChange={(event) => setCycleForm({ ...cycleForm, reviewTo: event.target.value })} /></label>
      <button type="submit" disabled={busy}>{editing === null ? 'Create cycle' : 'Save cycle'}</button>
    </form>
    {cycles.map((cycle) => <article key={cycle.id}>
      <h4>{cycle.name}</h4><p>{cycle.reviewFrom} to {cycle.reviewTo} · {cycle.status}</p>
      {cycle.status === 'draft' && <>
        <button type="button" disabled={busy} onClick={() => {
          setEditing(cycle); setCycleForm({ name: cycle.name, reviewFrom: cycle.reviewFrom, reviewTo: cycle.reviewTo })
        }}>Edit</button>
        <button type="button" disabled={busy} onClick={() => run(
          () => appraisalCycleCommand(authentication, branchId, cycle, 'activate'),
          'Appraisal cycle activated.',
        ).then(load)}>Activate</button>
        {!cycle.appraisals.length && <button type="button" className="danger" disabled={busy} onClick={() => run(
          () => deleteAppraisalCycle(authentication, branchId, cycle), 'Appraisal cycle removed.',
        ).then(load)}>Remove</button>}
      </>}
      {cycle.status === 'active' && <>
        <button type="button" disabled={busy} onClick={() => run(
          () => appraisalCycleCommand(authentication, branchId, cycle, 'generate'),
          'Missing appraisals generated.',
        ).then(load)}>Generate missing appraisals</button>
        <button type="button" disabled={busy} onClick={() => run(
          () => appraisalCycleCommand(authentication, branchId, cycle, 'close'),
          'Appraisal cycle closed.',
        ).then(load)}>Close cycle</button>
      </>}
      <AppraisalRows appraisals={cycle.appraisals} account={account} authentication={authentication} branchId={branchId} reload={load} run={run} />
    </article>)}
  </section>
}

function Incidents({ authentication, branchId }) {
  const [incidents, setIncidents] = useState([])
  const [form, setForm] = useState(emptyIncident)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => readIncidents(authentication, branchId).then(setIncidents), [authentication, branchId])
  useEffect(() => {
    const pending = globalThis.setTimeout(() => {
      load().catch(() => setMessage('Clinical incidents are unavailable.'))
    }, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])
  const run = async (action, success) => {
    setBusy(true); setMessage('')
    try { await action(); setMessage(success); await load() }
    catch { setMessage('The clinical incident action could not be completed.') }
    finally { setBusy(false) }
  }
  const submit = (event) => {
    event.preventDefault()
    run(async () => {
      await saveIncident(authentication, branchId, form, editing)
      setForm(emptyIncident); setEditing(null)
    }, editing === null ? 'Clinical incident created.' : 'Clinical incident updated.')
  }
  return <section aria-labelledby="incidents-title"><h3 id="incidents-title">Clinical incidents</h3><Message>{message}</Message>
    <form className="expense-form" onSubmit={submit}>
      <label>Date<input required type="date" value={form.incidentDate} onChange={(event) => setForm({ ...form, incidentDate: event.target.value })} /></label>
      <label>Type<select value={form.incidentType} onChange={(event) => setForm({ ...form, incidentType: event.target.value })}>
        {['patient_safety', 'medication_error', 'injury', 'needlestick', 'infection', 'equipment', 'near_miss', 'workplace', 'other'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
      </select></label>
      <label>Severity<select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
        {['low', 'moderate', 'high', 'critical'].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Location<input maxLength="180" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} /></label>
      <label>Department<input maxLength="180" value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })} /></label>
      <label>Description<textarea required maxLength="10000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      <label>Immediate action<textarea maxLength="10000" value={form.immediateAction} onChange={(event) => setForm({ ...form, immediateAction: event.target.value })} /></label>
      <button type="submit" disabled={busy}>{editing === null ? 'Record incident' : 'Save incident'}</button>
    </form>
    <table className="expense-table"><thead><tr><th>Date</th><th>Incident</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{incidents.map((incident) => <tr key={incident.id}><td>{incident.incidentDate}</td>
        <td>{incident.incidentType.replaceAll('_', ' ')} · {incident.severity}<small>{incident.location}</small></td>
        <td>{incident.status}</td><td>
          {incident.status === 'open' && <><button type="button" disabled={busy} onClick={() => {
            setEditing(incident); setForm({
              incidentDate: incident.incidentDate, incidentTime: incident.incidentTime,
              location: incident.location, department: incident.department,
              incidentType: incident.incidentType, severity: incident.severity,
              description: incident.description, reportedById: incident.reportedById,
              involvedEmpId: incident.involvedEmpId, immediateAction: incident.immediateAction,
              notes: incident.notes,
            })
          }}>Edit</button><button type="button" disabled={busy} onClick={() => {
            const rootCause = globalThis.prompt('Root cause')?.trim()
            if (rootCause) run(() => incidentCommand(authentication, branchId, incident, 'investigate', { rootCause }), 'Investigation started.')
          }}>Investigate</button></>}
          {incident.status === 'investigating' && <><button type="button" disabled={busy} onClick={() => {
            const correctiveAction = globalThis.prompt('Corrective action')?.trim()
            if (correctiveAction) run(() => incidentCommand(authentication, branchId, incident, 'corrective-action', { correctiveAction }), 'Corrective action recorded.')
          }}>Corrective action</button><button type="button" disabled={busy} onClick={() => run(
            () => incidentCommand(authentication, branchId, incident, 'close'), 'Clinical incident closed.',
          )}>Close</button></>}
        </td></tr>)}</tbody></table>
  </section>
}

export default function AppraisalsIncidents({ account, authentication, branchId }) {
  return <section className="records-benefits" aria-labelledby="appraisals-incidents-title">
    <h2 id="appraisals-incidents-title">Appraisals and clinical incidents</h2>
    <Appraisals account={account} authentication={authentication} branchId={branchId} />
    {account.role === 'admin' && <Incidents authentication={authentication} branchId={branchId} />}
  </section>
}

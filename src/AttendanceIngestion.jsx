import { useEffect, useState } from 'react'

import { readAllEmployees } from './employeeApi.js'
import { HttpClientError } from './http.js'
import { parseAttendanceCsv } from './attendanceCsv.js'
import {
  createManualClockEvent,
  deleteBiometricMapping,
  importBiometricCandidates,
  readBiometricMappings,
  readClockEvents,
  replaceBiometricMapping,
} from './attendanceIngestionApi.js'

function messageFor(error) {
  if (!(error instanceof HttpClientError)) return error instanceof Error ? error.message : 'The request failed.'
  if (error.code === 'idempotency_conflict') return 'This command key was already used with different data.'
  if (error.code === 'resource_not_found') return 'The selected employee or mapping is unavailable in this branch.'
  return error.message
}

function dubaiInstant(value) {
  return `${value}${value.length === 16 ? ':00' : ''}+04:00`
}

export default function AttendanceIngestion({ authentication, branchId }) {
  const [events, setEvents] = useState([])
  const [mappings, setMappings] = useState([])
  const [employees, setEmployees] = useState([])
  const [manual, setManual] = useState({ employeeId: '', eventType: 'CLOCK_IN', eventTime: '', note: '' })
  const [mapping, setMapping] = useState({ badgeNo: '', employeeId: '', deviceName: 'Default' })
  const [batch, setBatch] = useState(null)
  const [result, setResult] = useState(null)
  const [message, setMessage] = useState('')

  const load = async (signal) => Promise.all([
      readClockEvents(authentication, branchId, { limit: 100, signal }),
      readBiometricMappings(authentication, branchId, { signal }),
      readAllEmployees(authentication, branchId, { signal }),
    ])

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readClockEvents(authentication, branchId, { limit: 100, signal: controller.signal }),
      readBiometricMappings(authentication, branchId, { signal: controller.signal }),
      readAllEmployees(authentication, branchId, { signal: controller.signal }),
    ])
      .then(([nextEvents, nextMappings, nextEmployees]) => {
        if (controller.signal.aborted) return
        setEvents(nextEvents.data); setMappings(nextMappings.data); setEmployees(nextEmployees)
      })
      .catch((error) => {
        if (!controller.signal.aborted) setMessage(messageFor(error))
      })
    return () => controller.abort()
  }, [authentication, branchId])

  const submitManual = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const saved = await createManualClockEvent(authentication, branchId, { ...manual, eventTime: dubaiInstant(manual.eventTime) }, { idempotencyKey: crypto.randomUUID() })
      setEvents((rows) => [saved, ...rows]); setMessage('Manual clock event recorded.')
    } catch (error) { setMessage(messageFor(error)) }
  }
  const submitMapping = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const saved = await replaceBiometricMapping(authentication, branchId, mapping.badgeNo, mapping, { idempotencyKey: crypto.randomUUID() })
      setMappings((rows) => [...rows.filter((row) => row.badgeNo !== saved.badgeNo), saved].sort((a, b) => a.badgeNo.localeCompare(b.badgeNo)))
      setMessage('Biometric mapping saved.')
    } catch (error) { setMessage(messageFor(error)) }
  }
  const removeMapping = async (badgeNo) => {
    try {
      await deleteBiometricMapping(authentication, branchId, badgeNo, { idempotencyKey: crypto.randomUUID() })
      setMappings((rows) => rows.filter((row) => row.badgeNo !== badgeNo)); setMessage('Biometric mapping deleted.')
    } catch (error) { setMessage(messageFor(error)) }
  }
  const selectCsv = async (event) => {
    setResult(null); setMessage('')
    const file = event.target.files?.[0]
    if (!file) return
    try { setBatch(parseAttendanceCsv(await file.text())) }
    catch (error) { setBatch(null); setMessage(messageFor(error)) }
  }
  const submitImport = async () => {
    try {
      const imported = await importBiometricCandidates(authentication, branchId, batch, { idempotencyKey: crypto.randomUUID() })
      setResult(imported); setMessage('Biometric import completed.')
      const [nextEvents, nextMappings, nextEmployees] = await load()
      setEvents(nextEvents.data); setMappings(nextMappings.data); setEmployees(nextEmployees)
    } catch (error) { setMessage(messageFor(error)) }
  }

  return (
    <section className="attendance-ingestion" aria-labelledby="attendance-ingestion-title">
      <h2 id="attendance-ingestion-title">Attendance ingestion</h2>
      <form className="settings-form" onSubmit={submitManual}>
        <h3>Manual clock event</h3>
        <label>Employee<select required value={manual.employeeId} onChange={(event) => setManual({ ...manual, employeeId: event.target.value })}><option value="">Select employee</option>{employees.filter((employee) => employee.active).map((employee) => <option key={employee.id} value={employee.id}>{employee.employeeNo} — {employee.name}</option>)}</select></label>
        <label>Event<select value={manual.eventType} onChange={(event) => setManual({ ...manual, eventType: event.target.value })}><option value="CLOCK_IN">Clock in</option><option value="CLOCK_OUT">Clock out</option></select></label>
        <label>Dubai time<input type="datetime-local" required value={manual.eventTime} onChange={(event) => setManual({ ...manual, eventTime: event.target.value })} /></label>
        <label>Reason<input required maxLength="500" value={manual.note} onChange={(event) => setManual({ ...manual, note: event.target.value })} /></label>
        <button type="submit">Record event</button>
      </form>

      <form className="settings-form" onSubmit={submitMapping}>
        <h3>Biometric mapping</h3>
        <label>Badge number<input required maxLength="120" value={mapping.badgeNo} onChange={(event) => setMapping({ ...mapping, badgeNo: event.target.value })} /></label>
        <label>Employee<select required value={mapping.employeeId} onChange={(event) => setMapping({ ...mapping, employeeId: event.target.value })}><option value="">Select employee</option>{employees.filter((employee) => employee.active).map((employee) => <option key={employee.id} value={employee.id}>{employee.employeeNo} — {employee.name}</option>)}</select></label>
        <label>Device<input required maxLength="120" value={mapping.deviceName} onChange={(event) => setMapping({ ...mapping, deviceName: event.target.value })} /></label>
        <button type="submit">Save mapping</button>
      </form>
      <ul>{mappings.map((row) => <li key={row.id}>{row.badgeNo} — {row.deviceName}<button type="button" className="danger" onClick={() => removeMapping(row.badgeNo)}>Delete</button></li>)}</ul>

      <div className="settings-form">
        <h3>Biometric CSV import</h3>
        <p>Upload normalized columns badgeNo,eventType,eventTime and optional deviceName.</p>
        <input type="file" accept=".csv,text/csv" onChange={selectCsv} />
        {batch && <><p>{batch.candidates.length} rows ready; showing up to 100.</p><ol>{batch.preview.map((row, index) => <li key={`${row.badgeNo}-${row.eventTime}-${index}`}>{row.badgeNo} — {row.eventType} — {row.eventTime}</li>)}</ol><button type="button" onClick={submitImport}>Import punches</button></>}
        {result && <p>{result.acceptedCount} accepted, {result.duplicateCount} duplicates, {result.rejectedCount} rejected.</p>}
      </div>

      <h3>Recent raw events</h3>
      <ul>{events.map((row) => <li key={row.id}>{row.eventTime} — {row.eventType} — {row.method}</li>)}</ul>
      {message && <p role="status">{message}</p>}
    </section>
  )
}

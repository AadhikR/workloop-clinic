import { useEffect, useState } from 'react'

import { readAllEmployees } from './employeeApi.js'
import { HttpClientError } from './http.js'
import { createManualClockEvent, readClockEvents } from './attendanceIngestionApi.js'

function messageFor(error) {
  if (!(error instanceof HttpClientError)) return error instanceof Error ? error.message : 'The request failed.'
  if (error.code === 'idempotency_conflict') return 'This command key was already used with different data.'
  if (error.code === 'resource_not_found') return 'The selected employee is unavailable in this branch.'
  return error.message
}

function dubaiInstant(value) {
  return `${value}${value.length === 16 ? ':00' : ''}+04:00`
}

export default function AttendanceIngestion({ authentication, branchId }) {
  const [events, setEvents] = useState([])
  const [employees, setEmployees] = useState([])
  const [manual, setManual] = useState({ employeeId: '', eventType: 'CLOCK_IN', eventTime: '', note: '' })
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readClockEvents(authentication, branchId, { limit: 100, signal: controller.signal }),
      readAllEmployees(authentication, branchId, { signal: controller.signal }),
    ])
      .then(([nextEvents, nextEmployees]) => {
        if (controller.signal.aborted) return
        setEvents(nextEvents.data)
        setEmployees(nextEmployees)
      })
      .catch((error) => {
        if (!controller.signal.aborted) setMessage(messageFor(error))
      })
    return () => controller.abort()
  }, [authentication, branchId])

  const submitManual = async (event) => {
    event.preventDefault()
    setMessage('')
    try {
      const saved = await createManualClockEvent(authentication, branchId, {
        ...manual,
        eventTime: dubaiInstant(manual.eventTime),
      }, { idempotencyKey: crypto.randomUUID() })
      setEvents((rows) => [saved, ...rows])
      setManual({ employeeId: '', eventType: 'CLOCK_IN', eventTime: '', note: '' })
      setMessage('Manual clock event recorded.')
    } catch (error) {
      setMessage(messageFor(error))
    }
  }

  return (
    <section className="attendance-ingestion" aria-labelledby="attendance-ingestion-title">
      <h2 id="attendance-ingestion-title">Manual attendance entry</h2>
      <p>Record a selected employee&apos;s clock event with an audit reason. Device integration is not available in this workspace.</p>
      <form className="settings-form" onSubmit={submitManual}>
        <label>Employee<select required value={manual.employeeId} onChange={(event) => setManual({ ...manual, employeeId: event.target.value })}><option value="">Select employee</option>{employees.filter((employee) => employee.active).map((employee) => <option key={employee.id} value={employee.id}>{employee.empNo} — {employee.name}</option>)}</select></label>
        <label>Event<select value={manual.eventType} onChange={(event) => setManual({ ...manual, eventType: event.target.value })}><option value="CLOCK_IN">Clock in</option><option value="CLOCK_OUT">Clock out</option></select></label>
        <label>Dubai time<input type="datetime-local" required value={manual.eventTime} onChange={(event) => setManual({ ...manual, eventTime: event.target.value })} /></label>
        <label>Reason<input required maxLength="500" value={manual.note} onChange={(event) => setManual({ ...manual, note: event.target.value })} /></label>
        <button type="submit">Record event</button>
      </form>
      <section className="employee-panel"><div className="panel-heading"><h3>Recent raw events</h3></div>{events.length === 0 ? <div className="empty-state">No raw events are available.</div> : <div className="table-wrap"><table><thead><tr><th>Time</th><th>Employee</th><th>Event</th><th>Method</th></tr></thead><tbody>{events.map((row) => <tr key={row.id}><td>{row.eventTime}</td><td>{employees.find((employee) => employee.id === row.employeeId)?.name ?? row.employeeId}</td><td>{row.eventType.replace('_', ' ')}</td><td>{row.method}</td></tr>)}</tbody></table></div>}</section>
      {message && <p role="status">{message}</p>}
    </section>
  )
}

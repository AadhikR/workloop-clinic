import { useCallback, useEffect, useState } from 'react'

import { readAttendanceRecords } from './attendanceCalculationApi.js'
import {
  approveOvertime,
  decideRegularisation,
  readAttendanceAudit,
  readRegularisationQueue,
  resolveAbsence,
} from './attendanceExceptionsApi.js'
import { readAllEmployees } from './employeeApi.js'

const actionLabels = {
  ABSENCE_RESOLVED: 'Absence resolved',
  OVERTIME_APPROVED: 'Overtime approved',
  REGULARISATION_APPROVED: 'Correction approved',
  REGULARISATION_REJECTED: 'Correction rejected',
}

export default function AttendanceExceptions({ authentication, branchId }) {
  const [requests, setRequests] = useState([])
  const [records, setRecords] = useState([])
  const [audit, setAudit] = useState([])
  const [employees, setEmployees] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const names = new Map(employees.map((employee) => [employee.id, `${employee.employeeNo} — ${employee.name}`]))

  const load = useCallback(async () => {
    const [nextRequests, nextRecords, nextAudit, nextEmployees] = await Promise.all([
      readRegularisationQueue(authentication, branchId, { status: 'Pending', limit: 50 }),
      readAttendanceRecords(authentication, branchId, { limit: 100 }),
      readAttendanceAudit(authentication, branchId, { limit: 20 }),
      readAllEmployees(authentication, branchId),
    ])
    setRequests(nextRequests.data)
    setRecords(nextRecords.data)
    setAudit(nextAudit.data)
    setEmployees(nextEmployees)
  }, [authentication, branchId])

  useEffect(() => {
    const refresh = async () => {
      try { await load() }
      catch { setMessage('Attendance exception controls are unavailable.') }
    }
    void refresh()
  }, [load])

  const run = async (operation, success) => {
    setBusy(true); setMessage('')
    try { await operation(); await load(); setMessage(success) }
    catch { setMessage('Nothing changed because the request was stale, closed, or no longer valid.') }
    finally { setBusy(false) }
  }

  const decide = (request, action) => {
    const rejectionReason = action === 'reject' ? window.prompt('Why is this correction being rejected?') : null
    if (action === 'reject' && !rejectionReason) return
    run(
      () => decideRegularisation(authentication, branchId, request.id, action, request.version, rejectionReason, { idempotencyKey: crypto.randomUUID() }),
      action === 'approve' ? 'Correction approved and attendance recalculated.' : 'Correction rejected.',
    )
  }

  const resolve = (record, resolutionType) => {
    const reason = window.prompt('Add the evidence or reason for this resolution.')
    if (!reason) return
    run(
      () => resolveAbsence(authentication, branchId, record.id, { expectedCalculationVersion: record.calculationVersion, resolutionType, reason }, { idempotencyKey: crypto.randomUUID() }),
      'Absence resolved and attendance recalculated.',
    )
  }

  const unresolved = records.filter((record) => record.status === 'UNEXPLAINED_ABSENCE' && record.resolutionType === null)
  const unapprovedOvertime = records.filter((record) => Number(record.overtimeHours) > 0 && !record.overtimeApproved && !record.periodClosed && !record.sourceStale)

  return (
    <section className="attendance-exceptions" aria-labelledby="attendance-exceptions-title">
      <h2 id="attendance-exceptions-title">Attendance exceptions</h2>
      <p>Review corrections, resolve absences, and approve calculated overtime for the selected branch.</p>

      <h3>Pending corrections</h3>
      {requests.length === 0 ? <p>No pending corrections.</p> : <ul className="exception-list">{requests.map((request) => <li key={request.id}><span><strong>{names.get(request.employeeId) ?? request.employeeId}</strong><br />{request.attendanceDate}: {request.reason}<br />{request.correctClockIn} to {request.correctClockOut}</span><div className="settings-actions"><button disabled={busy} type="button" onClick={() => decide(request, 'approve')}>Approve</button><button disabled={busy} className="danger" type="button" onClick={() => decide(request, 'reject')}>Reject</button></div></li>)}</ul>}

      <h3>Unresolved absences</h3>
      {unresolved.length === 0 ? <p>No unresolved absences.</p> : <ul className="exception-list">{unresolved.map((record) => <li key={record.id}><span><strong>{names.get(record.employeeId) ?? record.employeeId}</strong><br />{record.date}</span><div className="settings-actions"><button disabled={busy} type="button" onClick={() => resolve(record, 'LEAVE_LINKED')}>Link leave</button><button disabled={busy} className="danger" type="button" onClick={() => resolve(record, 'UNAUTHORISED')}>Unauthorised</button><button disabled={busy} className="secondary" type="button" onClick={() => resolve(record, 'WFH')}>Confirm WFH</button></div></li>)}</ul>}

      <h3>Overtime awaiting approval</h3>
      {unapprovedOvertime.length === 0 ? <p>No overtime awaits approval.</p> : <ul className="exception-list">{unapprovedOvertime.map((record) => <li key={record.id}><span><strong>{names.get(record.employeeId) ?? record.employeeId}</strong><br />{record.date}: {record.overtimeHours} hours, AED {record.overtimeAmount}</span><button disabled={busy} type="button" onClick={() => run(() => approveOvertime(authentication, branchId, record.id, record.calculationVersion, { idempotencyKey: crypto.randomUUID() }), 'Overtime approved.')}>Approve overtime</button></li>)}</ul>}

      <h3>Recent audit</h3>
      <ul className="exception-list">{audit.map((item) => <li key={item.id}><span>{item.occurredAt}<br />{names.get(item.employeeId) ?? item.employeeId}: {actionLabels[item.action]}</span></li>)}</ul>
      {message && <p role="status">{message}</p>}
    </section>
  )
}

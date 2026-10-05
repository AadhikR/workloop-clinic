import { useCallback, useEffect, useState } from 'react'
import { FormDialog } from './PortalUi.jsx'

import { readAllEmployees, readEmployeePortalRole } from './employeeApi.js'
import {
  createDelegation,
  decideLeave,
  deleteDelegation,
  readAdminApprovalQueue,
  readApproverQueue,
  readDelegations,
  readLeaveAudit,
  updateDelegation,
} from './leaveApprovalApi.js'

const emptyDelegation = Object.freeze({
  id: null,
  approverEmployeeId: '',
  delegateEmployeeId: '',
  fromDate: '',
  toDate: '',
  expectedUpdatedAt: null,
})

function QueueRow({ item, admin, authentication, branchId, onChanged }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [audit, setAudit] = useState(null)
  const [rejecting, setRejecting] = useState(false)
  const [retry, setRetry] = useState(null)
  const needsOverrideReason = admin && item.request.status === 'Pending'

  const decide = async (decision) => {
    if (!item.canDecide || busy) return
    if ((decision === 'reject' || needsOverrideReason) && !reason.trim()) {
      setMessage(decision === 'reject' ? 'Enter a rejection reason.' : 'Enter an override reason.')
      return
    }
    setBusy(true)
    setMessage('Recording decision...')
    const payload = JSON.stringify({ decision, reason, version: item.request.updatedAt })
    const attempt = retry?.payload === payload ? retry : { payload, key: crypto.randomUUID() }
    setRetry(attempt)
    try {
      await decideLeave(
        authentication,
        admin ? branchId : null,
        item.request.id,
        decision,
        reason,
        item.request.updatedAt,
        attempt.key,
      )
      setMessage('Decision recorded.')
      setRejecting(false); setRetry(null)
      await onChanged().catch(() => setMessage('Decision recorded. Refresh to see the latest queue.'))
    } catch {
      setMessage('The request changed or you no longer have authority to decide it.')
    } finally {
      setBusy(false)
    }
  }

  const showAudit = async () => {
    try {
      setAudit(await readLeaveAudit(
        authentication, admin ? branchId : null, item.request.id,
      ))
    } catch {
      setMessage('Audit history is unavailable for this request.')
    }
  }

  return (
    <tr>
      <td>{item.employee.name}<br /><small>{item.employee.employeeNumber}</small></td>
      <td>{item.leaveType.name}</td>
      <td>{item.request.startDate} to {item.request.endDate}</td>
      <td>{item.request.daysRequested}</td>
      {!admin && <td>{item.request.reason || 'None'}</td>}
      <td>{item.request.status}</td>
      <td>{item.visibleBecause}</td>
      <td>
        {admin && <label>
          <span className="sr-only">Decision reason for {item.employee.name}</span>
          <input
            maxLength="2000"
            placeholder={needsOverrideReason ? 'Override reason' : 'Decision reason'}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>}
        <div className="actions">
          <button type="button" disabled={busy || !item.canDecide} onClick={() => decide('approve')}>Approve</button>
          <button type="button" className="danger" disabled={busy || !item.canDecide} onClick={() => admin ? decide('reject') : setRejecting(true)}>
            Reject
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={showAudit}>
            Audit
          </button>
        </div>
        {message && <p role="status">{message}</p>}
        <FormDialog title="Reject leave request" open={rejecting} onClose={() => { if (!busy) setRejecting(false) }}><form className="restoration-form" onSubmit={(event) => { event.preventDefault(); decide('reject') }}><p>{item.employee.name} · {item.request.startDate} to {item.request.endDate}</p><label>Rejection reason<textarea required maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>{message && <p role="alert">{message}</p>}<button type="submit" className="btn btn-danger" disabled={busy}>{busy ? 'Saving...' : 'Reject request'}</button></form></FormDialog>
        {audit && (
          <ol className="leave-audit-list">
            {audit.map((entry) => (
              <li key={entry.id}>
                {entry.oldStatus || 'Created'} to {entry.newStatus}: {entry.reason}
              </li>
            ))}
          </ol>
        )}
      </td>
    </tr>
  )
}

function Queue({ items, ...props }) {
  if (items.length === 0) return <p>No leave requests await your decision.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th><th>Leave type</th><th>Dates</th><th>Days</th>
            {!props.admin && <th>Reason</th>}
            <th>Status</th><th>Queue source</th><th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => <QueueRow key={item.request.id} item={item} {...props} />)}
        </tbody>
      </table>
    </div>
  )
}

export function Delegations({ authentication, branchId }) {
  const [rows, setRows] = useState([])
  const [employees, setEmployees] = useState([])
  const [form, setForm] = useState(emptyDelegation)
  const [message, setMessage] = useState('')

  const refresh = useCallback(async (signal) => {
    const [delegations, employeeRows] = await Promise.all([
      readDelegations(authentication, branchId, { signal }),
      readAllEmployees(authentication, branchId, { signal }),
    ])
    const activeEmployees = employeeRows.filter((employee) => employee.active)
    const portalRoles = await Promise.all(activeEmployees.map((employee) => (
      readEmployeePortalRole(authentication, branchId, employee.id, { signal })
    )))
    const rolesByEmployee = new Map(portalRoles.map((portal) => [portal.employeeId, portal.role]))
    setRows(delegations)
    setEmployees(activeEmployees.map((employee) => ({
      ...employee,
      portalRole: rolesByEmployee.get(employee.id) ?? null,
    })))
  }, [authentication, branchId])

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        await refresh(controller.signal)
      } catch {
        if (!controller.signal.aborted) setMessage('Leave delegations are unavailable.')
      }
    }
    void load()
    return () => controller.abort()
  }, [refresh])

  const change = (name, value) => setForm((current) => ({ ...current, [name]: value }))

  const save = async (event) => {
    event.preventDefault()
    setMessage('Saving delegation...')
    const values = {
      approverEmployeeId: form.approverEmployeeId,
      delegateEmployeeId: form.delegateEmployeeId,
      fromDate: form.fromDate,
      toDate: form.toDate,
    }
    try {
      if (form.id) {
        await updateDelegation(authentication, branchId, form.id, {
          ...values, expectedUpdatedAt: form.expectedUpdatedAt,
        })
      } else {
        await createDelegation(authentication, branchId, values)
      }
      setForm(emptyDelegation)
      await refresh()
      setMessage('Delegation saved.')
    } catch {
      setMessage('The delegation is invalid, overlaps another period, or has already started.')
    }
  }

  const remove = async (row) => {
    setMessage('Deleting delegation...')
    try {
      await deleteDelegation(authentication, branchId, row.id, row.updatedAt)
      await refresh()
      setMessage('Delegation deleted.')
    } catch {
      setMessage('Only delegations that have not started can be deleted.')
    }
  }

  return (
    <section aria-labelledby="leave-delegations-title">
      <h3 id="leave-delegations-title">Approval delegations</h3>
      <form onSubmit={save} className="employee-form-grid">
        <label>
          Approver
          <select required value={form.approverEmployeeId} onChange={(event) => change('approverEmployeeId', event.target.value)}>
            <option value="">Select a manager</option>
            {employees.filter((employee) => employee.portalRole === 'manager').map((employee) => (
              <option key={employee.id} value={employee.id}>{employee.name}</option>
            ))}
          </select>
        </label>
        <label>
          Delegate
          <select required value={form.delegateEmployeeId} onChange={(event) => change('delegateEmployeeId', event.target.value)}>
            <option value="">Select an employee</option>
            {employees.filter((employee) => employee.id !== form.approverEmployeeId).map((employee) => (
              <option key={employee.id} value={employee.id}>{employee.name}</option>
            ))}
          </select>
        </label>
        <label>Starts <input required type="date" value={form.fromDate} onChange={(event) => change('fromDate', event.target.value)} /></label>
        <label>Ends <input required type="date" min={form.fromDate || undefined} value={form.toDate} onChange={(event) => change('toDate', event.target.value)} /></label>
        <div className="actions">
          <button type="submit">{form.id ? 'Update delegation' : 'Create delegation'}</button>
          {form.id && <button type="button" className="secondary" onClick={() => setForm(emptyDelegation)}>Cancel edit</button>}
        </div>
      </form>
      {message && <p role="status">{message}</p>}
      {rows.length === 0 ? <p>No leave approval delegations exist.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Approver</th><th>Delegate</th><th>Period</th><th>Actions</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{employees.find((employee) => employee.id === row.approverEmployeeId)?.name ?? row.approverEmployeeId}</td>
                  <td>{employees.find((employee) => employee.id === row.delegateEmployeeId)?.name ?? row.delegateEmployeeId}</td>
                  <td>{row.fromDate} to {row.toDate}</td>
                  <td className="actions">
                    <button type="button" className="secondary" onClick={() => setForm({ ...row, expectedUpdatedAt: row.updatedAt })}>Edit</button>
                    <button type="button" className="danger" onClick={() => remove(row)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default function LeaveApprovals({ account, authentication, branchId, queueOnly = false, delegationsOnly = false }) {
  const admin = account.role === 'admin'
  const [state, setState] = useState({ status: 'loading', items: [], message: '' })

  const refresh = useCallback(async (signal) => {
    const items = admin
      ? await readAdminApprovalQueue(authentication, branchId, { signal })
      : await readApproverQueue(authentication, { signal })
    setState({ status: 'ready', items, message: '' })
  }, [admin, authentication, branchId])

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        await refresh(controller.signal)
      } catch {
        if (!controller.signal.aborted) setState({ status: 'error', items: [], message: 'The approval queue is unavailable.' })
      }
    }
    void load()
    return () => controller.abort()
  }, [refresh])

  return (
    <section className="leave-approvals" aria-labelledby={delegationsOnly ? 'leave-delegations-title' : 'leave-approvals-title'}>
      {!delegationsOnly && <header className="employee-section-heading"><div><h2 id="leave-approvals-title">{admin ? 'Branch leave decisions' : 'Leave Queue'}</h2>{!admin && <p>Pending requests from current direct reports and active approval delegations.</p>}</div><button type="button" className="btn btn-outline" onClick={() => refresh().catch(() => setState({ status: 'error', items: [], message: 'The approval queue is unavailable.' }))}>Refresh</button></header>}
      {state.message && <p role="status">{state.message}</p>}
      {!delegationsOnly && (state.status === 'loading' ? <p>Loading approval queue...</p> : (
        <Queue
          items={state.items}
          admin={admin}
          authentication={authentication}
          branchId={branchId}
          onChanged={refresh}
        />
      ))}
      {admin && !queueOnly && <Delegations authentication={authentication} branchId={branchId} />}
    </section>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import PortalDialog from './PortalDialog.jsx'

import {
  initializeLeaveBalances,
  readAllAdminLeaveBalances,
  readAllAdminLeaveRequests,
  readAllEmployeeLeaveBalances,
  readAllEmployeeLeaveRequests,
  recalculateLeaveBalances,
} from './leaveBalanceApi.js'
import {
  createLeaveAttachmentDownload,
  uploadStagedLeaveAttachment,
  uploadLeaveAttachment,
} from './leaveAttachmentApi.js'
import { readAllEmployees } from './employeeApi.js'
import {
  cancelAdminLeaveRequest,
  cancelEmployeeLeaveRequest,
  createLeaveIdempotencyKey,
  readSubmissionLeaveTypes,
  submitAdminLeaveRequest,
  submitEmployeeLeaveRequest,
} from './leaveRequestApi.js'
import { downloadLeaveBalances } from './outputApi.js'
import { saveDownload } from './outputDelivery.js'

function currentYear() {
  return new Date().getUTCFullYear()
}

function BalanceTable({ balances, employees, leaveTypes }) {
  if (balances.length === 0) return <p>No balances exist for this leave year.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Leave type</th>
            <th>Entitled</th>
            <th>Accrued</th>
            <th>Used</th>
            <th>Pending</th>
            <th>Carried</th>
            <th>Remaining</th>
          </tr>
        </thead>
        <tbody>
          {balances.map((balance) => (
            <tr key={`${balance.employeeId}:${balance.leaveTypeId}:${balance.leaveYear}`}>
              <td>{employees.find((employee) => employee.id === balance.employeeId)?.name ?? 'Employee unavailable'}</td>
              <td>{leaveTypes.find((type) => type.id === balance.leaveTypeId)?.name ?? 'Leave type unavailable'}</td>
              <td>{balance.entitledDays}</td>
              <td>{balance.accruedDays}</td>
              <td>{balance.usedDays}</td>
              <td>{balance.pendingDays}</td>
              <td>{balance.carriedForward}</td>
              <td>{balance.remainingDays}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EmployeeBalanceCards({ balances, leaveTypes }) {
  if (balances.length === 0) return <div className="empty-state"><h3>No balances</h3><p>No leave balances exist for this year.</p></div>
  return <div className="leave-balance-grid">{balances.map((balance) => {
    const allowance = Number(balance.entitledDays) + Number(balance.carriedForward)
    const used = Number(balance.usedDays) + Number(balance.pendingDays)
    const percent = allowance > 0 ? Math.min(100, Math.round((used / allowance) * 100)) : 0
    return <article className="leave-balance-card" key={`${balance.employeeId}:${balance.leaveTypeId}:${balance.leaveYear}`}><h3>{leaveTypes.find((type) => type.id === balance.leaveTypeId)?.name ?? 'Leave type unavailable'}</h3><div className="leave-balance-value"><strong>{balance.remainingDays}</strong><span>days remaining</span></div><dl><div><dt>Allowance</dt><dd>{balance.entitledDays}</dd></div><div><dt>Used</dt><dd>{balance.usedDays}</dd></div><div><dt>Pending</dt><dd>{balance.pendingDays}</dd></div></dl><div className="progress-track" aria-label={`${percent}% of leave used`}><span style={{ width: `${percent}%` }} /></div></article>
  })}</div>
}

function LeaveCalendar({ month, onMonthChange, requests }) {
  const [year, monthNumber] = month.split('-').map(Number)
  const firstWeekday = new Date(Date.UTC(year, monthNumber - 1, 1)).getUTCDay()
  const daysInMonth = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate()
  const approved = requests.filter((request) => request.status === 'Approved')
  const cells = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
  return <><div className="month-toolbar"><label>Month<input type="month" value={month} onChange={(event) => onMonthChange(event.target.value)} /></label></div><div className="leave-calendar" role="grid" aria-label={`Approved leave for ${month}`}><div className="calendar-weekdays" role="row">{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => <span role="columnheader" key={day}>{day}</span>)}</div><div className="calendar-days">{cells.map((day, index) => {
    if (day === null) return <span aria-hidden="true" className="calendar-day empty" key={`empty-${index}`} />
    const date = `${month}-${String(day).padStart(2, '0')}`
    const entries = approved.filter((request) => request.startDate <= date && request.endDate >= date)
    return <article className="calendar-day" role="gridcell" key={date}><time dateTime={date}>{day}</time>{entries.map((request) => <span key={request.id} title={request.reason || 'Approved leave'}>{request.daysRequested} day leave</span>)}</article>
  })}</div></div>{approved.length === 0 && <p className="empty-copy">No approved leave appears in this month.</p>}</>
}

const emptySubmission = Object.freeze({
  employeeId: '',
  leaveTypeId: '',
  startDate: '',
  endDate: '',
  isHalfDay: false,
  halfDayPeriod: '',
  reason: '',
  relationship: '',
  deceasedName: '',
  dateOfDeath: '',
  childBirthDate: '',
  childName: '',
  expectedDueDate: '',
  institutionName: '',
  examDates: '',
  substituteEmployeeId: '',
})

function optional(value) {
  return value === '' ? null : value
}

function submissionPayload(form, attachmentId, admin) {
  const payload = {
    leaveTypeId: form.leaveTypeId,
    startDate: form.startDate,
    endDate: form.endDate,
    isHalfDay: form.isHalfDay,
    halfDayPeriod: form.isHalfDay ? form.halfDayPeriod : null,
    reason: form.reason,
    attachmentId,
    relationship: optional(form.relationship),
    deceasedName: optional(form.deceasedName),
    dateOfDeath: optional(form.dateOfDeath),
    childBirthDate: optional(form.childBirthDate),
    childName: optional(form.childName),
    expectedDueDate: optional(form.expectedDueDate),
    institutionName: optional(form.institutionName),
    examDates: optional(form.examDates),
    substituteEmployeeId: optional(form.substituteEmployeeId),
  }
  return admin ? { ...payload, employeeId: form.employeeId } : payload
}

function LeaveRequestForm({ admin, authentication, branchId, employees, leaveTypes, onSubmitted }) {
  const [form, setForm] = useState(emptySubmission)
  const [file, setFile] = useState(null)
  const [stagedAttachmentId, setStagedAttachmentId] = useState(null)
  const [retry, setRetry] = useState(null)
  const [status, setStatus] = useState({ busy: false, message: '', result: null })
  const selectedType = leaveTypes.find((leaveType) => leaveType.id === form.leaveTypeId)
  const requestedDays = useMemo(() => {
    if (!form.startDate || !form.endDate || form.endDate < form.startDate) return null
    if (form.isHalfDay) return '0.5'
    const start = new Date(`${form.startDate}T00:00:00Z`)
    const end = new Date(`${form.endDate}T00:00:00Z`)
    let days = 0
    for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
      if (![0, 6].includes(cursor.getUTCDay())) days += 1
    }
    return String(days)
  }, [form.endDate, form.isHalfDay, form.startDate])
  const eligibleEmployees = employees.filter((employee) => (
    employee.active && ['active', 'probation', 'on_leave'].includes(employee.employmentStatus)
  ))

  const change = (name, value) => {
    setForm((current) => name === 'leaveTypeId' ? {
      ...current,
      leaveTypeId: value,
      relationship: '',
      deceasedName: '',
      dateOfDeath: '',
      childBirthDate: '',
      childName: '',
      expectedDueDate: '',
      institutionName: '',
      examDates: '',
    } : { ...current, [name]: value })
    setRetry(null)
    setStatus((current) => ({ ...current, message: '', result: null }))
  }

  const selectFile = (selected) => {
    setFile(selected)
    setStagedAttachmentId(null)
    setRetry(null)
    setStatus((current) => ({ ...current, message: '', result: null }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setStatus({ busy: true, message: file ? 'Uploading attachment...' : 'Submitting request...', result: null })
    try {
      let attachmentId = stagedAttachmentId
      if (file && attachmentId === null) {
        const uploaded = await uploadStagedLeaveAttachment(
          authentication,
          admin ? branchId : null,
          admin ? form.employeeId : null,
          file,
        )
        attachmentId = uploaded.id
        setStagedAttachmentId(uploaded.id)
      }
      const payload = submissionPayload(form, attachmentId, admin)
      const fingerprint = JSON.stringify(payload)
      const idempotencyKey = retry?.fingerprint === fingerprint
        ? retry.idempotencyKey
        : createLeaveIdempotencyKey()
      setRetry({ fingerprint, idempotencyKey })
      setStatus({ busy: true, message: 'Submitting request...', result: null })
      const result = admin
        ? await submitAdminLeaveRequest(
          authentication, branchId, payload, idempotencyKey,
        )
        : await submitEmployeeLeaveRequest(authentication, payload, idempotencyKey)
      setForm(emptySubmission)
      setFile(null)
      setStagedAttachmentId(null)
      setRetry(null)
      setStatus({
        busy: false,
        message: `Request submitted for ${result.daysRequested} day(s). Status: ${result.status}.`,
        result,
      })
      await onSubmitted()
    } catch {
      setStatus({
        busy: false,
        message: stagedAttachmentId || file
          ? 'The request was not submitted. The uploaded file will be reused when you retry unchanged details.'
          : 'The request was not submitted. Check the details and try again.',
        result: null,
      })
    }
  }

  const substituteOptions = eligibleEmployees.filter((employee) => employee.id !== form.employeeId)

  return (
    <form className="leave-request-form" onSubmit={submit}>
      <h3>Submit leave request</h3>
      <div className="employee-form-grid">
        {admin && (
          <label>
            Employee
            <select
              required
              value={form.employeeId}
              onChange={(event) => change('employeeId', event.target.value)}
            >
              <option value="">Select an employee</option>
              {eligibleEmployees.map((employee) => (
                <option key={employee.id} value={employee.id}>{employee.name} ({employee.empNo})</option>
              ))}
            </select>
          </label>
        )}
        <label>
          Leave type
          <select
            required
            value={form.leaveTypeId}
            onChange={(event) => change('leaveTypeId', event.target.value)}
          >
            <option value="">Select a leave type</option>
            {leaveTypes.filter((leaveType) => leaveType.isActive).map((leaveType) => (
              <option key={leaveType.id} value={leaveType.id}>{leaveType.name}</option>
            ))}
          </select>
        </label>
        <label>
          Start date
          <input
            type="date"
            required
            value={form.startDate}
            onChange={(event) => change('startDate', event.target.value)}
          />
        </label>
        <label>
          End date
          <input
            type="date"
            required
            min={form.startDate || undefined}
            value={form.endDate}
            onChange={(event) => change('endDate', event.target.value)}
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.isHalfDay}
            onChange={(event) => change('isHalfDay', event.target.checked)}
          />
          Half day
        </label>
        {form.isHalfDay && (
          <label>
            Half-day period
            <select
              required
              value={form.halfDayPeriod}
              onChange={(event) => change('halfDayPeriod', event.target.value)}
            >
              <option value="">Select a period</option>
              <option value="AM">Morning</option>
              <option value="PM">Afternoon</option>
            </select>
          </label>
        )}
        <label>
          Substitute
          <select
            value={form.substituteEmployeeId}
            onChange={(event) => change('substituteEmployeeId', event.target.value)}
          >
            <option value="">No substitute</option>
            {substituteOptions.map((employee) => (
              <option key={employee.id} value={employee.id}>{employee.name}</option>
            ))}
          </select>
        </label>
        {selectedType?.code === 'BEREAVEMENT' && (
          <>
            <label>
              Relationship
              <select
                required
                value={form.relationship}
                onChange={(event) => change('relationship', event.target.value)}
              >
                <option value="">Select a relationship</option>
                {['Spouse', 'Parent', 'Child', 'Sibling'].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              Deceased name
              <input
                maxLength="200"
                value={form.deceasedName}
                onChange={(event) => change('deceasedName', event.target.value)}
              />
            </label>
            <label>
              Date of death
              <input
                type="date"
                max={form.startDate || undefined}
                value={form.dateOfDeath}
                onChange={(event) => change('dateOfDeath', event.target.value)}
              />
            </label>
          </>
        )}
        {selectedType?.code === 'PATERNITY' && (
          <>
            <label>
              Child birth date
              <input
                type="date"
                required
                max={form.startDate || undefined}
                value={form.childBirthDate}
                onChange={(event) => change('childBirthDate', event.target.value)}
              />
            </label>
            <label>
              Child name
              <input
                maxLength="200"
                value={form.childName}
                onChange={(event) => change('childName', event.target.value)}
              />
            </label>
          </>
        )}
        {selectedType?.code === 'MATERNITY' && (
          <label>
            Expected due date
            <input
              type="date"
              required
              value={form.expectedDueDate}
              onChange={(event) => change('expectedDueDate', event.target.value)}
            />
          </label>
        )}
        {selectedType?.code === 'STUDY' && (
          <>
            <label>
              Institution name
              <input
                required
                maxLength="300"
                value={form.institutionName}
                onChange={(event) => change('institutionName', event.target.value)}
              />
            </label>
            <label>
              Exam dates
              <input
                required
                maxLength="1000"
                value={form.examDates}
                onChange={(event) => change('examDates', event.target.value)}
              />
            </label>
          </>
        )}
        <label>
          Attachment
          <input
            type="file"
            required={selectedType?.requiresAttachment === true && stagedAttachmentId === null}
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          />
          {stagedAttachmentId && <span>Uploaded and ready for retry.</span>}
        </label>
        <label className="leave-request-reason">
          Reason
          <textarea
            required={selectedType?.requiresReason === true}
            maxLength="2000"
            rows="4"
            value={form.reason}
            onChange={(event) => change('reason', event.target.value)}
          />
        </label>
      </div>
      {requestedDays !== null && <p className="leave-day-preview"><strong>{requestedDays}</strong> estimated working day{requestedDays === '1' ? '' : 's'}. The server applies branch holidays and leave rules when you submit.</p>}
      <button type="submit" disabled={status.busy || leaveTypes.length === 0}>
        {status.busy ? 'Working...' : 'Submit request'}
      </button>
      {status.message && <p role="status">{status.message}</p>}
      {status.result?.approvalComment && <p>{status.result.approvalComment}</p>}
      {status.result?.warnings.length > 0 && (
        <ul>{status.result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      )}
    </form>
  )
}

function RequestTable({
  admin, requests, employees, onCancel, onDownload, onUpload, uploadState, cancellingId,
}) {
  const today = new Date().toISOString().slice(0, 10)
  if (requests.length === 0) return <p>No leave requests overlap this leave year.</p>
  return (
    <div className="table-wrap leave-history-table">
      <table className="leave-request-table">
        <thead>
          <tr>
            {admin && <th>Employee</th>}
            <th>Dates</th>
            <th>Days</th>
            <th>Status</th>
            <th>Reason</th>
            <th>Attachment</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr key={request.id}>
              {admin && <td data-label="Employee">{employees.find((employee) => employee.id === request.employeeId)?.name ?? 'Employee unavailable'}</td>}
              <td className="leave-request-dates" data-label="Dates"><span className="leave-request-date-range"><time dateTime={request.startDate}>{request.startDate}</time><span className="leave-request-date-separator">to</span><time dateTime={request.endDate}>{request.endDate}</time></span></td>
              <td data-label="Days">{request.daysRequested}</td>
              <td data-label="Status"><span className="status-pill" data-status={request.status.toLowerCase()}>{request.status}</span>{request.rejectionReason && <small>{request.rejectionReason}</small>}</td>
              <td className="leave-request-reason-cell" data-label="Reason">{request.reason || 'No reason supplied'}</td>
              <td className="leave-request-attachment" data-label="Attachment">
                {request.attachment ? (
                  <button type="button" className="secondary" onClick={() => onDownload(request)}>
                    Download {request.attachment.fileName}
                  </button>
                ) : request.status === 'Pending' ? (
                  <label className="compact-file-picker">
                    <span className="sr-only">Upload attachment for request {request.id}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                      onChange={(event) => onUpload(request, event.target.files?.[0] ?? null)}
                    />
                  </label>
                ) : 'None'}
                {uploadState[request.id] === 'Uploading...' && (
                  <progress aria-label={`Uploading attachment for request ${request.id}`} />
                )}
                {uploadState[request.id] && <span role="status">{uploadState[request.id]}</span>}
              </td>
              <td className="leave-request-actions" data-label="Actions">
                {((!admin && request.status === 'Pending') || (
                  admin && request.status === 'Approved' && request.startDate > today
                )) && (
                  <button
                    type="button"
                    className="danger"
                    disabled={cancellingId === request.id}
                    onClick={() => onCancel(request)}
                  >
                    {cancellingId === request.id ? 'Cancelling...' : 'Cancel'}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function LeaveOverview({
  account, authentication, branchId, view = null, refreshKey = 0, onChanged = () => {},
}) {
  const [year, setYear] = useState(currentYear)
  const [state, setState] = useState({ status: 'loading', balances: [], requests: [], message: '' })
  const [uploadState, setUploadState] = useState({})
  const [referenceData, setReferenceData] = useState({ leaveTypes: [], employees: [] })
  const [cancellingId, setCancellingId] = useState(null)
  const [tab, setTab] = useState(view ?? 'requests')
  const [showRequest, setShowRequest] = useState(false)
  const [calendarMonth, setCalendarMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const admin = account.role === 'admin'
  const activeView = view ?? tab

  const read = useCallback(async (signal) => {
    void refreshKey
    const options = { year, signal }
    const [balances, requests, leaveTypes, employees] = admin
      ? await Promise.all([
        readAllAdminLeaveBalances(authentication, branchId, options),
        readAllAdminLeaveRequests(authentication, branchId, options),
        readSubmissionLeaveTypes(authentication, branchId, { signal }),
        readAllEmployees(authentication, branchId, { signal }),
      ])
      : await Promise.all([
        readAllEmployeeLeaveBalances(authentication, options),
        readAllEmployeeLeaveRequests(authentication, options),
        readSubmissionLeaveTypes(authentication, null, { signal }),
        Promise.resolve([]),
      ])
    return { balances, requests, leaveTypes, employees }
  }, [admin, authentication, branchId, refreshKey, year])

  useEffect(() => {
    const controller = new AbortController()
    read(controller.signal)
      .then(({ balances, requests, leaveTypes, employees }) => {
        if (!controller.signal.aborted) {
          setState({ status: 'ready', balances, requests, message: '' })
          setReferenceData({ leaveTypes, employees })
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({
            status: 'error',
            balances: [],
            requests: [],
            message: 'Leave details are unavailable.',
          })
        }
      })
    return () => controller.abort()
  }, [read])

  const changeBalances = async (operation) => {
    setState((current) => ({ ...current, message: 'Updating leave balances...' }))
    try {
      if (operation === 'initialize') {
        await initializeLeaveBalances(authentication, branchId, year)
      } else {
        await recalculateLeaveBalances(authentication, branchId, year)
      }
      const { balances, requests, leaveTypes, employees } = await read()
      setState({
        status: 'ready',
        balances,
        requests,
        message: operation === 'initialize'
          ? 'Missing balances were initialized.'
          : 'Balances were recalculated from leave requests.',
      })
      setReferenceData({ leaveTypes, employees })
      onChanged()
    } catch {
      setState((current) => ({ ...current, message: 'Leave balances could not be updated.' }))
    }
  }

  const upload = async (leaveRequest, file) => {
    if (!file) return
    setUploadState((current) => ({ ...current, [leaveRequest.id]: 'Uploading...' }))
    try {
      await uploadLeaveAttachment(
        authentication, admin ? branchId : null, leaveRequest.id, file,
      )
      const refreshed = await read()
      setState((current) => ({ ...current, ...refreshed }))
      setReferenceData({ leaveTypes: refreshed.leaveTypes, employees: refreshed.employees })
      setUploadState((current) => ({ ...current, [leaveRequest.id]: 'Upload complete.' }))
      onChanged()
    } catch {
      setUploadState((current) => ({
        ...current,
        [leaveRequest.id]: 'Upload failed. Choose the file again to retry.',
      }))
    }
  }

  const download = async (leaveRequest) => {
    try {
      const signed = await createLeaveAttachmentDownload(
        authentication, admin ? branchId : null, leaveRequest.attachment.id,
      )
      globalThis.location.assign(signed.url)
    } catch {
      setState((current) => ({ ...current, message: 'The attachment could not be downloaded.' }))
    }
  }

  const refresh = async () => {
    const refreshed = await read()
    setState((current) => ({
      ...current,
      balances: refreshed.balances,
      requests: refreshed.requests,
    }))
    setReferenceData({ leaveTypes: refreshed.leaveTypes, employees: refreshed.employees })
  }

  const cancel = async (leaveRequest) => {
    if (!globalThis.confirm('Cancel this pending leave request?')) return
    setCancellingId(leaveRequest.id)
    setState((current) => ({ ...current, message: 'Cancelling leave request...' }))
    try {
      const idempotencyKey = createLeaveIdempotencyKey()
      if (admin) {
        await cancelAdminLeaveRequest(
          authentication, branchId, leaveRequest.id, idempotencyKey,
        )
      } else {
        await cancelEmployeeLeaveRequest(authentication, leaveRequest.id, idempotencyKey)
      }
      await refresh()
      setState((current) => ({ ...current, message: 'Leave request cancelled.' }))
      onChanged()
    } catch {
      setState((current) => ({ ...current, message: 'The leave request could not be cancelled.' }))
    } finally {
      setCancellingId(null)
    }
  }

  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })
  const onLeaveToday = state.requests.filter((request) => (
    request.status === 'Approved' && request.startDate <= today && request.endDate >= today
  ))
  const pendingRequests = state.requests.filter((request) => (
    request.status === 'Pending' || request.status === 'ManagerApproved'
  ))
  const employeeName = (employeeId) => (
    referenceData.employees.find((employee) => employee.id === employeeId)?.name
    ?? 'Employee unavailable'
  )

  return (
    <section className="leave-overview" aria-labelledby="leave-overview-title">
      <header className="employee-module-toolbar leave-toolbar">
        <div>
          <h2 id="leave-overview-title">{admin ? 'Branch leave overview' : 'My leave'}</h2>
          <p>{admin ? 'Review branch requests and balances for the selected year.' : 'Submit requests and track balances, approvals, and planned leave.'}</p>
        </div>
        <label className="leave-year-control">
          <span>Leave year</span>
          <input
            type="number"
            min="2000"
            max="2100"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
          />
        </label>
        <button type="button" className="btn btn-primary" disabled={state.status !== 'ready'} onClick={() => setShowRequest(true)}>Request Leave</button>
      </header>
      {admin && (
        <div className="actions module-actions">
          <button type="button" onClick={() => changeBalances('initialize')}>Initialize missing</button>
          <button type="button" className="secondary" onClick={() => changeBalances('recalculate')}>
            Recalculate all
          </button>
          <button type="button" className="secondary" onClick={async () => saveDownload(await downloadLeaveBalances(authentication, branchId, year))}>
            Download balance CSV
          </button>
        </div>
      )}
      {state.message && <p className="feedback" role="status">{state.message}</p>}
      {state.status === 'loading' && <p className="module-loading">Loading leave details...</p>}
      {state.status === 'error' && <p className="feedback danger">Try refreshing after the leave service is available.</p>}
      {state.status === 'ready' && (
        <>
          {!view && <div className="tabs" role="tablist" aria-label="Leave views">{[['requests', 'Requests'], ['balances', 'Balances'], ['calendar', 'Calendar']].map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} className={`tab-btn${tab === id ? ' active' : ''}`} key={id} onClick={() => setTab(id)}>{label}</button>)}</div>}
          {showRequest && <PortalDialog labelledBy="leave-request-dialog-title" onClose={() => setShowRequest(false)}><div className="modal-header"><h3 id="leave-request-dialog-title">Request Leave</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close leave request" onClick={() => setShowRequest(false)}>×</button></div><div className="modal-body"><LeaveRequestForm
              admin={admin}
              authentication={authentication}
              branchId={branchId}
              employees={referenceData.employees}
              leaveTypes={referenceData.leaveTypes}
              onSubmitted={async () => { await refresh(); onChanged(); setShowRequest(false) }}
            /></div></PortalDialog>}
          {activeView === 'overview' && <div className="leave-tab-panel leave-dashboard" role="tabpanel">
            <div className="stats-grid module-summary-grid">
              <div className="stat-card"><div className="stat-label">On leave today</div><div className="stat-value">{onLeaveToday.length}</div><div className="stat-sub">approved absences</div></div>
              <div className="stat-card"><div className="stat-label">Pending approvals</div><div className="stat-value">{pendingRequests.length}</div><div className="stat-sub">awaiting a decision</div></div>
              <div className="stat-card"><div className="stat-label">Leave types</div><div className="stat-value">{referenceData.leaveTypes.length}</div><div className="stat-sub">available in this branch</div></div>
              <div className="stat-card"><div className="stat-label">Balance records</div><div className="stat-value">{state.balances.length}</div><div className="stat-sub">for {year}</div></div>
            </div>
            <section className="employee-panel"><div className="panel-heading"><h3>On leave today</h3></div>{onLeaveToday.length === 0 ? <div className="empty-state">No approved leave today.</div> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Dates</th><th>Days</th><th>Status</th></tr></thead><tbody>{onLeaveToday.map((request) => <tr key={request.id}><td>{employeeName(request.employeeId)}</td><td>{request.startDate} to {request.endDate}</td><td>{request.daysRequested}</td><td>{request.status}</td></tr>)}</tbody></table></div>}</section>
            <section className="employee-panel"><div className="panel-heading"><h3>Pending approvals</h3></div>{pendingRequests.length === 0 ? <div className="empty-state">No leave requests await a decision.</div> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Dates</th><th>Days</th><th>Status</th></tr></thead><tbody>{pendingRequests.slice(0, 5).map((request) => <tr key={request.id}><td>{employeeName(request.employeeId)}</td><td>{request.startDate} to {request.endDate}</td><td>{request.daysRequested}</td><td>{request.status}</td></tr>)}</tbody></table></div>}</section>
          </div>}
          {activeView === 'requests' && <div className="leave-tab-panel" role="tabpanel">
            <section className="employee-panel leave-history-panel" aria-labelledby="leave-history-title">
              <div className="panel-heading">
                <div>
                  <h3 id="leave-history-title">Request history</h3>
                  <p>{state.requests.length} request{state.requests.length === 1 ? '' : 's'} in {year}</p>
                </div>
              </div>
              <RequestTable
                admin={admin}
                requests={state.requests}
                employees={referenceData.employees}
                onCancel={cancel}
                onDownload={download}
                onUpload={upload}
                uploadState={uploadState}
                cancellingId={cancellingId}
              />
            </section>
          </div>}
          {activeView === 'balances' && <section className="employee-panel leave-tab-panel" role="tabpanel"><div className="panel-heading"><h3>Balances</h3></div>{admin ? <BalanceTable balances={state.balances} employees={referenceData.employees} leaveTypes={referenceData.leaveTypes} /> : <EmployeeBalanceCards balances={state.balances} leaveTypes={referenceData.leaveTypes} />}</section>}
          {activeView === 'calendar' && <section className="employee-panel leave-tab-panel leave-calendar-panel" role="tabpanel"><div className="panel-heading"><h3>Request calendar</h3></div><LeaveCalendar month={calendarMonth} onMonthChange={setCalendarMonth} requests={state.requests} /></section>}
        </>
      )}
    </section>
  )
}

import { useCallback, useEffect, useState } from 'react'

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

function currentYear() {
  return new Date().getUTCFullYear()
}

function BalanceTable({ balances }) {
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
              <td>{balance.employeeId}</td>
              <td>{balance.leaveTypeId}</td>
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
  admin, requests, onCancel, onDownload, onUpload, uploadState, cancellingId,
}) {
  const today = new Date().toISOString().slice(0, 10)
  if (requests.length === 0) return <p>No leave requests overlap this leave year.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
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
              <td>{request.employeeId}</td>
              <td>{request.startDate} to {request.endDate}</td>
              <td>{request.daysRequested}</td>
              <td>{request.status}</td>
              <td>{request.reason || 'No reason supplied'}</td>
              <td>
                {request.attachment ? (
                  <button type="button" className="secondary" onClick={() => onDownload(request)}>
                    Download {request.attachment.fileName}
                  </button>
                ) : request.status === 'Pending' ? (
                  <label>
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
              <td>
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

export default function LeaveOverview({ account, authentication, branchId }) {
  const [year, setYear] = useState(currentYear)
  const [state, setState] = useState({ status: 'loading', balances: [], requests: [], message: '' })
  const [uploadState, setUploadState] = useState({})
  const [referenceData, setReferenceData] = useState({ leaveTypes: [], employees: [] })
  const [cancellingId, setCancellingId] = useState(null)
  const admin = account.role === 'admin'

  const read = useCallback(async (signal) => {
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
  }, [admin, authentication, branchId, year])

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
    } catch {
      setState((current) => ({ ...current, message: 'The leave request could not be cancelled.' }))
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <section className="leave-overview" aria-labelledby="leave-overview-title">
      <h2 id="leave-overview-title">{admin ? 'Branch leave overview' : 'My leave'}</h2>
      <label>
        Leave year
        <input
          type="number"
          min="2000"
          max="2100"
          value={year}
          onChange={(event) => setYear(Number(event.target.value))}
        />
      </label>
      {admin && (
        <div className="actions">
          <button type="button" onClick={() => changeBalances('initialize')}>Initialize missing</button>
          <button type="button" className="secondary" onClick={() => changeBalances('recalculate')}>
            Recalculate all
          </button>
        </div>
      )}
      {state.message && <p role="status">{state.message}</p>}
      {state.status === 'loading' && <p>Loading leave details...</p>}
      {state.status === 'error' && <p>Try refreshing after the leave service is available.</p>}
      {state.status === 'ready' && (
        <>
          <LeaveRequestForm
            admin={admin}
            authentication={authentication}
            branchId={branchId}
            employees={referenceData.employees}
            leaveTypes={referenceData.leaveTypes}
            onSubmitted={refresh}
          />
          <h3>Balances</h3>
          <BalanceTable balances={state.balances} />
          <h3>Request calendar</h3>
          <RequestTable
            admin={admin}
            requests={state.requests}
            onCancel={cancel}
            onDownload={download}
            onUpload={upload}
            uploadState={uploadState}
            cancellingId={cancellingId}
          />
        </>
      )}
    </section>
  )
}

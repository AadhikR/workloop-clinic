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
  uploadLeaveAttachment,
} from './leaveAttachmentApi.js'

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

function RequestTable({ requests, onDownload, onUpload, uploadState }) {
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
  const admin = account.role === 'admin'

  const read = useCallback(async (signal) => {
    const options = { year, signal }
    const [balances, requests] = admin
      ? await Promise.all([
        readAllAdminLeaveBalances(authentication, branchId, options),
        readAllAdminLeaveRequests(authentication, branchId, options),
      ])
      : await Promise.all([
        readAllEmployeeLeaveBalances(authentication, options),
        readAllEmployeeLeaveRequests(authentication, options),
      ])
    return { balances, requests }
  }, [admin, authentication, branchId, year])

  useEffect(() => {
    const controller = new AbortController()
    read(controller.signal)
      .then(({ balances, requests }) => {
        if (!controller.signal.aborted) {
          setState({ status: 'ready', balances, requests, message: '' })
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
      const { balances, requests } = await read()
      setState({
        status: 'ready',
        balances,
        requests,
        message: operation === 'initialize'
          ? 'Missing balances were initialized.'
          : 'Balances were recalculated from leave requests.',
      })
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
          <h3>Balances</h3>
          <BalanceTable balances={state.balances} />
          <h3>Request calendar</h3>
          <RequestTable
            requests={state.requests}
            onDownload={download}
            onUpload={upload}
            uploadState={uploadState}
          />
        </>
      )}
    </section>
  )
}

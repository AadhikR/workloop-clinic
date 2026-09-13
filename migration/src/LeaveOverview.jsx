import { useCallback, useEffect, useState } from 'react'

import {
  initializeLeaveBalances,
  readAllAdminLeaveBalances,
  readAllAdminLeaveRequests,
  readAllEmployeeLeaveBalances,
  readAllEmployeeLeaveRequests,
  recalculateLeaveBalances,
} from './leaveBalanceApi.js'

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

function RequestTable({ requests }) {
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
          <RequestTable requests={state.requests} />
        </>
      )}
    </section>
  )
}

import { useEffect, useState } from 'react'

import { HttpClientError } from './http.js'
import {
  readBranchJobHistory,
  readDirectReports,
  readEmployee,
  readEmployeeJobHistory,
  readEmployees,
  readEmployeeSelf,
} from './employeeApi.js'

function useLoad(load, dependencies) {
  const [state, setState] = useState({ status: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ status: 'error', error })
      })
    return () => controller.abort()
  // The caller passes the exact values that define the request.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)
  return state
}

function EmployeeRows({ employees, onSelect }) {
  return (
    <ul className="employee-list">
      {employees.map((employee) => (
        <li key={employee.id}>
          <button type="button" onClick={() => onSelect?.(employee.id)}>
            <strong>{employee.name}</strong>
            <span>{employee.empNo} · {employee.jobTitle || 'No job title'}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function AdminDirectory({ authentication, branchId, clearBranch }) {
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const listing = useLoad(
    (signal) => readEmployees(authentication, branchId, {
      signal,
      ...(appliedSearch ? { search: appliedSearch } : {}),
    }),
    [authentication, branchId, appliedSearch],
  )
  const recentHistory = useLoad(
    (signal) => readBranchJobHistory(authentication, branchId, { signal, limit: 10 }),
    [authentication, branchId],
  )
  const detail = useLoad(
    (signal) => selectedId === null
      ? Promise.resolve(null)
      : Promise.all([
        readEmployee(authentication, branchId, selectedId, { signal }),
        readEmployeeJobHistory(authentication, branchId, selectedId, { signal }),
      ]),
    [authentication, branchId, selectedId],
  )

  useEffect(() => {
    if (
      listing.status === 'error'
      && listing.error instanceof HttpClientError
      && listing.error.code === 'resource_not_found'
    ) clearBranch()
  }, [clearBranch, listing])

  return (
    <section className="employee-directory" aria-label="Employee directory">
      <h3>Employee directory</h3>
      <form onSubmit={(event) => { event.preventDefault(); setAppliedSearch(search.trim()) }}>
        <label htmlFor="employee-search">Search employees</label>
        <div className="employee-search-row">
          <input
            id="employee-search"
            value={search}
            maxLength={100}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button type="submit">Search</button>
        </div>
      </form>
      {listing.status === 'loading' && <p>Loading employees...</p>}
      {listing.status === 'error' && <p role="status">Employee directory is unavailable.</p>}
      {listing.status === 'ready' && (
        listing.data.data.length
          ? <EmployeeRows employees={listing.data.data} onSelect={setSelectedId} />
          : <p>No employees match this branch query.</p>
      )}
      {detail.status === 'ready' && detail.data && (
        <section className="employee-detail">
          <h4>{detail.data[0].name}</h4>
          <dl>
            <div><dt>Work email</dt><dd>{detail.data[0].workEmail}</dd></div>
            <div><dt>Status</dt><dd>{detail.data[0].employmentStatus}</dd></div>
            <div><dt>Department</dt><dd>{detail.data[0].department || 'Not assigned'}</dd></div>
          </dl>
          <h5>Job history</h5>
          <p>{detail.data[1].data.length} recorded changes</p>
        </section>
      )}
      <div className="employee-history-summary">
        <h4>Recent branch job history</h4>
        <p>
          {recentHistory.status === 'ready'
            ? `${recentHistory.data.data.length} entries`
            : recentHistory.status}
        </p>
      </div>
    </section>
  )
}

function StaffDirectory({ account, authentication }) {
  const self = useLoad(
    (signal) => readEmployeeSelf(authentication, { signal }),
    [authentication],
  )
  const reports = useLoad(
    (signal) => account.role === 'manager'
      ? readDirectReports(authentication, { signal })
      : Promise.resolve(null),
    [account.role, authentication],
  )
  return (
    <section className="employee-directory" aria-label="Employee profile">
      <h3>Employee profile</h3>
      {self.status === 'loading' && <p>Loading employee profile...</p>}
      {self.status === 'error' && <p role="status">Employee profile is unavailable.</p>}
      {self.status === 'ready' && (
        <dl className="employee-self">
          <div><dt>Name</dt><dd>{self.data.name}</dd></div>
          <div><dt>Job title</dt><dd>{self.data.jobTitle || 'Not assigned'}</dd></div>
          <div><dt>Department</dt><dd>{self.data.department || 'Not assigned'}</dd></div>
          <div><dt>Manager</dt><dd>{self.data.reportingManager?.name ?? 'Not assigned'}</dd></div>
        </dl>
      )}
      {account.role === 'manager' && (
        <section className="direct-reports">
          <h4>Direct reports</h4>
          {reports.status === 'ready' && <EmployeeRows employees={reports.data.data} />}
          {reports.status === 'loading' && <p>Loading direct reports...</p>}
          {reports.status === 'error' && <p role="status">Direct reports are unavailable.</p>}
        </section>
      )}
    </section>
  )
}

export default function EmployeeDirectory({ account, authentication, branchId, clearBranch }) {
  return account.role === 'admin'
    ? (
      <AdminDirectory
        authentication={authentication}
        branchId={branchId}
        clearBranch={clearBranch}
      />
    )
    : <StaffDirectory account={account} authentication={authentication} />
}

import { useEffect, useState } from 'react'

import { HttpClientError } from './http.js'
import {
  createEmployee,
  importEmployees,
  readBranchJobHistory,
  readDirectReports,
  readEmployee,
  readEmployeeJobHistory,
  readAllEmployees,
  readEmployees,
  readEmployeeSelf,
  updateEmployee,
} from './employeeApi.js'
import { parseEmployeeCsv } from './employeeCsv.js'
import { readAllDepartments } from './departmentApi.js'

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

const emptyCreate = {
  empNo: '',
  name: '',
  molId: '',
  workEmail: '',
  jobTitle: '',
  department: '',
  reportingManagerId: '',
  employmentStatus: 'active',
  employmentStartDate: '',
  basicSalary: '0.00',
  housingAllowance: '0.00',
  transportAllowance: '0.00',
  otherAllowances: '0.00',
  allowance: '0.00',
  bankName: '',
  bankRoutingCode: '',
  iban: '',
}

function EmployeeCreateForm({ authentication, branchId, departments, managers, onSaved }) {
  const [form, setForm] = useState(emptyCreate)
  const [status, setStatus] = useState('idle')
  const change = (field) => (event) => setForm((current) => ({
    ...current,
    [field]: event.target.value,
  }))
  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    try {
      const employee = await createEmployee(authentication, branchId, {
        ...form,
        reportingManagerId: form.reportingManagerId || null,
        employmentStartDate: form.employmentStartDate || null,
      }, { idempotencyKey: crypto.randomUUID() })
      setForm(emptyCreate)
      setStatus('saved')
      onSaved(employee)
    } catch {
      setStatus('error')
    }
  }
  return (
    <form className="employee-admin-form" onSubmit={submit} data-employee-create-form>
      <h4>Add employee</h4>
      <div className="employee-form-grid">
        <label>Employee number<input value={form.empNo} onChange={change('empNo')} /></label>
        <label>Name<input required value={form.name} onChange={change('name')} /></label>
        <label>MOL ID<input required pattern="[0-9]{10,15}" value={form.molId} onChange={change('molId')} /></label>
        <label>Work email<input type="email" value={form.workEmail} onChange={change('workEmail')} /></label>
        <label>Job title<input value={form.jobTitle} onChange={change('jobTitle')} /></label>
        <label>
          Department
          <select required value={form.department} onChange={change('department')}>
            <option value="">Choose department</option>
            {departments.map((department) => <option key={department.id}>{department.name}</option>)}
          </select>
        </label>
        <label>
          Reporting manager
          <select value={form.reportingManagerId} onChange={change('reportingManagerId')}>
            <option value="">No manager</option>
            {managers.map((manager) => <option key={manager.id} value={manager.id}>{manager.name}</option>)}
          </select>
        </label>
        <label>
          Initial status
          <select value={form.employmentStatus} onChange={change('employmentStatus')}>
            <option value="active">Active</option>
            <option value="probation">Probation</option>
            <option value="on_leave">On leave</option>
          </select>
        </label>
        <label>Start date<input type="date" value={form.employmentStartDate} onChange={change('employmentStartDate')} /></label>
        <label>Basic salary<input inputMode="decimal" value={form.basicSalary} onChange={change('basicSalary')} /></label>
        <label>Housing allowance<input inputMode="decimal" value={form.housingAllowance} onChange={change('housingAllowance')} /></label>
        <label>Transport allowance<input inputMode="decimal" value={form.transportAllowance} onChange={change('transportAllowance')} /></label>
        <label>Other allowances<input inputMode="decimal" value={form.otherAllowances} onChange={change('otherAllowances')} /></label>
        <label>Allowance<input inputMode="decimal" value={form.allowance} onChange={change('allowance')} /></label>
        <label>Bank name<input value={form.bankName} onChange={change('bankName')} /></label>
        <label>Routing code<input value={form.bankRoutingCode} onChange={change('bankRoutingCode')} /></label>
        <label>IBAN<input value={form.iban} onChange={change('iban')} /></label>
      </div>
      <button type="submit" disabled={status === 'saving'}>Create employee</button>
      <p role="status" data-employee-create-status={status}>{status === 'error' ? 'Employee could not be created.' : status === 'saved' ? 'Employee created.' : ''}</p>
    </form>
  )
}

function EmployeeEditor({ authentication, branchId, employee, onSaved }) {
  const [form, setForm] = useState({
    empNo: employee.empNo,
    name: employee.name,
    molId: employee.molId,
    personalEmail: employee.personalEmail,
    phone: employee.phone,
    bankName: employee.bankName,
    bankRoutingCode: employee.bankRoutingCode,
    iban: employee.iban,
    employmentStartDate: employee.employmentStartDate ?? '',
    nationality: employee.nationality,
    workLocationType: employee.workLocationType,
    freeZoneName: employee.freeZoneName,
  })
  const [status, setStatus] = useState('idle')
  const change = (field) => (event) => setForm((current) => ({
    ...current,
    [field]: event.target.value,
  }))
  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    try {
      const updated = await updateEmployee(authentication, branchId, employee.id, {
        ...form,
        employmentStartDate: form.employmentStartDate || null,
        expectedUpdatedAt: employee.updatedAt,
      })
      setStatus('saved')
      onSaved(updated)
    } catch {
      setStatus('error')
    }
  }
  return (
    <form className="employee-admin-form" onSubmit={submit} data-employee-edit-form>
      <h5>Edit employee details</h5>
      <div className="employee-form-grid">
        <label>Employee number<input value={form.empNo} onChange={change('empNo')} /></label>
        <label>Name<input required value={form.name} onChange={change('name')} /></label>
        <label>MOL ID<input required value={form.molId} onChange={change('molId')} /></label>
        <label>Personal email<input type="email" value={form.personalEmail} onChange={change('personalEmail')} /></label>
        <label>Phone<input value={form.phone} onChange={change('phone')} /></label>
        <label>Start date<input type="date" value={form.employmentStartDate} onChange={change('employmentStartDate')} /></label>
        <label>Bank name<input value={form.bankName} onChange={change('bankName')} /></label>
        <label>Routing code<input value={form.bankRoutingCode} onChange={change('bankRoutingCode')} /></label>
        <label>IBAN<input value={form.iban} onChange={change('iban')} /></label>
        <label>Nationality<input value={form.nationality} onChange={change('nationality')} /></label>
        <label>
          Work location
          <select value={form.workLocationType} onChange={change('workLocationType')}>
            <option value="mainland">Mainland</option>
            <option value="free_zone">Free zone</option>
          </select>
        </label>
        <label>Free zone name<input value={form.freeZoneName} onChange={change('freeZoneName')} /></label>
      </div>
      <button type="submit" disabled={status === 'saving'}>Save details</button>
      <p role="status" data-employee-edit-status={status}>{status === 'error' ? 'Employee details could not be saved.' : status === 'saved' ? 'Employee details saved.' : ''}</p>
    </form>
  )
}

function EmployeeImportPanel({ authentication, branchId, onSaved }) {
  const [preview, setPreview] = useState({ rows: [], diagnostics: [] })
  const [status, setStatus] = useState('idle')
  const selectFile = async (event) => {
    const file = event.target.files?.[0]
    setStatus('idle')
    setPreview(file ? parseEmployeeCsv(await file.text()) : { rows: [], diagnostics: [] })
  }
  const submit = async () => {
    setStatus('saving')
    try {
      const result = await importEmployees(authentication, branchId, preview.rows, {
        idempotencyKey: crypto.randomUUID(),
      })
      setStatus('saved')
      onSaved(result)
    } catch {
      setStatus('error')
    }
  }
  return (
    <section className="employee-import" aria-label="Employee CSV import">
      <h4>Import employees</h4>
      <p>CSV import creates new employees only. It does not match or update existing records.</p>
      <label>CSV file<input type="file" accept=".csv,text/csv" onChange={selectFile} /></label>
      {preview.rows.length > 0 && <p>{preview.rows.length} rows ready for review.</p>}
      {preview.diagnostics.length > 0 && (
        <ul data-employee-import-diagnostics>
          {preview.diagnostics.map((item) => (
            <li key={`${item.rowNumber}-${item.field}-${item.message}`}>Row {item.rowNumber}, {item.field}: {item.message}</li>
          ))}
        </ul>
      )}
      {preview.rows.length > 0 && (
        <div className="employee-import-preview">
          <table><thead><tr><th>Row</th><th>Employee</th><th>MOL ID</th><th>Basic salary</th></tr></thead>
            <tbody>{preview.rows.map((row) => <tr key={row.rowNumber}><td>{row.rowNumber}</td><td>{row.empNo} · {row.name}</td><td>{row.molId}</td><td>{row.basicSalary}</td></tr>)}</tbody>
          </table>
        </div>
      )}
      <button type="button" onClick={submit} disabled={!preview.rows.length || preview.diagnostics.length > 0 || status === 'saving'}>Import employees</button>
      <p role="status" data-employee-import-status={status}>{status === 'error' ? 'Employee import failed. No rows were added.' : status === 'saved' ? 'Employee import completed.' : ''}</p>
    </section>
  )
}

function AdminDirectory({ authentication, branchId, clearBranch }) {
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [revision, setRevision] = useState(0)
  const listing = useLoad(
    (signal) => readEmployees(authentication, branchId, {
      signal,
      ...(appliedSearch ? { search: appliedSearch } : {}),
    }),
    [authentication, branchId, appliedSearch, revision],
  )
  const choices = useLoad(
    (signal) => Promise.all([
      readAllDepartments(authentication, branchId, { signal }),
      readAllEmployees(authentication, branchId, { signal }),
    ]),
    [authentication, branchId, revision],
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
    [authentication, branchId, selectedId, revision],
  )

  const saved = (employee) => {
    if (employee?.id) setSelectedId(employee.id)
    setRevision((value) => value + 1)
  }

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
      {choices.status === 'ready' && (
        <EmployeeCreateForm
          authentication={authentication}
          branchId={branchId}
          departments={choices.data[0]}
          managers={choices.data[1]}
          onSaved={saved}
        />
      )}
      <EmployeeImportPanel authentication={authentication} branchId={branchId} onSaved={saved} />
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
          <EmployeeEditor
            key={`${detail.data[0].id}-${detail.data[0].updatedAt}`}
            authentication={authentication}
            branchId={branchId}
            employee={detail.data[0]}
            onSaved={saved}
          />
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

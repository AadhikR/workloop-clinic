import { useEffect, useState } from 'react'
import PortalDialog from './PortalDialog.jsx'
import Offboarding from './Offboarding.jsx'
import { EmployeeRecordsEditor } from './RecordsBenefits.jsx'

import { HttpClientError } from './http.js'
import {
  archiveEmployee,
  changeEmployeeStatus,
  confirmEmployeeProbation,
  createEmployee,
  extendEmployeeProbation,
  importEmployees,
  readBranchJobHistory,
  readDirectReports,
  readEmployee,
  readEmployeeJobHistory,
  readAllEmployees,
  readEmployees,
  readEmployeeSelf,
  readEmployeePortalRole,
  setEmployeePortalRole,
  saveEmployeeProfile,
  terminateEmployeeProbation,
  updateEmployeeSelfContact,
} from './employeeApi.js'
import { parseEmployeeCsv } from './employeeCsv.js'
import { readAllDepartments } from './departmentApi.js'
import { downloadEmployees, downloadEmployeeTemplate } from './outputApi.js'
import { saveDownload } from './outputDelivery.js'
import { readEmployeeDocuments } from './recordsBenefitsApi.js'

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
  if (onSelect) return <div className="table-wrap employee-directory-table"><table><thead><tr><th>Employee</th><th>Job title</th><th>Department</th><th>Status</th><th aria-label="Actions" /></tr></thead><tbody>{employees.map((employee) => <tr key={employee.id}><td><button type="button" className="employee-name-link" onClick={() => onSelect(employee.id)}>{employee.name}</button><small>{employee.empNo}</small></td><td>{employee.jobTitle || 'Not assigned'}</td><td>{employee.department || 'Not assigned'}</td><td><span className={`badge ${employee.active ? 'badge-green' : 'badge-gray'}`}>{employee.employmentStatus.replaceAll('_', ' ')}</span></td><td><button type="button" className="btn btn-ghost btn-sm" onClick={() => onSelect(employee.id)}>View</button></td></tr>)}</tbody></table></div>
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

const employeeTabs = [
  ['personal', 'Personal'],
  ['job', 'Job and contract'],
  ['salary', 'Salary and bank'],
  ['compliance', 'UAE compliance'],
  ['documents', 'Documents'],
  ['insurance', 'Insurance'],
  ['contracts', 'Contracts'],
]
const profileFields = [
  'empNo', 'name', 'photoUrl', 'molId', 'personalEmail', 'phone',
  'homeCountryAddress', 'emergencyContactName', 'emergencyContactRelationship',
  'emergencyContactPhone', 'bankName', 'bankRoutingCode', 'bankAccountHolder', 'iban',
  'nationality', 'visaNumber', 'passportNumber', 'emiratesId', 'labourCardNumber',
  'sponsoringEntity', 'freeZoneName', 'nafisRegistrationNo', 'licenceAuthority', 'licenceNumber',
]
const profileDateFields = [
  'dateOfBirth', 'employmentStartDate', 'visaExpiry', 'passportExpiry',
  'emiratesIdExpiry', 'labourCardExpiry', 'licenceExpiry',
]
const salaryFields = [
  'basicSalary', 'allowance', 'housingAllowance', 'transportAllowance', 'otherAllowances',
]

function editorState(employee) {
  const fields = [...profileFields, 'jobTitle', 'department', 'otherAllowancesLabel']
  const result = Object.fromEntries(fields.map((field) => [field, employee[field] ?? '']))
  for (const field of profileDateFields) result[field] = employee[field] ?? ''
  for (const field of salaryFields) result[field] = employee[field]
  return {
    ...result,
    gender: employee.gender,
    maritalStatus: employee.maritalStatus,
    visaType: employee.visaType,
    workLocationType: employee.workLocationType,
    reportingManagerId: employee.reportingManagerId ?? '',
  }
}

function profileInputs(form, change, definitions) {
  return definitions.map(([label, field, kind = 'text', required = false]) => <label key={field}>{label}<input
    required={required}
    type={kind === 'date' ? 'date' : undefined}
    inputMode={kind === 'decimal' ? 'decimal' : undefined}
    value={form[field]}
    onChange={change(field)}
  /></label>)
}

function EmployeeEditor({ account, authentication, branchId, employee, employees, departments, history, onSaved }) {
  const [form, setForm] = useState(() => editorState(employee))
  const [activeTab, setActiveTab] = useState('personal')
  const [reason, setReason] = useState('Profile details updated')
  const [status, setStatus] = useState('idle')
  const tabs = employee?.id ? employeeTabs : employeeTabs.slice(0, 4)
  const change = (field) => (event) => setForm((current) => ({
    ...current,
    [field]: event.target.value,
  }))
  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    try {
      const profile = {
        expectedUpdatedAt: employee.updatedAt,
        ...Object.fromEntries([...profileFields, 'gender', 'maritalStatus', 'visaType', 'workLocationType'].map((field) => [field, form[field]])),
        ...Object.fromEntries(profileDateFields.map((field) => [field, form[field] || null])),
      }
      const updated = await saveEmployeeProfile(authentication, branchId, employee.id, {
        expectedUpdatedAt: employee.updatedAt,
        reason: reason.trim(),
        profile,
        jobTitle: form.jobTitle,
        department: form.department,
        reportingManagerId: form.reportingManagerId || null,
        ...Object.fromEntries(salaryFields.map((field) => [field, form[field]])),
        otherAllowancesLabel: form.otherAllowancesLabel,
      }, { idempotencyKey: crypto.randomUUID() })
      setStatus('saved')
      onSaved(updated)
    } catch {
      setStatus('error')
    }
  }
  return (
    <div className="employee-editor">
      <div className="tabs" role="tablist" aria-label="Employee profile tabs">
        {tabs.map(([id, label]) => <button key={id} type="button" role="tab" className={`tab-btn${activeTab === id ? ' active' : ''}`} aria-selected={activeTab === id} onClick={() => setActiveTab(id)}>{label}</button>)}
      </div>
      {['documents', 'insurance', 'contracts'].includes(activeTab) ? (
        <EmployeeRecordsEditor account={account} authentication={authentication} branchId={branchId} employeeId={employee.id} view={activeTab} />
      ) : <form className="employee-admin-form" onSubmit={submit} data-employee-edit-form>
        {activeTab === 'personal' && <div className="employee-form-grid">
          {profileInputs(form, change, [
            ['Employee number', 'empNo'], ['Name', 'name', 'text', true], ['Photo URL', 'photoUrl'],
            ['Personal email', 'personalEmail'], ['Phone', 'phone'], ['Date of birth', 'dateOfBirth', 'date'],
            ['Home-country address', 'homeCountryAddress'], ['Emergency contact', 'emergencyContactName'],
            ['Emergency relationship', 'emergencyContactRelationship'], ['Emergency phone', 'emergencyContactPhone'],
          ])}
          <label>Work email<input readOnly value={employee.workEmail} /></label>
          <label>Gender<select value={form.gender ?? ''} onChange={change('gender')}><option value="">Not specified</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select></label>
          <label>Marital status<select value={form.maritalStatus ?? ''} onChange={change('maritalStatus')}><option value="">Not specified</option><option value="single">Single</option><option value="married">Married</option><option value="divorced">Divorced</option><option value="widowed">Widowed</option></select></label>
        </div>}
        {activeTab === 'job' && <>
          <div className="employee-form-grid">
            {profileInputs(form, change, [['Job title', 'jobTitle', 'text', true], ['Employment start date', 'employmentStartDate', 'date']])}
            <label>Department<select required value={form.department} onChange={change('department')}><option value="">Choose department</option>{departments.map((item) => <option key={item.id}>{item.name}</option>)}</select></label>
            <label>Reporting manager<select value={form.reportingManagerId} onChange={change('reportingManagerId')}><option value="">No manager</option>{employees.filter((item) => item.id !== employee.id && item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Employment status<input readOnly value={employee.employmentStatus.replaceAll('_', ' ')} /></label>
            <label>Probation end date<input readOnly value={employee.probationEndDate ?? ''} /></label>
          </div>
          <section aria-labelledby="job-history-title"><h5 id="job-history-title">Job history</h5>{history.length ? <ul>{history.map((entry) => <li key={entry.id}>{entry.changeType.replaceAll('_', ' ')}: {entry.oldValue} to {entry.newValue}. {entry.reason}</li>)}</ul> : <p>No recorded changes.</p>}</section>
        </>}
        {activeTab === 'salary' && <div className="employee-form-grid">
          {profileInputs(form, change, [
            ['Basic salary', 'basicSalary', 'decimal'], ['Allowance', 'allowance', 'decimal'],
            ['Housing allowance', 'housingAllowance', 'decimal'], ['Transport allowance', 'transportAllowance', 'decimal'],
            ['Other allowances', 'otherAllowances', 'decimal'], ['Other allowance label', 'otherAllowancesLabel'],
            ['Bank name', 'bankName'], ['Routing code', 'bankRoutingCode'],
            ['Account holder', 'bankAccountHolder'], ['IBAN', 'iban'],
          ])}
        </div>}
        {activeTab === 'compliance' && <div className="employee-form-grid">
          {profileInputs(form, change, [
            ['MOL ID', 'molId', 'text', true], ['Nationality', 'nationality'], ['Visa number', 'visaNumber'],
            ['Visa expiry', 'visaExpiry', 'date'], ['Passport number', 'passportNumber'],
            ['Passport expiry', 'passportExpiry', 'date'], ['Emirates ID', 'emiratesId'],
            ['Emirates ID expiry', 'emiratesIdExpiry', 'date'], ['Labour card number', 'labourCardNumber'],
            ['Labour card expiry', 'labourCardExpiry', 'date'], ['Sponsoring entity', 'sponsoringEntity'],
            ['Free-zone name', 'freeZoneName'], ['Nafis registration number', 'nafisRegistrationNo'],
            ['Licence authority', 'licenceAuthority'], ['Licence number', 'licenceNumber'],
            ['Licence expiry', 'licenceExpiry', 'date'],
          ])}
          <label>Visa type<select value={form.visaType ?? ''} onChange={change('visaType')}><option value="">Not specified</option><option value="employment_visa">Employment visa</option><option value="investor_visa">Investor visa</option><option value="dependent_visa">Dependent visa</option><option value="tourist_temp">Tourist (temporary)</option><option value="exempt">Exempt</option></select></label>
          <label>Work location<select value={form.workLocationType} onChange={change('workLocationType')}><option value="mainland">Mainland</option><option value="free_zone">Free zone</option></select></label>
        </div>}
        <label>Reason for profile changes<textarea required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button type="submit" disabled={status === 'saving'}>Save employee profile</button>
        <p role="status" data-employee-edit-status={status}>{status === 'error' ? 'Employee profile could not be saved.' : status === 'saved' ? 'Employee profile saved.' : ''}</p>
      </form>}
      {activeTab === 'job' && <Offboarding account={account} authentication={authentication} branchId={branchId} selectedEmployeeId={employee.id} />}
    </div>
  )
}

function ReportReassignments({ reports, managers, replacements, onChange }) {
  if (!reports.length) return null
  return (
    <fieldset>
      <legend>Reassign every direct report</legend>
      {reports.map((report) => (
        <label key={report.id}>
          {report.name}
          <select
            required
            value={replacements[report.id] ?? ''}
            onChange={(event) => onChange(report.id, event.target.value)}
          >
            <option value="">Choose a new manager</option>
            {managers
              .filter((manager) => manager.id !== report.id)
              .map((manager) => (
                <option key={manager.id} value={manager.id}>{manager.name}</option>
              ))}
          </select>
        </label>
      ))}
    </fieldset>
  )
}

function reassignmentBody(reports, replacements) {
  return reports.map((report) => {
    const newManagerId = replacements[report.id]
    if (!newManagerId) throw new Error('Every direct report requires a replacement manager')
    return {
      employeeId: report.id,
      newManagerId,
      expectedUpdatedAt: report.updatedAt,
    }
  })
}

function EmployeeLifecyclePanel({
  authentication,
  branchId,
  employee,
  employees,
  onSaved,
}) {
  const [action, setAction] = useState('status')
  const [reason, setReason] = useState('')
  const [value, setValue] = useState('')
  const [replacements, setReplacements] = useState({})
  const [status, setStatus] = useState('idle')
  const reports = employees.filter((item) => item.reportingManagerId === employee.id)
  const eligibleManagers = employees.filter((item) => (
    item.id !== employee.id
    && item.active
    && item.employmentStatus !== 'terminated'
  ))
  const needsReassignments = action === 'archive'
    || action === 'probation-termination'
    || action === 'status' && value === 'terminated'
  const replace = (reportId, managerId) => setReplacements((current) => ({
    ...current,
    [reportId]: managerId,
  }))
  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    const shared = { expectedUpdatedAt: employee.updatedAt, reason: reason.trim() }
    const options = { idempotencyKey: crypto.randomUUID() }
    try {
      let updated
      if (action === 'status') {
        updated = await changeEmployeeStatus(authentication, branchId, employee.id, {
          ...shared,
          employmentStatus: value,
          ...(value === 'terminated' ? {
            reportReassignments: reassignmentBody(reports, replacements),
          } : {}),
        }, options)
      } else if (action === 'probation-confirmation') {
        updated = await confirmEmployeeProbation(
          authentication, branchId, employee.id, shared, options,
        )
      } else if (action === 'probation-extension') {
        updated = await extendEmployeeProbation(authentication, branchId, employee.id, {
          ...shared, probationEndDate: value,
        }, options)
      } else if (action === 'probation-termination') {
        updated = await terminateEmployeeProbation(authentication, branchId, employee.id, {
          ...shared, reportReassignments: reassignmentBody(reports, replacements),
        }, options)
      } else {
        updated = await archiveEmployee(authentication, branchId, employee.id, {
          ...shared, reportReassignments: reassignmentBody(reports, replacements),
        }, options)
      }
      setReason('')
      setValue('')
      setReplacements({})
      setStatus('saved')
      onSaved(updated)
    } catch {
      setStatus('error')
    }
  }
  return (
    <form className="employee-admin-form" onSubmit={submit} data-employee-lifecycle-form>
      <h5>Employee lifecycle</h5>
      <label>
        Workflow
        <select value={action} onChange={(event) => { setAction(event.target.value); setValue('') }}>
          <option value="status">Change employment status</option>
          <option value="probation-confirmation">Confirm probation</option>
          <option value="probation-extension">Extend probation</option>
          <option value="probation-termination">Terminate during probation</option>
          <option value="archive">Archive employee</option>
        </select>
      </label>
      {action === 'status' && (
        <label>
          New status
          <select required value={value} onChange={(event) => setValue(event.target.value)}>
            <option value="">Choose status</option>
            <option value="active">Active</option>
            <option value="probation">Probation</option>
            <option value="on_leave">On leave</option>
            <option value="terminated">Terminated</option>
          </select>
        </label>
      )}
      {action === 'probation-extension' && (
        <label>
          New probation end date
          <input required type="date" value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
      )}
      <label>
        Reason
        <textarea required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
      {needsReassignments && (
        <ReportReassignments
          reports={reports}
          managers={eligibleManagers}
          replacements={replacements}
          onChange={replace}
        />
      )}
      <button type="submit" disabled={status === 'saving'}>Run workflow</button>
      <p role="status" data-employee-lifecycle-status={status}>
        {status === 'error' ? 'The workflow could not be completed.' : status === 'saved' ? 'Employee workflow completed.' : ''}
      </p>
    </form>
  )
}

function EmployeePortalRolePanel({ authentication, branchId, employee, employees, onSaved }) {
  const [revision, setRevision] = useState(0)
  const [status, setStatus] = useState('idle')
  const [replacements, setReplacements] = useState({})
  const portal = useLoad(
    (signal) => readEmployeePortalRole(authentication, branchId, employee.id, { signal }),
    [authentication, branchId, employee.id, revision],
  )
  const reports = employees.filter((item) => item.reportingManagerId === employee.id)
  const managers = employees.filter((item) => (
    item.id !== employee.id && item.active && item.employmentStatus !== 'terminated'
  ))
  const changeRole = async () => {
    if (portal.status !== 'ready' || !portal.data.activated) return
    setStatus('saving')
    const role = portal.data.role === 'manager' ? 'employee' : 'manager'
    try {
      await setEmployeePortalRole(authentication, branchId, employee.id, {
        role,
        expectedRole: portal.data.role,
        ...(role === 'employee' ? {
          reportReassignments: reassignmentBody(reports, replacements),
        } : {}),
      }, { idempotencyKey: crypto.randomUUID() })
      setStatus('saved')
      setReplacements({})
      setRevision((value) => value + 1)
      onSaved()
    } catch {
      setStatus('error')
    }
  }
  return (
    <section className="employee-portal-role" aria-label="Employee portal role">
      <h5>Portal role</h5>
      {portal.status === 'loading' && <p>Loading portal role...</p>}
      {portal.status === 'error' && <p role="status">Portal role is unavailable.</p>}
      {portal.status === 'ready' && !portal.data.activated && (
        <p>This employee has no eligible activated portal account.</p>
      )}
      {portal.status === 'ready' && portal.data.activated && (
        <>
          <p>Current role: {portal.data.role}</p>
          {portal.data.role === 'manager' && (
            <ReportReassignments
              reports={reports}
              managers={managers}
              replacements={replacements}
              onChange={(reportId, managerId) => setReplacements((current) => ({
                ...current, [reportId]: managerId,
              }))}
            />
          )}
          <button type="button" onClick={changeRole} disabled={status === 'saving'}>
            Change to {portal.data.role === 'manager' ? 'employee' : 'manager'}
          </button>
        </>
      )}
      <p role="status" data-employee-portal-role-status={status}>
        {status === 'error' ? 'Portal role could not be changed.' : status === 'saved' ? 'Portal role changed.' : ''}
      </p>
    </section>
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

function AdminDirectory({ account, authentication, branchId, clearBranch }) {
  const [dialog, setDialog] = useState(null)
  const [directoryView, setDirectoryView] = useState('list')
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
  const directoryDetails = useLoad(
    async (signal) => {
      const employees = await readAllEmployees(authentication, branchId, { signal })
      const details = await Promise.all(employees.map(async (employee) => {
        const [record, documents] = await Promise.all([
          readEmployee(authentication, branchId, employee.id, { signal }),
          readEmployeeDocuments(authentication, branchId, employee.id),
        ])
        return { ...record, documentExpiries: documents.items.map((item) => item.expiryDate).filter(Boolean) }
      }))
      return [details, Date.now() + 90 * 24 * 60 * 60 * 1000]
    },
    [authentication, branchId, revision],
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
    setDialog(null)
    if (employee?.id) setSelectedId(employee.id)
    setRevision((value) => value + 1)
  }

  const allDetails = directoryDetails.status === 'ready' ? directoryDetails.data[0] : []
  const expiryThreshold = directoryDetails.status === 'ready' ? directoryDetails.data[1] : 0
  const expiring = allDetails.filter((employee) => {
    const dates = [employee.visaExpiry, employee.passportExpiry, employee.emiratesIdExpiry, employee.labourCardExpiry, employee.licenceExpiry, ...employee.documentExpiries].filter(Boolean)
    return dates.some((value) => new Date(`${value}T00:00:00Z`).valueOf() <= expiryThreshold)
  })
  const terminated = allDetails.filter((employee) => employee.employmentStatus === 'terminated')
  const visibleEmployees = directoryView === 'expiry'
    ? expiring
    : directoryView === 'terminated'
      ? terminated
      : listing.status === 'ready' ? listing.data.data : []

  useEffect(() => {
    if (
      listing.status === 'error'
      && listing.error instanceof HttpClientError
      && listing.error.code === 'resource_not_found'
    ) clearBranch()
  }, [clearBranch, listing])

  return (
    <section className="employee-directory" aria-label="Employee directory">
      <div className="employee-module-toolbar"><h3>Employees</h3><div className="actions"><button type="button" className="btn btn-outline" onClick={async () => saveDownload(await downloadEmployees(authentication, branchId))}>Export CSV</button><button type="button" className="btn btn-outline" onClick={() => setDialog('import')}>Import employees</button><button type="button" className="btn btn-primary" disabled={choices.status !== 'ready'} onClick={() => setDialog('create')}>Add Employee</button></div></div>
      <div className="employee-summary-tabs" role="tablist" aria-label="Employee summaries">
        <button type="button" role="tab" aria-selected={directoryView === 'list'} onClick={() => setDirectoryView('list')}>Employee list <strong>{allDetails.filter((item) => item.active).length}</strong></button>
        <button type="button" role="tab" aria-selected={directoryView === 'expiry'} onClick={() => setDirectoryView('expiry')}>Document expiry <strong>{expiring.length}</strong></button>
        <button type="button" role="tab" aria-selected={directoryView === 'terminated'} onClick={() => setDirectoryView('terminated')}>Terminated employees <strong>{terminated.length}</strong></button>
      </div>
      {dialog && <PortalDialog labelledBy="employee-dialog-title" onClose={() => setDialog(null)}><div className="modal-header"><h3 id="employee-dialog-title">{dialog === 'create' ? 'Add Employee' : 'Import employees'}</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close employee form" onClick={() => setDialog(null)}>×</button></div><div className="modal-body">{dialog === 'create' && choices.status === 'ready' ? <EmployeeCreateForm authentication={authentication} branchId={branchId} departments={choices.data[0]} managers={choices.data[1]} onSaved={saved} /> : <><p><button type="button" className="btn btn-outline btn-sm" onClick={async () => saveDownload(await downloadEmployeeTemplate(authentication, branchId))}>Download import template</button></p><EmployeeImportPanel authentication={authentication} branchId={branchId} onSaved={saved} /></>}</div></PortalDialog>}
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
        visibleEmployees.length
          ? <EmployeeRows employees={visibleEmployees} onSelect={setSelectedId} />
          : <p>No employees match this branch query.</p>
      )}
      {detail.status === 'ready' && detail.data && (
        <PortalDialog labelledBy="employee-profile-dialog-title" onClose={() => setSelectedId(null)}>
          <div className="modal-header"><div><h3 id="employee-profile-dialog-title">{detail.data[0].name}</h3><p>{detail.data[0].empNo} · {detail.data[0].employmentStatus.replaceAll('_', ' ')}</p></div><button type="button" className="btn btn-ghost btn-icon" aria-label="Close employee profile" onClick={() => setSelectedId(null)}>×</button></div>
          <div className="modal-body employee-profile-modal">
          {choices.status === 'ready' && <>
          <EmployeeEditor
            key={detail.data[0].id}
            account={account}
            authentication={authentication}
            branchId={branchId}
            employee={detail.data[0]}
            employees={choices.data[1]}
            departments={choices.data[0]}
            history={detail.data[1].data}
            onSaved={saved}
          />
          <details><summary>Lifecycle and portal access</summary>
              <EmployeeLifecyclePanel
                key={`lifecycle-${detail.data[0].id}-${detail.data[0].updatedAt}`}
                authentication={authentication}
                branchId={branchId}
                employee={detail.data[0]}
                employees={choices.data[1]}
                onSaved={saved}
              />
              <EmployeePortalRolePanel
                key={`portal-${detail.data[0].id}`}
                authentication={authentication}
                branchId={branchId}
                employee={detail.data[0]}
                employees={choices.data[1]}
                onSaved={saved}
              />
          </details>
          </>}
          </div>
        </PortalDialog>
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

function EmployeeSelfContactForm({ authentication, employee, onSaved }) {
  const [form, setForm] = useState({
    phone: employee.phone,
    personalEmail: employee.personalEmail,
    emergencyContactName: employee.emergencyContactName,
    emergencyContactPhone: employee.emergencyContactPhone,
  })
  const [status, setStatus] = useState('idle')
  const change = (field) => (event) => setForm((current) => ({
    ...current, [field]: event.target.value,
  }))
  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    try {
      const updated = await updateEmployeeSelfContact(authentication, {
        ...form, expectedUpdatedAt: employee.updatedAt,
      })
      setStatus('saved')
      onSaved(updated)
    } catch {
      setStatus('error')
    }
  }
  return (
    <form className="employee-admin-form" onSubmit={submit} data-employee-self-contact-form>
      <h4>Contact details</h4>
      <div className="employee-form-grid">
        <label>Phone<input value={form.phone} onChange={change('phone')} /></label>
        <label>Personal email<input type="email" value={form.personalEmail} onChange={change('personalEmail')} /></label>
        <label>Emergency contact<input value={form.emergencyContactName} onChange={change('emergencyContactName')} /></label>
        <label>Emergency phone<input value={form.emergencyContactPhone} onChange={change('emergencyContactPhone')} /></label>
      </div>
      <button type="submit" disabled={status === 'saving'}>Save contact details</button>
      <p role="status" data-employee-self-contact-status={status}>
        {status === 'error' ? 'Contact details could not be saved.' : status === 'saved' ? 'Contact details saved.' : ''}
      </p>
    </form>
  )
}

function StaffDirectory({ account, authentication }) {
  const [revision, setRevision] = useState(0)
  const self = useLoad(
    (signal) => readEmployeeSelf(authentication, { signal }),
    [authentication, revision],
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
        <>
          <dl className="employee-self">
            <div><dt>Name</dt><dd>{self.data.name}</dd></div>
            <div><dt>Job title</dt><dd>{self.data.jobTitle || 'Not assigned'}</dd></div>
            <div><dt>Department</dt><dd>{self.data.department || 'Not assigned'}</dd></div>
            <div><dt>Manager</dt><dd>{self.data.reportingManager?.name ?? 'Not assigned'}</dd></div>
          </dl>
          <EmployeeSelfContactForm
            key={self.data.updatedAt}
            authentication={authentication}
            employee={self.data}
            onSaved={() => setRevision((value) => value + 1)}
          />
        </>
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
        account={account}
        authentication={authentication}
        branchId={branchId}
        clearBranch={clearBranch}
      />
    )
    : <StaffDirectory account={account} authentication={authentication} />
}

import { useEffect, useState } from 'react'
import { readAllEmployees, readDirectReports } from './employeeApi.js'

export default function EmployeePicker({ authentication, branchId, value, onChange, role = 'admin', required = false, label = 'Employee', emptyLabel = 'Choose employee' }) {
  const [state, setState] = useState({ status: 'loading', employees: [] })
  const matches = state.authentication === authentication && state.branchId === branchId && state.role === role
  const status = matches ? state.status : 'loading'
  const employees = matches ? state.employees : []
  useEffect(() => {
    const controller = new AbortController()
    const pending = role === 'manager'
      ? readDirectReports(authentication, { signal: controller.signal }).then((result) => result.data)
      : readAllEmployees(authentication, branchId, { signal: controller.signal, sort: 'name' })
    pending.then((items) => {
      if (controller.signal.aborted) return
      setState({ authentication, branchId, role, employees: items, status: 'ready' })
    }).catch(() => { if (!controller.signal.aborted) setState({ authentication, branchId, role, employees: [], status: 'unavailable' }) })
    return () => controller.abort()
  }, [authentication, branchId, role])
  return <label className="employee-picker">{label}<select required={required} value={value} disabled={status !== 'ready'} onChange={(event) => onChange(event.target.value)}><option value="">{status === 'loading' ? 'Loading employees...' : status === 'unavailable' ? 'Employees unavailable' : emptyLabel}</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}{employee.empNo ? ` · ${employee.empNo}` : ''}</option>)}</select></label>
}

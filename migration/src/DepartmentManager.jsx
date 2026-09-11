import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  createDepartment,
  createStaffingRule,
  deleteDepartment,
  deleteStaffingRule,
  departmentSnapshot,
  readAllDepartments,
  readAllStaffingRules,
  staffingRuleSnapshot,
  updateDepartment,
  updateStaffingRule,
} from './departmentApi.js'
import { readAllEmployees } from './employeeApi.js'
import { HttpClientError } from './http.js'

const emptyDepartment = {
  name: '', parentId: null, headEmployeeId: null, color: '#6366f1', description: '', sortOrder: 0,
}
const emptyRule = {
  department: '', shiftCategory: 'morning', minStaff: 1, effectiveFrom: null, effectiveTo: null,
}

function requestError(error) {
  if (!(error instanceof HttpClientError)) return 'The request failed. No changes were saved.'
  if (error.code === 'state_conflict') return 'This record changed. The current values have been reloaded.'
  if (error.code === 'department_conflict') return 'The department name, hierarchy, head, or retained use blocks this change.'
  if (error.code === 'staffing_rule_conflict') return 'The department or an existing category rule blocks this change.'
  if (error.code === 'idempotency_in_progress') return 'The rename is still running. Retry in a moment.'
  return error.message
}

function hierarchyRows(departments) {
  const children = new Map()
  for (const department of departments) {
    const key = department.parentId ?? 'root'
    children.set(key, [...(children.get(key) ?? []), department])
  }
  const rows = []
  const seen = new Set()
  const visit = (parentId, depth) => {
    for (const department of children.get(parentId) ?? []) {
      if (seen.has(department.id)) continue
      seen.add(department.id)
      rows.push({ department, depth })
      visit(department.id, depth + 1)
    }
  }
  visit('root', 0)
  for (const department of departments) {
    if (!seen.has(department.id)) rows.push({ department, depth: 0 })
  }
  return rows
}

function DepartmentEditor({ departments, employees, selected, onCancel, onSaved, authentication, branchId }) {
  const [draft, setDraft] = useState(selected ?? emptyDepartment)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const field = (name) => (event) => setDraft({
    ...draft,
    [name]: ['parentId', 'headEmployeeId'].includes(name)
      ? event.target.value || null
      : name === 'sortOrder' ? Number(event.target.value) : event.target.value,
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      if (selected) {
        await updateDepartment(authentication, branchId, selected.id, {
          name: draft.name,
          parentId: draft.parentId,
          headEmployeeId: draft.headEmployeeId,
          color: draft.color,
          description: draft.description,
          sortOrder: draft.sortOrder,
          expected: departmentSnapshot(selected),
        }, { idempotencyKey: crypto.randomUUID() })
      } else {
        await createDepartment(authentication, branchId, draft)
      }
      if (!selected) setDraft(emptyDepartment)
      await onSaved({
        keepSelection: Boolean(selected),
        notice: selected ? 'Department saved.' : 'Department created.',
      })
    } catch (error) {
      setMessage(requestError(error))
      await onSaved({ keepSelection: true }).catch(() => {})
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setSaving(true)
    setMessage('')
    try {
      await deleteDepartment(authentication, branchId, selected)
      await onSaved({ notice: 'Department deleted.' })
    } catch (error) {
      setMessage(requestError(error))
      await onSaved({ keepSelection: true }).catch(() => {})
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="settings-form department-editor" onSubmit={submit}>
      <h4>{selected ? `Edit ${selected.name}` : 'New department'}</h4>
      <label>Name<input value={draft.name} maxLength={200} required onChange={field('name')} /></label>
      <label>Parent
        <select value={draft.parentId ?? ''} onChange={field('parentId')}>
          <option value="">No parent</option>
          {departments.filter((item) => item.id !== selected?.id).map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </label>
      <label>Department head
        <select value={draft.headEmployeeId ?? ''} onChange={field('headEmployeeId')}>
          <option value="">No head</option>
          {employees.filter((employee) => employee.active && employee.employmentStatus !== 'terminated').map((employee) => (
            <option key={employee.id} value={employee.id}>{employee.name}</option>
          ))}
        </select>
      </label>
      <label>Color<input type="color" value={draft.color} onChange={field('color')} /></label>
      <label>Description<textarea value={draft.description} maxLength={2000} onChange={field('description')} /></label>
      <label>Sort order<input type="number" value={draft.sortOrder} onChange={field('sortOrder')} /></label>
      <div className="settings-actions">
        <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save department'}</button>
        {selected && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}
        {selected && <button type="button" className="danger" disabled={saving} onClick={remove}>Delete</button>}
      </div>
      {message && <p role="status">{message}</p>}
    </form>
  )
}

function StaffingEditor({ authentication, branchId, departments, rules, selected, onSelect, onSaved }) {
  const [draft, setDraft] = useState(selected ?? { ...emptyRule, department: departments[0]?.name ?? '' })
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const field = (name) => (event) => setDraft({
    ...draft,
    [name]: name === 'minStaff' ? Number(event.target.value) : event.target.value || null,
  })
  const values = () => ({
    department: draft.department,
    shiftCategory: draft.shiftCategory,
    minStaff: draft.minStaff,
    effectiveFrom: draft.effectiveFrom,
    effectiveTo: draft.effectiveTo,
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      if (selected) {
        await updateStaffingRule(authentication, branchId, selected, {
          ...values(), expected: staffingRuleSnapshot(selected),
        })
      } else {
        await createStaffingRule(authentication, branchId, values())
      }
      if (!selected) {
        setDraft({ ...emptyRule, department: departments[0]?.name ?? '' })
      }
      await onSaved({
        keepSelection: Boolean(selected),
        notice: selected ? 'Staffing rule saved.' : 'Staffing rule created.',
      })
    } catch (error) {
      setMessage(requestError(error))
      await onSaved({ keepSelection: true }).catch(() => {})
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setSaving(true)
    try {
      await deleteStaffingRule(authentication, branchId, selected)
      await onSaved({ notice: 'Staffing rule deleted.' })
    } catch (error) {
      setMessage(requestError(error))
      await onSaved({ keepSelection: true }).catch(() => {})
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="staffing-editor">
      <ul className="staffing-list">
        {rules.map((rule) => (
          <li key={rule.id}>
            <button type="button" className="secondary" onClick={() => onSelect(rule)}>
              {rule.department}: {rule.shiftCategory}, minimum {rule.minStaff}
            </button>
          </li>
        ))}
      </ul>
      <form className="settings-form" onSubmit={submit}>
        <h4>{selected ? 'Edit staffing rule' : 'New staffing rule'}</h4>
        <label>Department
          <select value={draft.department} required onChange={field('department')}>
            {departments.map((department) => (
              <option key={department.id} value={department.name}>{department.name}</option>
            ))}
          </select>
        </label>
        <label>Shift category
          <select value={draft.shiftCategory} onChange={field('shiftCategory')}>
            {['morning', 'afternoon', 'night', 'flexible'].map((category) => (
              <option key={category} value={category}>{category}</option>
            ))}
          </select>
        </label>
        <label>Minimum staff<input type="number" min="0" value={draft.minStaff} onChange={field('minStaff')} /></label>
        <label>Effective from<input type="date" value={draft.effectiveFrom ?? ''} onChange={field('effectiveFrom')} /></label>
        <label>Effective to<input type="date" value={draft.effectiveTo ?? ''} onChange={field('effectiveTo')} /></label>
        <div className="settings-actions">
          <button type="submit" disabled={saving || departments.length === 0}>{saving ? 'Saving...' : 'Save rule'}</button>
          {selected && <button type="button" className="secondary" onClick={() => onSelect(null)}>Cancel</button>}
          {selected && <button type="button" className="danger" disabled={saving} onClick={remove}>Delete</button>}
        </div>
        {message && <p role="status">{message}</p>}
      </form>
    </div>
  )
}

export default function DepartmentManager({ authentication, branchId, clearBranch }) {
  const [state, setState] = useState({ status: 'loading', departments: [], employees: [], rules: [] })
  const [notice, setNotice] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState(null)
  const [selectedRule, setSelectedRule] = useState(null)

  const load = useCallback(async ({ keepSelection = false, notice: nextNotice = '' } = {}) => {
    try {
      const [departments, employees, rules] = await Promise.all([
        readAllDepartments(authentication, branchId),
        readAllEmployees(authentication, branchId),
        readAllStaffingRules(authentication, branchId),
      ])
      setState({ status: 'ready', departments, employees, rules })
      setNotice(nextNotice)
      if (!keepSelection) {
        setSelectedDepartment(null)
        setSelectedRule(null)
      } else {
        setSelectedDepartment((current) => departments.find((item) => item.id === current?.id) ?? null)
        setSelectedRule((current) => rules.find((item) => item.id === current?.id) ?? null)
      }
    } catch (error) {
      if (error instanceof HttpClientError && error.code === 'resource_not_found') clearBranch()
      else setState((current) => ({ ...current, status: 'error' }))
      throw error
    }
  }, [authentication, branchId, clearBranch])

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readAllDepartments(authentication, branchId, { signal: controller.signal }),
      readAllEmployees(authentication, branchId, { signal: controller.signal }),
      readAllStaffingRules(authentication, branchId, { signal: controller.signal }),
    ]).then(([departments, employees, rules]) => {
      setState({ status: 'ready', departments, employees, rules })
    }).catch((error) => {
      if (controller.signal.aborted) return
      if (error instanceof HttpClientError && error.code === 'resource_not_found') clearBranch()
      else setState((current) => ({ ...current, status: 'error' }))
    })
    return () => controller.abort()
  }, [authentication, branchId, clearBranch])

  const rows = useMemo(() => hierarchyRows(state.departments), [state.departments])
  if (state.status === 'loading') return <p>Loading departments...</p>
  if (state.status === 'error') return <p role="status">Department settings are unavailable.</p>

  return (
    <section className="department-manager" aria-label="Departments and staffing rules">
      {notice && <p role="status">{notice}</p>}
      <h3>Departments</h3>
      <div className="department-layout">
        <ul className="department-tree">
          {rows.map(({ department, depth }) => (
            <li key={department.id} style={{ paddingInlineStart: `${depth * 1.25}rem` }}>
              <button type="button" className="secondary" onClick={() => setSelectedDepartment(department)}>
                <span className="department-swatch" style={{ background: department.color }} />
                {department.name}
              </button>
            </li>
          ))}
        </ul>
        <DepartmentEditor
          key={selectedDepartment ? JSON.stringify(departmentSnapshot(selectedDepartment)) : 'new'}
          authentication={authentication}
          branchId={branchId}
          departments={state.departments}
          employees={state.employees}
          selected={selectedDepartment}
          onCancel={() => setSelectedDepartment(null)}
          onSaved={load}
        />
      </div>
      <h3>Staffing rules</h3>
      <StaffingEditor
        key={selectedRule
          ? JSON.stringify(staffingRuleSnapshot(selectedRule))
          : `new:${state.departments[0]?.id ?? 'none'}`}
        authentication={authentication}
        branchId={branchId}
        departments={state.departments}
        rules={state.rules}
        selected={selectedRule}
        onSelect={setSelectedRule}
        onSaved={load}
      />
    </section>
  )
}

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
import { readBranch } from './organizationApi.js'
import { ConfirmDialog, FilterTabs, FormDialog, PortalTable } from './PortalUi.jsx'

const emptyDepartment = {
  name: '', parentId: null, headEmployeeId: null, color: '#6366f1', description: '', sortOrder: 0,
}
const emptyRule = {
  department: '', shiftCategory: 'morning', minStaff: 1, effectiveFrom: null, effectiveTo: null,
}

async function readDepartmentWorkspace(authentication, branchId, signal) {
  const [branch, departments, employees] = await Promise.all([
    readBranch(authentication, branchId, { signal }),
    readAllDepartments(authentication, branchId, { signal }),
    readAllEmployees(authentication, branchId, { signal }),
  ])
  const rules = branch.enableStaffingRules
    ? await readAllStaffingRules(authentication, branchId, { signal })
    : []
  return { departments, employees, rules, enableStaffingRules: branch.enableStaffingRules }
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

function DepartmentEditor({ departments, employees, selected, onCancel, onSaved, onBusy, authentication, branchId }) {
  const [draft, setDraft] = useState(selected ?? emptyDepartment)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  useEffect(() => onBusy(saving), [onBusy, saving])

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
        {selected && <button type="button" className="danger" disabled={saving} onClick={() => setConfirmDelete(true)}>Delete</button>}
      </div>
      {message && <p role="status">{message}</p>}
      <ConfirmDialog title="Delete department" open={confirmDelete} busy={saving} onClose={() => setConfirmDelete(false)} onConfirm={remove} confirmLabel="Delete department">Delete this department? Dependent records may prevent deletion.</ConfirmDialog>
    </form>
  )
}

function StaffingEditor({ authentication, branchId, departments, selected, onSelect, onSaved, onBusy }) {
  const [draft, setDraft] = useState(selected ?? { ...emptyRule, department: departments[0]?.name ?? '' })
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  useEffect(() => onBusy(saving), [onBusy, saving])

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
          {selected && <button type="button" className="danger" disabled={saving} onClick={() => setConfirmDelete(true)}>Delete</button>}
        </div>
        {message && <p role="status">{message}</p>}
        <ConfirmDialog title="Delete staffing rule" open={confirmDelete} busy={saving} onClose={() => setConfirmDelete(false)} onConfirm={remove} confirmLabel="Delete rule">Delete this staffing rule?</ConfirmDialog>
      </form>
    </div>
  )
}

export default function DepartmentManager({ authentication, branchId, clearBranch }) {
  const [state, setState] = useState({ status: 'loading', departments: [], employees: [], rules: [], enableStaffingRules: false })
  const [notice, setNotice] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState(null)
  const [selectedRule, setSelectedRule] = useState(null)
  const [view, setView] = useState('departments')
  const [collapsed, setCollapsed] = useState([])
  const [showDepartment, setShowDepartment] = useState(false)
  const [showRule, setShowRule] = useState(false)
  const [editorBusy, setEditorBusy] = useState(false)
  const [orgSearch, setOrgSearch] = useState('')
  const [orgDepartment, setOrgDepartment] = useState('')

  const load = useCallback(async ({ keepSelection = false, notice: nextNotice = '' } = {}) => {
    try {
      const { departments, employees, rules, enableStaffingRules } = await readDepartmentWorkspace(authentication, branchId)
      setState({ status: 'ready', departments, employees, rules, enableStaffingRules })
      if (!enableStaffingRules) setView('departments')
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
    readDepartmentWorkspace(authentication, branchId, controller.signal).then(({ departments, employees, rules, enableStaffingRules }) => {
      setState({ status: 'ready', departments, employees, rules, enableStaffingRules })
      if (!enableStaffingRules) setView('departments')
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
    <section className="department-manager restored-module" aria-label="Departments and staffing rules">
      {notice && <p role="status">{notice}</p>}
      <header className="restored-module-header"><h3>Departments</h3><div className="module-actions"><button type="button" className="btn btn-outline" onClick={() => load().catch(() => {})}>Reload</button><button type="button" className="btn btn-primary" onClick={() => { setSelectedDepartment(null); setShowDepartment(true) }}>New Department</button></div></header>
      <FilterTabs label="Department views" options={[{ value: 'departments', label: 'Departments' }, { value: 'chart', label: 'Organization Chart' }, ...(state.enableStaffingRules ? [{ value: 'staffing', label: 'Staffing Rules' }] : [])]} value={view} onChange={setView} />
      {view === 'departments' && <PortalTable label="Departments"><thead><tr><th>Department</th><th>Parent</th><th>Head</th><th>Employees</th><th>Actions</th></tr></thead><tbody>{rows.map(({ department, depth }) => <tr key={department.id}><td style={{ paddingInlineStart: `${16 + depth * 18}px` }}><span className="department-swatch" style={{ background: department.color }} />{department.name}<small>{department.description}</small></td><td>{state.departments.find((item) => item.id === department.parentId)?.name ?? 'No parent'}</td><td>{state.employees.find((item) => item.id === department.headEmployeeId)?.name ?? 'No head'}</td><td>{state.employees.filter((item) => item.department === department.name && item.active).length}</td><td><button type="button" className="btn btn-outline btn-sm" onClick={() => { setSelectedDepartment(department); setShowDepartment(true) }}>Edit</button></td></tr>)}{state.departments.length === 0 && <tr><td colSpan={5}><div className="empty-state">No departments yet.</div></td></tr>}</tbody></PortalTable>}
      {view === 'chart' && <><div className="restored-toolbar"><label>Search organization<input type="search" value={orgSearch} onChange={(event) => setOrgSearch(event.target.value)} placeholder="Search by name or title" /></label><label>Department<select value={orgDepartment} onChange={(event) => setOrgDepartment(event.target.value)}><option value="">All departments</option>{[...new Set(state.employees.map((employee) => employee.department).filter(Boolean))].sort().map((name) => <option key={name}>{name}</option>)}</select></label><button type="button" className="btn btn-outline" onClick={() => setCollapsed([])}>Expand all</button><button type="button" className="btn btn-outline" onClick={() => setCollapsed(state.employees.map((item) => item.id))}>Collapse all</button></div><ReportingChart employees={state.employees} departments={state.departments} search={orgSearch} department={orgDepartment} collapsed={collapsed} onToggle={(id) => setCollapsed((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])} /></>}
      <FormDialog title={selectedDepartment ? 'Edit department' : 'New department'} open={showDepartment} onClose={() => { if (!editorBusy) setShowDepartment(false) }}>
        <DepartmentEditor
          key={selectedDepartment ? JSON.stringify(departmentSnapshot(selectedDepartment)) : 'new'}
          authentication={authentication}
          branchId={branchId}
          departments={state.departments}
          employees={state.employees}
          selected={selectedDepartment}
          onBusy={setEditorBusy}
          onCancel={() => setShowDepartment(false)}
          onSaved={async (options) => { await load(options); if (options.notice) setShowDepartment(false) }}
        />
      </FormDialog>
      {view === 'staffing' && state.enableStaffingRules && <><div className="restored-toolbar"><h4>Staffing rules</h4><button type="button" className="btn btn-primary" disabled={!state.departments.length} onClick={() => { setSelectedRule(null); setShowRule(true) }}>Add Rule</button></div><PortalTable label="Staffing rules"><thead><tr><th>Department</th><th>Shift category</th><th>Minimum staff</th><th>Effective from</th><th>Effective to</th><th>Actions</th></tr></thead><tbody>{state.rules.map((rule) => <tr key={rule.id}><td>{rule.department}</td><td>{rule.shiftCategory}</td><td>{rule.minStaff}</td><td>{rule.effectiveFrom ?? 'Not set'}</td><td>{rule.effectiveTo ?? 'Not set'}</td><td><button type="button" className="btn btn-outline btn-sm" onClick={() => { setSelectedRule(rule); setShowRule(true) }}>Edit</button></td></tr>)}{state.rules.length === 0 && <tr><td colSpan={6}><div className="empty-state">No staffing rules yet.</div></td></tr>}</tbody></PortalTable></>}
      {state.enableStaffingRules && <FormDialog title={selectedRule ? 'Edit staffing rule' : 'New staffing rule'} open={showRule} onClose={() => { if (!editorBusy) setShowRule(false) }}>
      <StaffingEditor
        key={selectedRule
          ? JSON.stringify(staffingRuleSnapshot(selectedRule))
          : `new:${state.departments[0]?.id ?? 'none'}`}
        authentication={authentication}
        branchId={branchId}
        departments={state.departments}
        onBusy={setEditorBusy}
        selected={selectedRule}
        onSelect={setSelectedRule}
        onSaved={async (options) => { await load(options); if (options.notice) setShowRule(false) }}
      />
      </FormDialog>}
    </section>
  )
}

function ReportingChart({ employees, departments, search, department, collapsed, onToggle }) {
  const active = employees.filter((employee) => employee.active && employee.employmentStatus !== 'Terminated')
  const byId = new Map(active.map((employee) => [employee.id, employee]))
  const matches = (employee) => (!department || employee.department === department)
    && `${employee.name} ${employee.jobTitle}`.toLowerCase().includes(search.toLowerCase())
  const visible = new Set()
  for (const employee of active.filter(matches)) {
    let current = employee
    const seen = new Set()
    while (current && !seen.has(current.id)) {
      seen.add(current.id); visible.add(current.id)
      current = byId.get(current.reportingManagerId)
    }
  }
  const visited = new Set()
  const node = (employee) => {
    if (visited.has(employee.id) || !visible.has(employee.id)) return null
    visited.add(employee.id)
    const children = active.filter((item) => item.reportingManagerId === employee.id && visible.has(item.id))
    const hidden = collapsed.includes(employee.id) && !search && !department
    return <li key={employee.id} style={{ borderInlineStartColor: departments.find((item) => item.name === employee.department)?.color ?? '#6366f1' }}><div>{children.length > 0 && <button type="button" className="btn btn-ghost btn-sm" aria-label={`${hidden ? 'Expand' : 'Collapse'} ${employee.name}`} aria-expanded={!hidden} onClick={() => onToggle(employee.id)}>{hidden ? '+' : '−'}</button>}<strong>{employee.name}</strong><small>{employee.jobTitle} · {employee.department || 'No department'}</small></div>{!hidden && children.length > 0 && <ul>{children.map(node)}</ul>}</li>
  }
  const roots = active.filter((employee) => !employee.reportingManagerId || !byId.has(employee.reportingManagerId))
  const rendered = roots.map(node)
  const unplaced = active.filter((employee) => !visited.has(employee.id) && visible.has(employee.id))
  return <><ul className="restoration-org-chart">{rendered}</ul>{visible.size === 0 && <div className="empty-state">No employees match this search.</div>}{unplaced.length > 0 && !collapsed.length && <p role="status">Check reporting-manager links for {unplaced.map((employee) => employee.name).join(', ')}.</p>}</>
}

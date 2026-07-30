/**
 * DepartmentManager.jsx — Feature 3.1: Department Hierarchy & Org Tree
 *
 * Tab 1 – Departments: CRUD tree (parent/child nesting, dept head, colour)
 * Tab 2 – Org Chart:   CSS tree of employees by reporting-manager hierarchy
 */
import { useState, useEffect } from 'react';
import {
  GitBranch, Users, Plus, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, Search, AlertCircle, ShieldCheck, RefreshCw,
} from 'lucide-react';
import { getDepartments, saveDepartment, deleteDepartment } from '../utils/departmentStorage';
import { getDeptStaffingRules, saveDeptStaffingRule, deleteDeptStaffingRule } from '../utils/staffingStorage';
import { getEmployees } from '../utils/storage';
import { useCompany } from '../context/CompanyContext';

// ── helpers ──────────────────────────────────────────────────────────────────

const PRESET_COLORS = [
  '#6366f1','#2563eb','#06b6d4','#10b981','#f59e0b',
  '#ef4444','#ec4899','#8b5cf6','#0ea5e9','#84cc16',
];

function initials(name = '') {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?';
}

/** Flatten departments into a display order with level numbers. */
function flattenTree(depts, parentId = null, level = 0) {
  return depts
    .filter(d => (d.parentId ?? null) === (parentId ?? null))
    .sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name))
    .flatMap(d => [{ ...d, level }, ...flattenTree(depts, d.id, level + 1)]);
}

// ── Org Chart node (recursive) ────────────────────────────────────────────────

/** Recursively checks whether any descendant matches the search string. */
function hasMatchingDescendant(emp, allEmps, search) {
  const reports = allEmps.filter(e => e.reportingManagerId === emp.id);
  return reports.some(r =>
    r.name.toLowerCase().includes(search) ||
    (r.jobTitle || '').toLowerCase().includes(search) ||
    hasMatchingDescendant(r, allEmps, search)
  );
}

function OrgNode({ emp, allEmps, depts, deptColorMap, search, collapsed, onToggle }) {
  const reports    = allEmps.filter(e => e.reportingManagerId === emp.id);
  const color      = deptColorMap[emp.department] || '#94a3b8';
  const matchSearch = !search || emp.name.toLowerCase().includes(search) || (emp.jobTitle || '').toLowerCase().includes(search);
  const hasVisibleDesc = search ? hasMatchingDescendant(emp, allEmps, search) : reports.length > 0;

  if (search && !matchSearch && !hasVisibleDesc) return null;

  const isCollapsed = collapsed.has(emp.id);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', background: '#fff',
        border: '1px solid var(--gray-200)', borderRadius: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        cursor: reports.length ? 'pointer' : 'default',
        transition: 'box-shadow 0.15s',
      }}
        onClick={() => reports.length && onToggle(emp.id)}
      >
        {/* Avatar */}
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: color + '33', color,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: 13, flexShrink: 0,
          border: `2px solid ${color}55`,
        }}>
          {initials(emp.name)}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--gray-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {emp.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 1 }}>
            {emp.jobTitle || '—'}
          </div>
        </div>

        {/* Dept badge — shows parent dept in tooltip when applicable */}
        {emp.department && (() => {
          const deptRecord = depts.find(d => d.name === emp.department);
          const parentDept = deptRecord?.parentId ? depts.find(d => d.id === deptRecord.parentId) : null;
          return (
            <span
              title={parentDept ? `${parentDept.name} › ${emp.department}` : emp.department}
              style={{
                background: color + '22', color,
                border: `1px solid ${color}44`,
                borderRadius: 999, padding: '2px 8px', fontSize: 11, fontWeight: 500,
                whiteSpace: 'nowrap', flexShrink: 0, cursor: parentDept ? 'help' : 'default',
              }}
            >
              {parentDept && <span style={{ opacity: 0.6, marginRight: 3 }}>{parentDept.name} ›</span>}
              {emp.department}
            </span>
          );
        })()}

        {/* Expand/collapse */}
        {reports.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--gray-400)', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 3 }}>
            <Users size={11} /> {reports.length}
            {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          </span>
        )}
      </div>

      {/* Children */}
      {reports.length > 0 && !isCollapsed && (
        <div style={{
          marginLeft: 24,
          paddingLeft: 16,
          borderLeft: '2px solid var(--gray-200)',
        }}>
          {reports.map(r => (
            <OrgNode
              key={r.id}
              emp={r}
              allEmps={allEmps}
              depts={depts}
              deptColorMap={deptColorMap}
              search={search}
              collapsed={collapsed}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  id: null, name: '', parentId: '', headEmployeeId: '', color: '#6366f1', description: '', sortOrder: 0,
};

export default function DepartmentManager() {
  const { activeCompany } = useCompany();
  const staffingRulesEnabled = activeCompany?.enableStaffingRules !== false;
  const [tab,       setTab]       = useState('departments');
  const [depts,     setDepts]     = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [form,      setForm]      = useState(null);   // null = form hidden
  const [saving,    setSaving]    = useState(false);
  const [msg,       setMsg]       = useState(null);   // {type, text}
  const [deleting,  setDeleting]  = useState(null);   // dept id pending delete confirm

  // Org chart state
  const [orgSearch,   setOrgSearch]   = useState('');
  const [orgDeptFilter, setOrgDeptFilter] = useState('');
  const [collapsed,   setCollapsed]   = useState(new Set());

  // Staffing rules state
  const [staffingRules, setStaffingRules] = useState([]);
  const [staffingForm,  setStaffingForm]  = useState(null);  // null = hidden
  const EMPTY_STAFFING = { department: '', shiftCategory: 'morning', minStaff: 1 };
  const SHIFT_CATEGORY_LABELS = { morning: '☀ Morning', afternoon: '🌤 Afternoon', night: '🌙 Night', flexible: '⟳ Flexible' };

  useEffect(() => {
    Promise.all([getDepartments(), getEmployees(), getDeptStaffingRules().catch(() => [])])
      .then(([d, e, rules]) => {
        setDepts(d);
        setEmployees(e.filter(e => e.employmentStatus !== 'Terminated'));
        setStaffingRules(rules);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSaveStaffingRule() {
    if (!staffingForm.department.trim()) { flash('danger', 'Department name is required.'); return; }
    try {
      await saveDeptStaffingRule(staffingForm);
      const updated = await getDeptStaffingRules();
      setStaffingRules(updated);
      setStaffingForm(null);
      flash('success', 'Staffing rule saved.');
    } catch (err) {
      flash('danger', 'Save failed: ' + (err.message || 'Unknown error'));
    }
  }

  async function handleDeleteStaffingRule(id) {
    try {
      await deleteDeptStaffingRule(id);
      setStaffingRules(prev => prev.filter(r => r.id !== id));
    } catch (err) {
      flash('danger', 'Delete failed: ' + (err.message || 'Unknown error'));
    }
  }

  function flash(type, text) {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 3500);
  }

  // ── Department CRUD ─────────────────────────────────────────────────────────

  function openAdd() { setForm({ ...EMPTY_FORM }); }
  function openEdit(d) {
    setForm({ id: d.id, name: d.name, parentId: d.parentId || '', headEmployeeId: d.headEmployeeId || '', color: d.color, description: d.description, sortOrder: d.sortOrder });
  }
  function closeForm() { setForm(null); }

  async function handleSave() {
    const trimmedName = form.name.trim();
    if (!trimmedName) return;

    // Duplicate name check within the same company (excludes self on edit).
    // Case-insensitive because "Nursing" and "nursing" are the same thing.
    const dup = depts.find(d =>
      d.id !== form.id &&
      (d.name || '').trim().toLowerCase() === trimmedName.toLowerCase(),
    );
    if (dup) {
      flash('danger', `A department named "${dup.name}" already exists.`);
      return;
    }

    // Parent cycle check — walk ancestor chain and refuse if the current dept
    // appears. Only meaningful when editing an existing dept (form.id set).
    if (form.id && form.parentId) {
      let cursor = form.parentId;
      const seen = new Set();
      while (cursor && !seen.has(cursor)) {
        if (cursor === form.id) {
          flash('danger', 'This parent would create a reporting cycle.');
          return;
        }
        seen.add(cursor);
        const parent = depts.find(d => d.id === cursor);
        cursor = parent?.parentId || null;
      }
    }

    setSaving(true);
    try {
      const saved = await saveDepartment({ ...form, name: trimmedName, parentId: form.parentId || null, headEmployeeId: form.headEmployeeId || null });
      setDepts(prev => {
        const idx = prev.findIndex(d => d.id === saved.id);
        return idx >= 0 ? prev.map((d, i) => i === idx ? saved : d) : [...prev, saved];
      });
      closeForm();
      flash('success', `Department "${saved.name}" saved.`);
    } catch (err) {
      flash('danger', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    const empCount = employees.filter(e => e.department === depts.find(d => d.id === id)?.name).length;
    const childCount = depts.filter(d => d.parentId === id).length;
    if (empCount > 0 || childCount > 0) {
      flash('danger', `Cannot delete: ${empCount} employee(s) and/or ${childCount} sub-department(s) are still assigned.`);
      setDeleting(null);
      return;
    }
    try {
      await deleteDepartment(id);
      setDepts(prev => prev.filter(d => d.id !== id));
      flash('success', 'Department deleted.');
    } catch (err) {
      flash('danger', err.message);
    }
    setDeleting(null);
  }

  // ── Org chart helpers ────────────────────────────────────────────────────────

  // Colour map: department name → colour from departments table (or auto-cycle)
  const deptColorMap = Object.fromEntries(
    depts.map(d => [d.name, d.color])
  );
  // Auto-assign colours for departments not in the table yet
  const allDeptNames = [...new Set(employees.map(e => e.department).filter(Boolean))];
  allDeptNames.forEach((name, i) => {
    if (!deptColorMap[name]) deptColorMap[name] = PRESET_COLORS[i % PRESET_COLORS.length];
  });

  const empIds    = new Set(employees.map(e => e.id));
  const filtered  = orgDeptFilter ? employees.filter(e => e.department === orgDeptFilter) : employees;
  const roots     = filtered.filter(e => !e.reportingManagerId || !empIds.has(e.reportingManagerId));

  function toggleCollapse(id) {
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;

  const flatDepts = flattenTree(depts);

  return (
    <div>
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <GitBranch size={20} /> Departments
        </h2>
        {tab === 'departments' && (
          <button className="btn btn-primary btn-sm" onClick={openAdd} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Plus size={14} style={{ flexShrink: 0 }} /> Add Department
          </button>
        )}
      </div>

      <div className="page-body">

        {/* Tabs */}
        <div className="tabs" style={{ marginBottom: 20 }}>
          <button className={`tab-btn ${tab === 'departments' ? 'active' : ''}`} onClick={() => setTab('departments')}>
            Departments ({depts.length})
          </button>
          <button className={`tab-btn ${tab === 'orgchart' ? 'active' : ''}`} onClick={() => setTab('orgchart')}>
            Org Chart
          </button>
          {staffingRulesEnabled && (
            <button className={`tab-btn ${tab === 'staffing' ? 'active' : ''}`} onClick={() => setTab('staffing')}>
              <ShieldCheck size={14} /> Staffing Rules ({staffingRules.length})
            </button>
          )}
        </div>

        {msg && (
          <div className={`alert alert-${msg.type}`} style={{ marginBottom: 16 }}>
            {msg.text}
          </div>
        )}

        {/* ── DEPARTMENTS TAB ── */}
        {tab === 'departments' && (
          <div>
            {/* Add / Edit form */}
            {form && (
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="card-header">
                  <h3>{form.id ? 'Edit Department' : 'New Department'}</h3>
                  <button className="btn btn-ghost btn-icon" onClick={closeForm}><X size={16} /></button>
                </div>
                <div className="card-body">
                  <div className="form-grid form-grid-2">
                    <div className="form-group">
                      <label>Name <span style={{ color: 'var(--danger)' }}>*</span></label>
                      <input className="form-control" value={form.name}
                        onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                        placeholder="e.g. Nursing" />
                    </div>
                    <div className="form-group">
                      <label>Parent Department</label>
                      <select className="form-control" value={form.parentId}
                        onChange={e => setForm(p => ({ ...p, parentId: e.target.value }))}>
                        <option value="">— Top-level —</option>
                        {depts.filter(d => d.id !== form.id).map(d => (
                          <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Department Head</label>
                      <select className="form-control" value={form.headEmployeeId}
                        onChange={e => setForm(p => ({ ...p, headEmployeeId: e.target.value }))}>
                        <option value="">— None —</option>
                        {employees.map(e => (
                          <option key={e.id} value={e.id}>{e.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Colour</label>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                        {PRESET_COLORS.map(c => (
                          <button key={c} type="button"
                            onClick={() => setForm(p => ({ ...p, color: c }))}
                            style={{
                              width: 24, height: 24, borderRadius: '50%', background: c, border: 'none',
                              cursor: 'pointer', outline: form.color === c ? `3px solid ${c}` : '3px solid transparent',
                              outlineOffset: 2,
                            }}
                          />
                        ))}
                        <input type="color" value={form.color}
                          onChange={e => setForm(p => ({ ...p, color: e.target.value }))}
                          style={{ width: 28, height: 28, padding: 0, border: 'none', borderRadius: 4, cursor: 'pointer' }} />
                      </div>
                    </div>
                    <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                      <label>Description</label>
                      <input className="form-control" value={form.description}
                        onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                        placeholder="Optional description" />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving || !form.name.trim()}>
                      <Check size={13} /> {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button className="btn btn-outline btn-sm" onClick={closeForm}>Cancel</button>
                  </div>
                </div>
              </div>
            )}

            {/* Department tree table */}
            {flatDepts.length === 0 ? (
              <div className="card">
                <div className="empty-state" style={{ padding: '48px 24px' }}>
                  <GitBranch size={32} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.2 }} />
                  <h3>No departments yet</h3>
                  <p>Click "Add Department" to create your organisation structure.</p>
                  <button className="btn btn-primary btn-sm" onClick={openAdd} style={{ marginTop: 12 }}>
                    <Plus size={13} /> Add Department
                  </button>
                </div>
              </div>
            ) : (
              <div className="card">
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Department</th>
                        <th>Head</th>
                        <th style={{ width: 80 }}>Employees</th>
                        <th style={{ width: 100 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {flatDepts.map(d => {
                        const headEmp  = employees.find(e => e.id === d.headEmployeeId);
                        const empCount = employees.filter(e => e.department === d.name).length;
                        const isDeleting = deleting === d.id;
                        return (
                          <tr key={d.id}>
                            <td>
                              <div style={{ paddingLeft: d.level * 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                                {d.level > 0 && (
                                  <span style={{ color: 'var(--gray-300)', fontSize: 16, lineHeight: 1 }}>└</span>
                                )}
                                <span style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 6,
                                  background: d.color + '22', color: d.color,
                                  border: `1px solid ${d.color}44`,
                                  borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600,
                                }}>
                                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                                  {d.name}
                                </span>
                                {d.description && (
                                  <span style={{ fontSize: 11, color: 'var(--gray-400)', marginLeft: 4 }}>{d.description}</span>
                                )}
                              </div>
                            </td>
                            <td style={{ fontSize: 13, color: 'var(--gray-600)' }}>
                              {headEmp ? headEmp.name : <span style={{ color: 'var(--gray-300)' }}>—</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <span style={{ fontWeight: 600, fontSize: 13, color: empCount ? 'var(--gray-800)' : 'var(--gray-300)' }}>
                                {empCount}
                              </span>
                            </td>
                            <td>
                              {isDeleting ? (
                                <div style={{ display: 'flex', gap: 4 }}>
                                  <button className="btn btn-danger btn-sm btn-icon" title="Confirm delete" onClick={() => handleDelete(d.id)}>
                                    <Check size={12} />
                                  </button>
                                  <button className="btn btn-ghost btn-sm btn-icon" title="Cancel" onClick={() => setDeleting(null)}>
                                    <X size={12} />
                                  </button>
                                </div>
                              ) : (
                                <div style={{ display: 'flex', gap: 4 }}>
                                  <button className="btn btn-ghost btn-icon btn-sm" title="Edit" onClick={() => openEdit(d)}>
                                    <Pencil size={13} />
                                  </button>
                                  <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Delete" onClick={() => setDeleting(d.id)}>
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── ORG CHART TAB ── */}
        {tab === 'orgchart' && (
          <div>
            {/* Controls */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
                <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)', pointerEvents: 'none' }} />
                <input
                  className="form-control"
                  style={{ paddingLeft: 30 }}
                  placeholder="Search by name or title…"
                  value={orgSearch}
                  onChange={e => setOrgSearch(e.target.value.toLowerCase())}
                />
              </div>
              <select className="form-control" style={{ width: 200 }} value={orgDeptFilter}
                onChange={e => setOrgDeptFilter(e.target.value)}>
                <option value="">All Departments</option>
                {[...new Set([
                  ...depts.map(d => d.name),
                  ...employees.map(e => e.department).filter(Boolean),
                ])].sort().map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <button className="btn btn-outline btn-sm" onClick={() => setCollapsed(new Set())}>
                Expand All
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => setCollapsed(new Set(employees.map(e => e.id)))}>
                Collapse All
              </button>
              <button className="btn btn-outline btn-sm" title="Reload employee data"
                onClick={() => getEmployees().then(e => setEmployees(e.filter(x => x.employmentStatus !== 'Terminated'))).catch(() => {})}>
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            {/* Legend */}
            {depts.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                {depts.map(d => (
                  <span key={d.id} style={{
                    background: d.color + '22', color: d.color,
                    border: `1px solid ${d.color}44`,
                    borderRadius: 999, padding: '2px 10px', fontSize: 11, fontWeight: 600,
                  }}>
                    {d.name}
                  </span>
                ))}
              </div>
            )}

            {employees.length === 0 ? (
              <div className="card">
                <div className="empty-state"><p>No employees found.</p></div>
              </div>
            ) : roots.length === 0 ? (
              <div className="card">
                <div style={{ padding: '24px', display: 'flex', alignItems: 'center', gap: 10, color: 'var(--gray-500)', fontSize: 13 }}>
                  <AlertCircle size={16} />
                  {orgDeptFilter
                    ? `No root employees in "${orgDeptFilter}" — all have a reporting manager outside this department.`
                    : 'No root employees found. Assign reporting managers in Employee profiles to build the hierarchy.'}
                </div>
              </div>
            ) : (
              <div style={{ padding: '4px 0' }}>
                {roots.map(emp => (
                  <OrgNode
                    key={emp.id}
                    emp={emp}
                    allEmps={employees}
                    depts={depts}
                    deptColorMap={deptColorMap}
                    search={orgSearch}
                    collapsed={collapsed}
                    onToggle={toggleCollapse}
                  />
                ))}
              </div>
            )}

            {/* Unassigned note */}
            {!orgDeptFilter && !orgSearch && (() => {
              const assigned = new Set();
              function walk(empId) {
                employees.filter(e => e.reportingManagerId === empId).forEach(e => { assigned.add(e.id); walk(e.id); });
              }
              roots.forEach(r => { assigned.add(r.id); walk(r.id); });
              const orphans = employees.filter(e => !assigned.has(e.id));
              return orphans.length > 0 ? (
                <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, fontSize: 12, color: 'var(--gray-500)' }}>
                  <AlertCircle size={12} style={{ marginRight: 6, color: 'var(--danger)' }} />
                  {orphans.length} employee{orphans.length > 1 ? 's' : ''} not shown (reporting manager set to an employee outside the company or to themselves): {orphans.map(e => e.name).join(', ')}
                </div>
              ) : null;
            })()}
          </div>
        )}

        {/* ── Staffing Rules tab ── */}
        {tab === 'staffing' && staffingRulesEnabled && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <p className="text-muted text-sm">
                Minimum required staff per department per shift category. The Roster will warn (and block publish) if coverage falls below these targets.
              </p>
              <button className="btn btn-primary btn-sm" onClick={() => setStaffingForm({ ...EMPTY_STAFFING })}>
                <Plus size={14} /> Add Rule
              </button>
            </div>

            {staffingForm && (
              <div className="card" style={{ marginBottom: 16, padding: '16px 20px' }}>
                <h4 style={{ marginBottom: 12, fontSize: 14 }}>
                  {staffingForm.id ? 'Edit Rule' : 'New Staffing Rule'}
                </h4>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Department</label>
                    <input
                      className="form-control"
                      list="dept-names"
                      value={staffingForm.department}
                      onChange={e => setStaffingForm(p => ({ ...p, department: e.target.value }))}
                      placeholder="e.g. Emergency, ICU, Pharmacy"
                    />
                    <datalist id="dept-names">
                      {depts.map(d => <option key={d.id} value={d.name} />)}
                    </datalist>
                  </div>
                  <div className="form-group">
                    <label>Shift Category</label>
                    <select
                      className="form-control"
                      value={staffingForm.shiftCategory}
                      onChange={e => setStaffingForm(p => ({ ...p, shiftCategory: e.target.value }))}
                    >
                      <option value="morning">☀ Morning</option>
                      <option value="afternoon">🌤 Afternoon</option>
                      <option value="night">🌙 Night</option>
                      <option value="flexible">⟳ Flexible</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Minimum Staff Required</label>
                    <input
                      className="form-control"
                      type="number"
                      min="1"
                      value={staffingForm.minStaff}
                      onChange={e => setStaffingForm(p => ({ ...p, minStaff: parseInt(e.target.value) || 1 }))}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveStaffingRule}>
                    <Check size={14} /> Save Rule
                  </button>
                  <button className="btn btn-outline btn-sm" onClick={() => setStaffingForm(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {staffingRules.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--gray-400)' }}>
                <ShieldCheck size={28} style={{ marginBottom: 12, opacity: 0.3 }} />
                <p>No staffing rules defined yet.</p>
                <p className="text-sm">Add rules to enforce minimum coverage targets on the Roster.</p>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Department</th>
                    <th>Shift Category</th>
                    <th>Min Staff</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {staffingRules.map(rule => (
                    <tr key={rule.id}>
                      <td style={{ fontWeight: 500 }}>{rule.department}</td>
                      <td>{SHIFT_CATEGORY_LABELS[rule.shiftCategory] || rule.shiftCategory}</td>
                      <td>
                        <span className="badge badge-blue">{rule.minStaff}</span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            className="btn btn-outline btn-sm"
                            title="Edit rule"
                            onClick={() => setStaffingForm({ ...rule })}
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            title="Delete rule"
                            onClick={() => handleDeleteStaffingRule(rule.id)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

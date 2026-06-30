/**
 * LeaveManager.jsx — Main Leave Management page for Workloop
 *
 * Tabs:
 *   1. Overview    — leave balances for current user's employees + today's absences
 *   2. Requests    — all leave requests with approval actions
 *   3. Calendar    — team calendar view colour-coded by leave type
 *   4. Balances    — HR summary table: all employees × all leave types
 *   5. Settings    — leave year, weekend, carry-forward, public holidays, Ramadan
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Calendar, Users, BarChart2, Settings, Plus, Check, X, AlertCircle,
  Clock, Download, ChevronLeft, ChevronRight, Info, Trash2, Save, RefreshCw, Printer
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getEmployees } from '../utils/storage';
import { createNotification } from '../utils/notificationStorage';
import {
  getLeaveTypes, saveLeaveType, getLeaveRequests, submitLeaveRequest, updateLeaveRequestStatus,
  cancelLeaveRequest, getLeaveBalances, getAllLeaveBalances, upsertLeaveBalance,
  getPublicHolidays, savePublicHoliday, deletePublicHoliday,
  getLeaveSettings, saveLeaveSettings, initialiseLeaveModule, recalculateAllBalances,
  seedPublicHolidaysForYear,
  // Feature 6: delegates
  getLeaveApprovalDelegates, saveLeaveApprovalDelegate, deleteLeaveApprovalDelegate,
} from '../utils/leaveStorage';
import {
  calculateAnnualLeaveAccrual, countLeaveDays, getLeaveAdvancePayWarnings,
  calculateLeaveEncashment, LEAVE_STATUS_COLORS, formatLeaveDuration,
  UAE_PUBLIC_HOLIDAYS_2025, UAE_PUBLIC_HOLIDAYS_2026
} from '../utils/leaveEngine';
import { formatDateUAE, formatAED } from '../utils/uaeValidators';
import LeaveRequestModal from './LeaveRequestModal';

function RequestWarnings({ warnings }) {
  if (!warnings?.length) return null;
  return (
    <div style={{ marginTop: 4 }}>
      {warnings.map((w, i) => (
        <div key={i} style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          background: '#fffbeb', border: '1px solid #fcd34d',
          borderRadius: 4, padding: '2px 6px', fontSize: 11,
          color: '#92400e', marginRight: 4, marginTop: 2,
        }}>
          <AlertCircle size={10} /> {w}
        </div>
      ))}
    </div>
  );
}

// ── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const cls = LEAVE_STATUS_COLORS[status] || 'badge-gray';
  return <span className={`badge ${cls}`}>{status}</span>;
}

// ── Leave Type Badge ──────────────────────────────────────────────────────────
function LeaveTypeBadge({ code, name, color }) {
  return (
    <span className="badge" style={{ background: color + '22', color, border: `1px solid ${color}44` }}>
      {name}
    </span>
  );
}

// ── Export CSV helper ─────────────────────────────────────────────────────────
function exportBalancesCSV(employees, leaveTypes, allBalances) {
  const headers = ['Employee', 'Department', 'Status', ...leaveTypes.map(lt => `${lt.name} (Used/Entitled)`)];
  const rows = employees.map(emp => {
    const cols = leaveTypes.map(lt => {
      const bal = allBalances.find(b => b.employeeId === emp.id && b.leaveTypeCode === lt.code);
      return bal ? `${bal.usedDays}/${bal.entitledDays}` : '0/0';
    });
    return [emp.name, emp.department || '—', emp.employmentStatus || 'Active', ...cols];
  });
  const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'leave_balances.csv'; a.click();
  URL.revokeObjectURL(url);
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function LeaveManager() {
  const { user } = useAuth();
  const [tab, setTab]               = useState('overview');
  const [loading, setLoading]       = useState(true);
  const [employees, setEmployees]   = useState([]);
  const [leaveTypes, setLeaveTypes] = useState([]);
  const [requests, setRequests]     = useState([]);
  const [allBalances, setAllBalances] = useState([]);
  const [holidays, setHolidays]     = useState([]);
  const [settings, setSettings]     = useState(null);
  const [showEmpSelector, setShowEmpSelector]   = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [calendarDeptFilter, setCalendarDeptFilter] = useState('');
  const [filterDept, setFilterDept] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterType, setFilterType] = useState('');
  const [approvalModal, setApprovalModal] = useState(null); // { request, action }
  const [approvalReason, setApprovalReason] = useState('');
  const [saving, setSaving]         = useState(false);
  const [msg, setMsg]               = useState(null);

  // Settings form state
  const [settingsForm, setSettingsForm] = useState(null);
  const [newHoliday, setNewHoliday] = useState({ date: '', name: '', type: 'company' });

  // Feature 6: Approval Delegates
  const [delegates, setDelegates]       = useState([]);
  const [delegateForm, setDelegateForm] = useState({ approverEmployeeId:'', delegateEmployeeId:'', fromDate:'', toDate:'' });
  const [delegateSaving, setDelegateSaving] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      await initialiseLeaveModule();
      const [emps, types, reqs, bals, hols, sett, dels] = await Promise.all([
        getEmployees(),
        getLeaveTypes(),
        getLeaveRequests(),
        getAllLeaveBalances(),
        getPublicHolidays(),
        getLeaveSettings(),
        getLeaveApprovalDelegates().catch(() => []),
      ]);
      setEmployees(emps);
      setLeaveTypes(types);
      setRequests(reqs);
      setHolidays(hols);
      setDelegates(dels);
      const defaultSettings = {
        leaveYearType: 'calendar', weekendDefinition: 'fri-sat',
        carryForwardEnabled: true, carryForwardMaxDays: 15,
        approvalChain: '1-level', ramadanActive: false,
        ramadanStart: '', ramadanEnd: '',
      };
      setSettings(sett || defaultSettings);
      setSettingsForm(sett || defaultSettings);

      // Auto-recalculate balances from approved requests + accrual
      if (emps.length > 0 && types.length > 0) {
        try {
          await recalculateAllBalances(emps, types, reqs, new Date().getFullYear(), (sett || defaultSettings).leaveYearType);
          const freshBals = await getAllLeaveBalances();
          setAllBalances(freshBals);
        } catch (e) {
          console.warn('Balance recalculation failed (leave tables may not exist yet):', e.message);
          setAllBalances(bals);
        }
      } else {
        setAllBalances(bals);
      }
    } catch (err) {
      console.error('LeaveManager loadAll:', err);
    } finally {
      setLoading(false);
    }
  };

  const publicHolidayDates = holidays.map(h => h.date);
  const weekendDef = settings?.weekendDefinition || 'fri-sat';

  // ── Today's absences ──────────────────────────────────────────────────────
  const todayStr = new Date().toISOString().split('T')[0];
  const onLeaveToday = requests.filter(r =>
    r.status === 'Approved' && r.startDate <= todayStr && r.endDate >= todayStr
  );

  // ── Pending / awaiting HR action requests ─────────────────────────────────
  // 'Pending' = needs action; 'ManagerApproved' = pre-approved by manager, needs HR final sign-off
  const pendingRequests = requests.filter(r => r.status === 'Pending' || r.status === 'ManagerApproved');

  // ── Advance pay warnings ──────────────────────────────────────────────────
  const advancePayWarnings = getLeaveAdvancePayWarnings(requests);

  // ── Filtered requests ─────────────────────────────────────────────────────
  const filteredRequests = requests.filter(r => {
    const emp = employees.find(e => e.id === r.employeeId);
    if (filterDept && emp?.department !== filterDept) return false;
    if (filterStatus && r.status !== filterStatus) return false;
    if (filterType && r.leaveTypeCode !== filterType) return false;
    return true;
  });

  // ── Approval action ───────────────────────────────────────────────────────
  const handleApproval = async (requestId, action, reason = '') => {
    setSaving(true);
    try {
      await updateLeaveRequestStatus(requestId, action, user?.email || 'HR', reason);

      // Notify the employee if they have a linked portal account
      if (action === 'Approved' || action === 'Rejected') {
        const req = requests.find(r => r.id === requestId);
        if (req) {
          const emp = employees.find(e => e.id === req.employeeId);
          if (emp?.authUserId) {
            const typeStr = action === 'Approved' ? 'leave_approved' : 'leave_rejected';
            createNotification({
              recipientUserId:   emp.authUserId,
              type:              typeStr,
              title:             `Leave request ${action.toLowerCase()}`,
              body:              `Your ${req.leaveTypeCode || 'leave'} request (${formatDateUAE(req.startDate)} – ${formatDateUAE(req.endDate)}) has been ${action.toLowerCase()}${reason ? ': ' + reason : '.'}`,
              relatedEntityType: 'leave_request',
              relatedEntityId:   requestId,
            }).catch(() => {});
          }
        }
      }

      await loadAll();
      setApprovalModal(null);
      setApprovalReason('');
      showMsg('success', `Leave request ${action.toLowerCase()}.`);
    } catch (err) {
      showMsg('danger', 'Failed to update leave request: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitRequest = async (requestData) => {
    const lt = leaveTypes.find(t => t.id === requestData.leaveTypeId);
    if (lt?.autoApprove) {
      const req = await submitLeaveRequest(requestData);
      await updateLeaveRequestStatus(req.id, 'Approved', 'Auto-approved', '');
    } else {
      await submitLeaveRequest(requestData);
    }
    await loadAll();
    showMsg('success', 'Leave request submitted successfully.');
  };

  const showMsg = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  // ── Save settings ─────────────────────────────────────────────────────────
  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await saveLeaveSettings(settingsForm);
      setSettings(settingsForm);
      showMsg('success', 'Leave settings saved.');
    } catch (err) {
      showMsg('danger', 'Failed to save settings: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddHoliday = async () => {
    if (!newHoliday.date || !newHoliday.name) return;
    try {
      await savePublicHoliday(newHoliday);
      setNewHoliday({ date: '', name: '', type: 'company' });
      const hols = await getPublicHolidays();
      setHolidays(hols);
      showMsg('success', 'Holiday added.');
    } catch (err) {
      showMsg('danger', 'Failed to add holiday: ' + err.message);
    }
  };

  const handleDeleteHoliday = async (id) => {
    try {
      await deletePublicHoliday(id);
      setHolidays(prev => prev.filter(h => h.id !== id));
    } catch (err) {
      showMsg('danger', 'Failed to delete holiday: ' + err.message);
    }
  };

  // ── Calendar helpers ──────────────────────────────────────────────────────
  const calYear  = calendarMonth.getFullYear();
  const calMonth = calendarMonth.getMonth();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const firstDayOfMonth = new Date(calYear, calMonth, 1).getDay();

  const getRequestsForDate = (dateStr) =>
    requests.filter(r => r.status === 'Approved' && r.startDate <= dateStr && r.endDate >= dateStr);

  const departments = [...new Set(employees.map(e => e.department).filter(Boolean))].sort();

  if (loading) {
    return <div style={{ padding:40, textAlign:'center', color:'var(--gray-400)' }}>Loading leave module…</div>;
  }

  const TABS = [
    { id:'overview',  label:'Overview',   icon:BarChart2 },
    { id:'requests',  label:`Requests${pendingRequests.length > 0 ? ` (${pendingRequests.length})` : ''}`, icon:Clock },
    { id:'calendar',  label:'Calendar',   icon:Calendar },
    { id:'balances',  label:'Balances',   icon:Users },
    { id:'settings',  label:'Settings',   icon:Settings },
  ];

  return (
    <div>
      <div className="page-header">
        <h2>Leave Management</h2>
        <div className="page-header-actions">
          <button className="btn btn-primary"
            disabled={employees.filter(e => e.employmentStatus !== 'Terminated').length === 0}
            onClick={() => {
              setSelectedEmployee(employees.find(e => e.employmentStatus !== 'Terminated') || employees[0]);
              setShowEmpSelector(false);
              setShowRequestModal(true);
            }}>
            <Plus size={15}/> New Leave Request
          </button>
        </div>
      </div>

      <div className="page-body">
        {msg && (
          <div className={`alert alert-${msg.type} mb-4`}>
            <AlertCircle size={15}/>{msg.text}
          </div>
        )}

        {/* Advance pay warnings — Art. 29 */}
        {advancePayWarnings.length > 0 && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={15}/>
            <div>
              <strong>Art. 29 — Annual Leave Advance Pay Required:</strong>{' '}
              {advancePayWarnings.map((r, i) => {
                const emp = employees.find(e => e.id === r.employeeId);
                return <span key={i}>{emp?.name} (starts {formatDateUAE(r.startDate)}){i < advancePayWarnings.length - 1 ? ', ' : ''}</span>;
              })}
              {' '}— UAE law requires annual leave salary to be paid in advance.
            </div>
          </div>
        )}

        {/* Ramadan notice */}
        {settings?.ramadanActive && (
          <div className="alert alert-info mb-4">
            <Info size={15}/>
            <strong>Ramadan Period Active</strong> ({formatDateUAE(settings.ramadanStart)} – {formatDateUAE(settings.ramadanEnd)}):
            UAE law requires working hours to be reduced by 2 hours per day for all employees.
          </div>
        )}

        {/* Tab bar */}
        <div className="tabs" style={{ marginBottom:20 }}>
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.id} className={`tab-btn ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
                <Icon size={13} style={{ marginRight:5 }}/>{t.label}
              </button>
            );
          })}
        </div>

        {/* ── OVERVIEW TAB ── */}
        {tab === 'overview' && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">On Leave Today</div>
                <div className="stat-value" style={{ color: onLeaveToday.length > 0 ? 'var(--warning)' : 'var(--success)' }}>{onLeaveToday.length}</div>
                <div className="stat-sub">of {employees.filter(e => e.employmentStatus !== 'Terminated').length} active</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Pending Approvals</div>
                <div className="stat-value" style={{ color: pendingRequests.length > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{pendingRequests.length}</div>
                <div className="stat-sub">awaiting action</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Leave Types</div>
                <div className="stat-value">{leaveTypes.length}</div>
                <div className="stat-sub">configured</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Public Holidays</div>
                <div className="stat-value">{holidays.filter(h => h.year === new Date().getFullYear()).length}</div>
                <div className="stat-sub">this year</div>
              </div>
            </div>

            {/* On leave today */}
            {onLeaveToday.length > 0 && (
              <div className="card mb-4">
                <div className="card-header"><h3>On Leave Today — {formatDateUAE(todayStr)}</h3></div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Employee</th><th>Leave Type</th><th>Period</th><th>Days</th></tr></thead>
                    <tbody>
                      {onLeaveToday.map(r => {
                        const emp = employees.find(e => e.id === r.employeeId);
                        const lt  = leaveTypes.find(t => t.code === r.leaveTypeCode);
                        return (
                          <tr key={r.id}>
                            <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                            <td>{lt && <LeaveTypeBadge code={lt.code} name={lt.name} color={lt.color}/>}</td>
                            <td>{formatDateUAE(r.startDate)} – {formatDateUAE(r.endDate)}</td>
                            <td>{r.daysRequested}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Pending requests quick view */}
            {pendingRequests.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h3>Pending Approvals</h3>
                  <button className="btn btn-ghost btn-sm" onClick={() => setTab('requests')}>View all</button>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Employee</th><th>Type</th><th>Dates</th><th>Days</th><th>Submitted</th><th></th></tr></thead>
                    <tbody>
                      {pendingRequests.slice(0, 5).map(r => {
                        const emp = employees.find(e => e.id === r.employeeId);
                        const lt  = leaveTypes.find(t => t.code === r.leaveTypeCode);
                        return (
                          <tr key={r.id}>
                            <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                            <td>{lt && <LeaveTypeBadge code={lt.code} name={lt.name} color={lt.color}/>}</td>
                            <td>
                              {formatDateUAE(r.startDate)} – {formatDateUAE(r.endDate)}
                              <RequestWarnings warnings={r.warnings} />
                            </td>
                            <td>{r.daysRequested}</td>
                            <td className="text-muted text-sm">{formatDateUAE(r.submittedAt?.split('T')[0])}</td>
                            <td>
                              <div className="flex gap-2">
                                <button className="btn btn-success btn-sm" onClick={() => handleApproval(r.id, 'Approved')}>
                                  <Check size={13}/> Approve
                                </button>
                                <button className="btn btn-danger btn-sm" onClick={() => setApprovalModal({ request: r, action: 'Rejected' })}>
                                  <X size={13}/> Reject
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── REQUESTS TAB ── */}
        {tab === 'requests' && (
          <div className="card">
            <div className="card-header">
              <h3>Leave Requests</h3>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                <select className="form-control" style={{ width:140 }} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                  <option value="">All Statuses</option>
                  <option value="Pending">Pending</option>
                  <option value="Approved">Approved</option>
                  <option value="Rejected">Rejected</option>
                  <option value="Cancelled">Cancelled</option>
                </select>
                <select className="form-control" style={{ width:160 }} value={filterType} onChange={e => setFilterType(e.target.value)}>
                  <option value="">All Types</option>
                  {leaveTypes.map(lt => <option key={lt.code} value={lt.code}>{lt.name}</option>)}
                </select>
                {departments.length > 0 && (
                  <select className="form-control" style={{ width:160 }} value={filterDept} onChange={e => setFilterDept(e.target.value)}>
                    <option value="">All Departments</option>
                    {departments.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                )}
              </div>
            </div>
            {filteredRequests.length === 0 ? (
              <div className="empty-state"><Calendar size={40}/><h3>No leave requests</h3><p>No requests match the current filters.</p></div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Employee</th><th>Type</th><th>Start</th><th>End</th>
                      <th>Days</th><th>Status</th><th>Submitted</th><th>Approved By</th><th>Doc</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRequests.map(r => {
                      const emp = employees.find(e => e.id === r.employeeId);
                      const lt  = leaveTypes.find(t => t.code === r.leaveTypeCode);
                      return (
                        <tr key={r.id}>
                          <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                          <td>{lt && <LeaveTypeBadge code={lt.code} name={lt.name} color={lt.color}/>}</td>
                          <td>{formatDateUAE(r.startDate)}</td>
                          <td>{formatDateUAE(r.endDate)}</td>
                          <td>
                            {r.isHalfDay ? '0.5' : r.daysRequested}
                            <RequestWarnings warnings={r.warnings} />
                          </td>
                          <td><StatusBadge status={r.status}/></td>
                          <td className="text-muted text-sm">{formatDateUAE(r.submittedAt?.split('T')[0])}</td>
                          <td className="text-muted text-sm">
                            {r.status === 'ManagerApproved' && r.managerApprovedBy
                              ? <span title="Manager pre-approved">Mgr: {r.managerApprovedBy}</span>
                              : r.status === 'ManagerRejected' && r.managerApprovedBy
                              ? <span title={r.managerRejectionReason} style={{ color:'#ef4444' }}>Mgr rejected</span>
                              : (r.approvedBy || '—')
                            }
                          </td>
                          <td>
                            {r.attachmentUrl
                              ? <a href={r.attachmentUrl} target="_blank" rel="noopener noreferrer" title="View attachment" style={{ color: 'var(--primary)' }}>📎</a>
                              : <span style={{ color: 'var(--gray-300)' }}>—</span>
                            }
                          </td>
                          <td>
                            {/* HR can approve/reject Pending requests (1-level) */}
                            {r.status === 'Pending' && (
                              <div className="flex gap-2">
                                <button className="btn btn-success btn-sm" onClick={() => handleApproval(r.id, 'Approved')}>
                                  <Check size={13}/>
                                </button>
                                <button className="btn btn-danger btn-sm" onClick={() => setApprovalModal({ request: r, action: 'Rejected' })}>
                                  <X size={13}/>
                                </button>
                              </div>
                            )}
                            {/* HR gives final sign-off after manager pre-approved (2-level) */}
                            {r.status === 'ManagerApproved' && (
                              <div className="flex gap-2">
                                <button
                                  className="btn btn-success btn-sm"
                                  title="Final HR approval"
                                  onClick={() => handleApproval(r.id, 'Approved')}
                                >
                                  <Check size={13}/> Final OK
                                </button>
                                <button
                                  className="btn btn-danger btn-sm"
                                  title="HR override reject"
                                  onClick={() => setApprovalModal({ request: r, action: 'Rejected' })}
                                >
                                  <X size={13}/>
                                </button>
                              </div>
                            )}
                            {r.status === 'Approved' && r.startDate > todayStr && (
                              <button className="btn btn-ghost btn-sm text-danger" onClick={() => handleApproval(r.id, 'Cancelled', 'Cancelled by HR')}>
                                Cancel
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── CALENDAR TAB ── */}
        {tab === 'calendar' && (
          <div className="card">
            <div className="card-header">
              <h3>
                <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setCalendarMonth(new Date(calYear, calMonth - 1, 1))}>
                  <ChevronLeft size={16}/>
                </button>
                {new Date(calYear, calMonth).toLocaleString('en-AE', { month:'long', year:'numeric' })}
                <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setCalendarMonth(new Date(calYear, calMonth + 1, 1))}>
                  <ChevronRight size={16}/>
                </button>
              </h3>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
                {departments.length > 0 && (
                  <select
                    className="form-control"
                    style={{ width:150, height:32, fontSize:12, padding:'0 8px' }}
                    value={calendarDeptFilter}
                    onChange={e => setCalendarDeptFilter(e.target.value)}
                  >
                    <option value="">All Departments</option>
                    {departments.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                )}
                {leaveTypes.slice(0, 5).map(lt => (
                  <span key={lt.code} style={{ display:'flex', alignItems:'center', gap:4, fontSize:11 }}>
                    <span style={{ width:10, height:10, borderRadius:2, background:lt.color, display:'inline-block' }}/>
                    {lt.name}
                  </span>
                ))}
                <button
                  className="btn btn-outline btn-sm"
                  style={{ marginLeft: 8 }}
                  onClick={() => window.print()}
                  title="Print calendar"
                >
                  <Printer size={13} /> Print
                </button>
              </div>
            </div>
            <div className="card-body" style={{ padding:0 }}>
              {/* Calendar grid */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(7, 1fr)', borderBottom:'1px solid var(--gray-200)' }}>
                {(weekendDef === 'fri-sat' ? ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']).map(d => (
                  <div key={d} style={{ padding:'8px 4px', textAlign:'center', fontSize:11, fontWeight:600, color:'var(--gray-500)', background:'var(--gray-50)', borderRight:'1px solid var(--gray-100)' }}>
                    {d}
                  </div>
                ))}
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(7, 1fr)' }}>
                {/* Empty cells before first day */}
                {Array.from({ length: (firstDayOfMonth + 6) % 7 }).map((_, i) => (
                  <div key={`empty-${i}`} style={{ minHeight:80, borderRight:'1px solid var(--gray-100)', borderBottom:'1px solid var(--gray-100)', background:'var(--gray-50)' }}/>
                ))}
                {/* Day cells */}
                {Array.from({ length: daysInMonth }).map((_, i) => {
                  const day = i + 1;
                  const dateStr = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
                  const isToday = dateStr === todayStr;
                  const isHoliday = publicHolidayDates.includes(dateStr);
                  const holiday = holidays.find(h => h.date === dateStr);
                  const dayRequests = getRequestsForDate(dateStr).filter(r => {
                    if (!calendarDeptFilter) return true;
                    const dEmp = employees.find(e => e.id === r.employeeId);
                    return dEmp?.department === calendarDeptFilter;
                  });
                  const isWeekendDay = (() => {
                    const d = new Date(dateStr).getDay();
                    return weekendDef === 'fri-sat' ? (d === 5 || d === 6) : (d === 0 || d === 6);
                  })();
                  return (
                    <div key={day} style={{
                      minHeight:80, padding:'4px 6px',
                      borderRight:'1px solid var(--gray-100)',
                      borderBottom:'1px solid var(--gray-100)',
                      background: isToday ? 'var(--primary-light)' : isWeekendDay ? 'var(--gray-50)' : 'white',
                    }}>
                      <div style={{ fontSize:12, fontWeight: isToday ? 700 : 400, color: isToday ? 'var(--primary)' : isWeekendDay ? 'var(--gray-400)' : 'var(--gray-700)', marginBottom:2 }}>
                        {day}
                        {isHoliday && <span style={{ marginLeft:4, fontSize:9, background:'#fef3c7', color:'#92400e', borderRadius:3, padding:'1px 4px' }}>{holiday?.name?.split(' ')[0]}</span>}
                      </div>
                      {dayRequests.slice(0, 3).map(r => {
                        const lt = leaveTypes.find(t => t.code === r.leaveTypeCode);
                        const emp = employees.find(e => e.id === r.employeeId);
                        return (
                          <div key={r.id} title={`${emp?.name} — ${lt?.name} (${formatDateUAE(r.startDate)} – ${formatDateUAE(r.endDate)})`} style={{ fontSize:10, background: lt?.color + '22', color: lt?.color, borderRadius:3, padding:'1px 4px', marginBottom:2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                            {emp?.name?.split(' ')[0]} {r.startDate === dateStr ? `↑${formatDateUAE(r.startDate).slice(0,5)}` : ''}
                          </div>
                        );
                      })}
                      {dayRequests.length > 3 && <div style={{ fontSize:10, color:'var(--gray-400)' }}>+{dayRequests.length - 3} more</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── BALANCES TAB ── */}
        {tab === 'balances' && (
          <div className="card">
            <div className="card-header">
              <h3>Leave Balances — {new Date().getFullYear()}</h3>
              <div style={{ display:'flex', gap:8 }}>
                <button className="btn btn-outline btn-sm" onClick={async () => {
                  setSaving(true);
                  try {
                    await recalculateAllBalances(employees, leaveTypes, requests, new Date().getFullYear(), settings?.leaveYearType || 'calendar');
                    const freshBals = await getAllLeaveBalances();
                    setAllBalances(freshBals);
                    showMsg('success', 'Leave balances recalculated.');
                  } catch(e) { showMsg('danger', 'Recalculation failed: ' + e.message); }
                  finally { setSaving(false); }
                }} disabled={saving}>
                  <RefreshCw size={14}/> Recalculate
                </button>
                <button className="btn btn-outline btn-sm" onClick={() => exportBalancesCSV(employees, leaveTypes, allBalances)}>
                  <Download size={14}/> Export CSV
                </button>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Dept</th>
                    {leaveTypes.map(lt => (
                      <th key={lt.code} style={{ color: lt.color, minWidth:100 }}>{lt.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {employees.filter(e => e.employmentStatus !== 'Terminated').map(emp => (
                    <tr key={emp.id}>
                      <td style={{ fontWeight:500 }}>{emp.name}</td>
                      <td className="text-muted text-sm">{emp.department || '—'}</td>
                      {leaveTypes.map(lt => {
                        const bal = allBalances.find(b => b.employeeId === emp.id && b.leaveTypeCode === lt.code);
                        const used = bal?.usedDays || 0;
                        const entitled = bal?.entitledDays || lt.annualEntitlementDays;
                        const remaining = bal?.remaining ?? (entitled - used);
                        return (
                          <td key={lt.code} style={{ textAlign:'center' }}>
                            {lt.isUnlimited ? (
                              <span className="text-muted text-sm">Unlimited</span>
                            ) : (
                              <div>
                                <span style={{ fontWeight:600, color: remaining < 0 ? 'var(--danger)' : 'var(--gray-800)' }}>
                                  {remaining}
                                </span>
                                <span style={{ fontSize:10, color:'var(--gray-400)', marginLeft:4 }}>/ {entitled}</span>
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── SETTINGS TAB ── */}
        {tab === 'settings' && settingsForm && (
          <div>
            <div className="card mb-4">
              <div className="card-header">
                <h3>Leave Configuration</h3>
                <button className="btn btn-primary btn-sm" onClick={handleSaveSettings} disabled={saving}>
                  <Save size={14}/> {saving ? 'Saving…' : 'Save Settings'}
                </button>
              </div>
              <div className="card-body">
                <div className="form-grid form-grid-2">
                  <div className="form-group">
                    <label>Leave Year Type</label>
                    <select className="form-control" value={settingsForm.leaveYearType}
                      onChange={e => setSettingsForm(p => ({ ...p, leaveYearType: e.target.value }))}>
                      <option value="calendar">Calendar Year (Jan – Dec)</option>
                      <option value="anniversary">Hire-Date Anniversary Year</option>
                    </select>
                    <span className="hint">Determines when annual leave resets each year</span>
                  </div>
                  <div className="form-group">
                    <label>Weekend Definition</label>
                    <select className="form-control" value={settingsForm.weekendDefinition}
                      onChange={e => setSettingsForm(p => ({ ...p, weekendDefinition: e.target.value }))}>
                      <option value="fri-sat">Friday – Saturday (UAE default)</option>
                      <option value="sat-sun">Saturday – Sunday</option>
                    </select>
                    <span className="hint">Used when counting working days for paternity, bereavement, study leave</span>
                  </div>
                  <div className="form-group">
                    <label>Approval Chain</label>
                    <select className="form-control" value={settingsForm.approvalChain}
                      onChange={e => setSettingsForm(p => ({ ...p, approvalChain: e.target.value }))}>
                      <option value="1-level">1-Level (Direct Manager)</option>
                      <option value="2-level">2-Level (Manager + HR)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Annual Leave Carry-Forward</label>
                    <select className="form-control" value={settingsForm.carryForwardEnabled ? 'yes' : 'no'}
                      onChange={e => setSettingsForm(p => ({ ...p, carryForwardEnabled: e.target.value === 'yes' }))}>
                      <option value="yes">Allowed</option>
                      <option value="no">Not Allowed</option>
                    </select>
                  </div>
                  {settingsForm.carryForwardEnabled && (
                    <div className="form-group">
                      <label>Max Carry-Forward Days</label>
                      <input className="form-control" type="number" min={0} max={30}
                        value={settingsForm.carryForwardMaxDays}
                        onChange={e => setSettingsForm(p => ({ ...p, carryForwardMaxDays: parseInt(e.target.value) || 0 }))}/>
                    </div>
                  )}
                  <div className="form-group" style={{ gridColumn:'1/-1' }}>
                    <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
                      <input type="checkbox" checked={settingsForm.ramadanActive}
                        onChange={e => setSettingsForm(p => ({ ...p, ramadanActive: e.target.checked }))}/>
                      Ramadan Period Active (reduces working hours by 2hrs/day for all employees)
                    </label>
                  </div>
                  {settingsForm.ramadanActive && (
                    <>
                      <div className="form-group">
                        <label>Ramadan Start Date</label>
                        <input className="form-control" type="date" value={settingsForm.ramadanStart || ''}
                          onChange={e => setSettingsForm(p => ({ ...p, ramadanStart: e.target.value }))}/>
                      </div>
                      <div className="form-group">
                        <label>Ramadan End Date</label>
                        <input className="form-control" type="date" value={settingsForm.ramadanEnd || ''}
                          onChange={e => setSettingsForm(p => ({ ...p, ramadanEnd: e.target.value }))}/>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Public Holidays */}
            <div className="card">
              <div className="card-header">
                <h3>Public Holidays</h3>
                <div style={{ display:'flex', gap:8 }}>
                  {[
                    { year: 2025, list: UAE_PUBLIC_HOLIDAYS_2025 },
                    { year: 2026, list: UAE_PUBLIC_HOLIDAYS_2026 },
                  ].map(({ year, list }) => {
                    const alreadySeeded = holidays.some(h => h.year === year && h.type === 'federal');
                    return (
                      <button
                        key={year}
                        className="btn btn-outline btn-sm"
                        disabled={alreadySeeded}
                        title={alreadySeeded ? `${year} UAE holidays already seeded` : `Seed ${year} UAE federal public holidays`}
                        onClick={async () => {
                          try {
                            const seeded = await seedPublicHolidaysForYear(year, list);
                            if (seeded) {
                              const fresh = await getPublicHolidays(year);
                              setHolidays(prev => [...prev.filter(h => h.year !== year), ...fresh]);
                            }
                          } catch (err) {
                            alert('Failed to seed holidays: ' + err.message);
                          }
                        }}
                      >
                        {alreadySeeded ? `✓ ${year} seeded` : `Seed ${year} UAE Holidays`}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="card-body" style={{ padding:0 }}>
                <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--gray-200)', display:'flex', gap:8, flexWrap:'wrap', alignItems:'flex-end' }}>
                  <div className="form-group" style={{ margin:0 }}>
                    <label>Date</label>
                    <input className="form-control" type="date" value={newHoliday.date}
                      onChange={e => setNewHoliday(p => ({ ...p, date: e.target.value }))}/>
                  </div>
                  <div className="form-group" style={{ margin:0, flex:1, minWidth:200 }}>
                    <label>Holiday Name</label>
                    <input className="form-control" value={newHoliday.name}
                      onChange={e => setNewHoliday(p => ({ ...p, name: e.target.value }))}
                      placeholder="e.g. Company Foundation Day"/>
                  </div>
                  <div className="form-group" style={{ margin:0 }}>
                    <label>Type</label>
                    <select className="form-control" value={newHoliday.type}
                      onChange={e => setNewHoliday(p => ({ ...p, type: e.target.value }))}>
                      <option value="company">Company</option>
                      <option value="federal">Federal</option>
                    </select>
                  </div>
                  <button className="btn btn-primary" onClick={handleAddHoliday} style={{ marginBottom:0 }}>
                    <Plus size={14}/> Add
                  </button>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Date</th><th>Name</th><th>Type</th><th>Year</th><th></th></tr></thead>
                    <tbody>
                      {holidays.sort((a,b) => a.date.localeCompare(b.date)).map(h => (
                        <tr key={h.id}>
                          <td>{formatDateUAE(h.date)}</td>
                          <td style={{ fontWeight:500 }}>{h.name}</td>
                          <td><span className={`badge ${h.type === 'federal' ? 'badge-blue' : 'badge-green'}`}>{h.type}</span></td>
                          <td>{h.year}</td>
                          <td>
                            {h.type === 'company' && (
                              <button className="btn btn-ghost btn-icon btn-sm text-danger" onClick={() => handleDeleteHoliday(h.id)}>
                                <Trash2 size={13}/>
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Probation Leave Rules (Feature 2.3) */}
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <h3>Probation Leave Eligibility</h3>
                <span style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 400 }}>
                  Toggle which leave types employees on probation can apply for
                </span>
              </div>
              <div className="card-body">
                <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 12 }}>
                  Disabled leave types are hidden from the employee portal during probation. Sick Leave is always available (processed as unpaid per Art. 31 UAE Labour Law).
                </p>
                <div className="table-wrap">
                  <table style={{ fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th>Leave Type</th>
                        <th style={{ width: 160 }}>Available on Probation</th>
                        <th style={{ width: 160 }}>Requires Attachment</th>
                        <th>Law Reference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leaveTypes.map(lt => (
                        <tr key={lt.id}>
                          <td>
                            <span style={{
                              background: lt.color + '22', color: lt.color,
                              border: `1px solid ${lt.color}44`,
                              borderRadius: 999, padding: '2px 10px', fontSize: 12, fontWeight: 600,
                            }}>
                              {lt.name}
                            </span>
                          </td>
                          <td>
                            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={lt.probationEligible !== false}
                                onChange={async e => {
                                  const updated = { ...lt, probationEligible: e.target.checked };
                                  setLeaveTypes(prev => prev.map(t => t.id === lt.id ? updated : t));
                                  try { await saveLeaveType(updated); }
                                  catch { setLeaveTypes(prev => prev.map(t => t.id === lt.id ? lt : t)); }
                                }}
                              />
                              {lt.probationEligible !== false ? 'Yes' : 'No'}
                            </label>
                          </td>
                          <td>
                            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={!!lt.requiresAttachment}
                                onChange={async e => {
                                  const updated = { ...lt, requiresAttachment: e.target.checked };
                                  setLeaveTypes(prev => prev.map(t => t.id === lt.id ? updated : t));
                                  try { await saveLeaveType(updated); }
                                  catch { setLeaveTypes(prev => prev.map(t => t.id === lt.id ? lt : t)); }
                                }}
                              />
                              {lt.requiresAttachment ? 'Yes' : 'No'}
                            </label>
                          </td>
                          <td style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                            {lt.lawReference || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Approval Delegation (Feature 6) */}
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <h3>Approval Delegation</h3>
                <span style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 400 }}>
                  Assign a deputy approver when a manager is on leave
                </span>
              </div>
              <div className="card-body">
                {/* Add delegate form */}
                <div className="form-grid form-grid-2" style={{ marginBottom: 16 }}>
                  <div className="form-group">
                    <label>Approver (manager who is away)</label>
                    <select className="form-control" value={delegateForm.approverEmployeeId}
                      onChange={e => setDelegateForm(p => ({ ...p, approverEmployeeId: e.target.value }))}>
                      <option value="">Select manager…</option>
                      {employees.filter(e => e.employmentStatus !== 'Terminated').map(e => (
                        <option key={e.id} value={e.id}>{e.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Delegate (will approve in their place)</label>
                    <select className="form-control" value={delegateForm.delegateEmployeeId}
                      onChange={e => setDelegateForm(p => ({ ...p, delegateEmployeeId: e.target.value }))}>
                      <option value="">Select delegate…</option>
                      {employees.filter(e => e.employmentStatus !== 'Terminated' && e.id !== delegateForm.approverEmployeeId).map(e => (
                        <option key={e.id} value={e.id}>{e.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>From Date</label>
                    <input className="form-control" type="date" value={delegateForm.fromDate}
                      onChange={e => setDelegateForm(p => ({ ...p, fromDate: e.target.value }))}/>
                  </div>
                  <div className="form-group">
                    <label>To Date</label>
                    <input className="form-control" type="date" value={delegateForm.toDate}
                      onChange={e => setDelegateForm(p => ({ ...p, toDate: e.target.value }))}/>
                  </div>
                </div>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={delegateSaving || !delegateForm.approverEmployeeId || !delegateForm.delegateEmployeeId || !delegateForm.fromDate || !delegateForm.toDate}
                  onClick={async () => {
                    setDelegateSaving(true);
                    try {
                      const saved = await saveLeaveApprovalDelegate(delegateForm);
                      setDelegates(d => [saved, ...d]);
                      setDelegateForm({ approverEmployeeId:'', delegateEmployeeId:'', fromDate:'', toDate:'' });
                    } catch (err) {
                      showMsg('danger', 'Failed to save delegate: ' + err.message);
                    } finally {
                      setDelegateSaving(false);
                    }
                  }}
                >
                  {delegateSaving ? 'Saving…' : 'Add Delegation'}
                </button>

                {delegates.length > 0 && (
                  <div className="table-wrap" style={{ marginTop: 16 }}>
                    <table>
                      <thead><tr><th>Approver</th><th>Delegate</th><th>From</th><th>To</th><th>Active</th><th></th></tr></thead>
                      <tbody>
                        {delegates.map(d => {
                          const today = new Date().toISOString().split('T')[0];
                          const isActive = d.fromDate <= today && d.toDate >= today;
                          const approver = employees.find(e => e.id === d.approverEmployeeId);
                          const delegate = employees.find(e => e.id === d.delegateEmployeeId);
                          return (
                            <tr key={d.id}>
                              <td style={{ fontWeight:500 }}>{approver?.name || '—'}</td>
                              <td>{delegate?.name || '—'}</td>
                              <td>{formatDateUAE(d.fromDate)}</td>
                              <td>{formatDateUAE(d.toDate)}</td>
                              <td><span className={`badge ${isActive ? 'badge-green' : 'badge-gray'}`}>{isActive ? 'Active' : 'Inactive'}</span></td>
                              <td>
                                <button className="btn btn-ghost btn-icon btn-sm text-danger"
                                  onClick={async () => {
                                    try {
                                      await deleteLeaveApprovalDelegate(d.id);
                                      setDelegates(ds => ds.filter(x => x.id !== d.id));
                                    } catch (err) {
                                      showMsg('danger', err.message);
                                    }
                                  }}>
                                  <Trash2 size={13}/>
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                {delegates.length === 0 && (
                  <p style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 12 }}>
                    No delegations configured.
                  </p>
                )}
              </div>
            </div>

          </div>
        )}
      </div>


      {/* ── Approval/Rejection Modal ── */}
      {approvalModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth:440 }}>
            <div className="modal-header">
              <h3>{approvalModal.action === 'Rejected' ? 'Reject Leave Request' : 'Request More Information'}</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setApprovalModal(null)}><X size={18}/></button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom:12, color:'var(--gray-600)', fontSize:13 }}>
                {approvalModal.action === 'Rejected'
                  ? 'Please provide a reason for rejecting this leave request.'
                  : 'Describe what additional information is needed.'}
              </p>
              <div className="form-group">
                <label>Reason *</label>
                <textarea className="form-control" rows={3} value={approvalReason}
                  onChange={e => setApprovalReason(e.target.value)}
                  placeholder="Enter reason…" style={{ resize:'vertical' }}/>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setApprovalModal(null)} disabled={saving}>Cancel</button>
              <button
                className={`btn ${approvalModal.action === 'Rejected' ? 'btn-danger' : 'btn-primary'}`}
                onClick={() => handleApproval(approvalModal.request.id, approvalModal.action, approvalReason)}
                disabled={saving || !approvalReason.trim()}
              >
                {saving ? 'Saving…' : approvalModal.action}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Leave Request Form ── */}
      {showRequestModal && leaveTypes.length > 0 && (
        <LeaveRequestModal
          employee={selectedEmployee || employees.find(e => e.employmentStatus !== 'Terminated') || employees[0]}
          allEmployees={employees.filter(e => e.employmentStatus !== 'Terminated')}
          onEmployeeChange={setSelectedEmployee}
          leaveTypes={leaveTypes}
          leaveBalances={allBalances.filter(b => b.employeeId === (selectedEmployee?.id || employees[0]?.id))}
          publicHolidayDates={publicHolidayDates}
          weekendDef={weekendDef}
          onSubmit={handleSubmitRequest}
          onClose={() => setShowRequestModal(false)}
        />
      )}
    </div>
  );
}
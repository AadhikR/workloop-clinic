import { useEffect, useState } from 'react';
import { Plus, X, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Calendar, AlertCircle, CheckCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  getLeaveTypes, getLeaveRequests, getLeaveBalances, getPublicHolidays,
} from '../../utils/leaveStorage';
import { supabase } from '../../lib/supabase';
import { countLeaveDays, validateLeaveRequest, getLeaveTypeColor, calculateAnnualLeaveAccrual, DEFAULT_LEAVE_TYPES } from '../../utils/leaveEngine';
import { getMyEmployeeRecord } from '../../utils/profileStorage';

function computeBalancesLocally(leaveTypes, requests, empRec, year) {
  return leaveTypes
    .filter(lt => !lt.isUnlimited)
    .map(lt => {
      const empReqs = requests.filter(r =>
        r.leaveTypeCode === lt.code && r.startDate?.startsWith(String(year))
      );
      const usedDays    = empReqs.filter(r => r.status === 'Approved').reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);
      const pendingDays = empReqs.filter(r => r.status === 'Pending').reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);

      let accruedDays  = lt.annualEntitlementDays || 0;
      let entitledDays = lt.annualEntitlementDays || 0;

      if (lt.code === 'ANNUAL' && (empRec?.employment_start_date || empRec?.startDate)) {
        const accrual = calculateAnnualLeaveAccrual(
          empRec.employment_start_date || empRec.startDate,
          new Date()
        );
        accruedDays  = accrual.totalAccrued;
        entitledDays = accrual.entitlementPerYear;
      }

      return {
        leaveTypeCode: lt.code,
        entitledDays,
        accruedDays,
        usedDays,
        pendingDays,
        remaining: Math.max(0, accruedDays - usedDays),
      };
    });
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AE', { day: 'numeric', month: 'short', year: 'numeric' });
}

const STATUS_BADGE = {
  Pending:   'badge-amber',
  Approved:  'badge-green',
  Rejected:  'badge-red',
  Cancelled: 'badge-gray',
};

export default function EmpLeave() {
  const { profile } = useAuth();
  const [leaveTypes, setLeaveTypes]   = useState([]);
  const [requests, setRequests]       = useState([]);
  const [balances, setBalances]       = useState([]);
  const [holidays, setHolidays]       = useState([]);
  const [emp, setEmp]                 = useState(null);
  const [loading, setLoading]         = useState(true);
  const [showForm, setShowForm]       = useState(false);
  const [activeTab, setActiveTab]     = useState('requests'); // 'requests' | 'balances' | 'calendar'
  const [expandedId, setExpandedId]   = useState(null);
  const [empCalMonth, setEmpCalMonth] = useState(new Date());
  const [saving, setSaving]           = useState(false);
  const [toast, setToast]             = useState(null); // { type, msg }

  // Form state
  const [form, setForm] = useState({
    leaveTypeCode: '',
    startDate: '',
    endDate: '',
    isHalfDay: false,
    reason: '',
  });
  const [formErrors, setFormErrors]   = useState([]);
  const [formWarnings, setFormWarnings] = useState([]);

  useEffect(() => {
    if (!profile?.employeeId) return;
    const year = new Date().getFullYear();
    Promise.all([
      getLeaveTypes(),
      getLeaveRequests({ employeeId: profile.employeeId }),
      getLeaveBalances(profile.employeeId, year),
      getPublicHolidays(year),
      getMyEmployeeRecord(),
    ]).then(([lts, reqs, bals, hols, empRec]) => {
      setLeaveTypes(lts);
      setRequests(reqs);
      const effectiveLts = lts.length > 0 ? lts : DEFAULT_LEAVE_TYPES;
      setBalances(bals.length > 0 ? bals : computeBalancesLocally(effectiveLts, reqs, empRec, year));
      setHolidays(hols.map(h => h.date));
      setEmp(empRec);
      setLoading(false);
    });
  }, [profile?.employeeId]);

  function showToast(type, msg) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  }

  async function handleCancel(reqId) {
    if (!window.confirm('Cancel this leave request?')) return;
    const req = requests.find(r => r.id === reqId);
    const { data, error } = await supabase.rpc('employee_cancel_leave_request', { p_request_id: reqId });
    if (error || !data?.success) {
      showToast('error', 'Could not cancel. Please contact HR.');
      return;
    }
    setRequests(prev => prev.map(r => r.id === reqId ? { ...r, status: 'Cancelled' } : r));
    if (req) {
      setBalances(prev => prev.map(b =>
        b.leaveTypeCode === req.leaveTypeCode
          ? {
              ...b,
              usedDays:    Math.max(0, parseFloat(b.usedDays)    - req.daysRequested),
              pendingDays: Math.max(0, parseFloat(b.pendingDays) - req.daysRequested),
              remaining:   parseFloat(b.remaining) + req.daysRequested,
            }
          : b
      ));
    }
    showToast('success', 'Leave request cancelled.');
  }

  // ── Mini-calendar helpers ─────────────────────────────────────────────────
  const empCalYear        = empCalMonth.getFullYear();
  const empCalMonthNum    = empCalMonth.getMonth();
  const empCalDaysInMonth = new Date(empCalYear, empCalMonthNum + 1, 0).getDate();
  const empCalFirstDay    = new Date(empCalYear, empCalMonthNum, 1).getDay();
  // Returns this employee's leave requests covering a given date
  const getEmpDayLeaves   = (dateStr) =>
    requests.filter(r =>
      ['Approved', 'Pending', 'ManagerApproved'].includes(r.status) &&
      r.startDate <= dateStr && r.endDate >= dateStr
    );

  // ── Form day computation ──────────────────────────────────────────────────
  // Compute days for current form selection
  const selectedType = leaveTypes.find(t => t.code === form.leaveTypeCode);
  const computedDays = selectedType && form.startDate && form.endDate
    ? countLeaveDays(form.startDate, form.endDate, selectedType.dayCountType, holidays, 'fri-sat', form.isHalfDay)
    : 0;

  // Validate live as form changes
  useEffect(() => {
    if (!selectedType || !form.startDate || !form.endDate || !emp) {
      setFormErrors([]); setFormWarnings([]); return;
    }
    const balance = balances.find(b => b.leaveTypeCode === selectedType.code);
    const result = validateLeaveRequest(
      { startDate: form.startDate, endDate: form.endDate, isHalfDay: form.isHalfDay, reason: form.reason },
      { startDate: emp.employment_start_date, employmentStartDate: emp.employment_start_date, gender: emp.gender },
      selectedType,
      balance,
      holidays,
      'fri-sat',
    );
    setFormErrors(result.errors);
    setFormWarnings(result.warnings);
  }, [form, selectedType, balances, holidays, emp]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (formErrors.length > 0 || !selectedType || computedDays <= 0) return;
    setSaving(true);

    const { data, error } = await supabase.rpc('employee_submit_leave_request', {
      p_leave_type_id:   selectedType.id,
      p_leave_type_code: selectedType.code,
      p_start_date:      form.startDate,
      p_end_date:        form.endDate,
      p_is_half_day:     form.isHalfDay,
      p_half_day_period: null,
      p_days_requested:  computedDays,
      p_reason:          form.reason,
      p_attachment_url:  '',
      p_warnings:        formWarnings,
    });

    setSaving(false);
    if (error || !data?.success) {
      showToast('error', 'Submission failed. Please try again.');
      return;
    }

    showToast('success', `${selectedType.name} request submitted — ${computedDays} day${computedDays !== 1 ? 's' : ''}.`);
    setShowForm(false);
    setForm({ leaveTypeCode: '', startDate: '', endDate: '', isHalfDay: false, reason: '' });

    // Refresh requests
    const fresh = await getLeaveRequests({ employeeId: profile.employeeId });
    setRequests(fresh);
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2>My Leave</h2>
            <p>UAE Federal Labour Law — Federal Decree-Law No. 33 of 2021</p>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(true)}>
            <Plus size={14} /> Apply
          </button>
        </div>
      </div>

      <div className="emp-page-body">

        {/* Toast */}
        {toast && (
          <div className={`alert ${toast.type === 'success' ? 'alert-success' : 'alert-danger'}`}
               style={{ marginBottom: 16, borderRadius: 10 }}>
            {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {toast.msg}
          </div>
        )}

        {/* Tabs */}
        <div className="tabs" style={{ marginBottom: 16 }}>
          <button className={`tab-btn ${activeTab === 'requests' ? 'active' : ''}`} onClick={() => setActiveTab('requests')}>
            Requests ({requests.length})
          </button>
          <button className={`tab-btn ${activeTab === 'balances' ? 'active' : ''}`} onClick={() => setActiveTab('balances')}>
            My Balances
          </button>
          <button className={`tab-btn ${activeTab === 'calendar' ? 'active' : ''}`} onClick={() => setActiveTab('calendar')}>
            <Calendar size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Calendar
          </button>
        </div>

        {/* Apply form */}
        {showForm && (
          <div className="emp-card" style={{ marginBottom: 16, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>New Leave Request</span>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowForm(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-grid" style={{ gap: 12 }}>
                <div className="form-group">
                  <label>Leave Type</label>
                  <select
                    className="form-control"
                    value={form.leaveTypeCode}
                    onChange={e => setForm(f => ({ ...f, leaveTypeCode: e.target.value }))}
                    required
                  >
                    <option value="">Select type…</option>
                    {leaveTypes.map(t => (
                      <option key={t.code} value={t.code}>{t.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-grid form-grid-2" style={{ gap: 12 }}>
                  <div className="form-group">
                    <label>Start Date</label>
                    <input
                      className="form-control" type="date"
                      value={form.startDate}
                      onChange={e => setForm(f => ({ ...f, startDate: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>End Date</label>
                    <input
                      className="form-control" type="date"
                      value={form.endDate}
                      min={form.startDate}
                      onChange={e => setForm(f => ({ ...f, endDate: e.target.value }))}
                      required
                    />
                  </div>
                </div>

                <div className="checkbox-wrap">
                  <input
                    type="checkbox" id="halfday"
                    checked={form.isHalfDay}
                    onChange={e => setForm(f => ({ ...f, isHalfDay: e.target.checked }))}
                  />
                  <label htmlFor="halfday" style={{ fontWeight: 400, cursor: 'pointer' }}>Half day</label>
                </div>

                {computedDays > 0 && (
                  <div style={{
                    padding: '8px 12px', background: 'var(--primary-light)',
                    borderRadius: 6, fontSize: 13, color: 'var(--primary-dark)',
                  }}>
                    {computedDays} {selectedType?.dayCountType === 'working' ? 'working' : 'calendar'} day{computedDays !== 1 ? 's' : ''}
                  </div>
                )}

                <div className="form-group">
                  <label>Reason (optional)</label>
                  <textarea
                    className="form-control" rows={2}
                    value={form.reason}
                    onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
                    style={{ resize: 'vertical' }}
                  />
                </div>

                {formErrors.map((err, i) => (
                  <div key={i} className="alert alert-danger" style={{ padding: '8px 12px', borderRadius: 6 }}>
                    <AlertCircle size={13} /> <span style={{ fontSize: 12 }}>{err}</span>
                  </div>
                ))}
                {formWarnings.map((w, i) => (
                  <div key={i} className="alert alert-warning" style={{ padding: '8px 12px', borderRadius: 6 }}>
                    <AlertCircle size={13} /> <span style={{ fontSize: 12 }}>{w}</span>
                  </div>
                ))}

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving || formErrors.length > 0 || computedDays <= 0}
                  style={{ justifyContent: 'center' }}
                >
                  {saving ? 'Submitting…' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Requests list */}
        {activeTab === 'requests' && (
          requests.length === 0
            ? <div className="empty-state"><p>No leave requests yet.</p></div>
            : requests.map(req => {
                const expanded = expandedId === req.id;
                return (
                  <div key={req.id} className="emp-card">
                    <div
                      style={{ padding: '14px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                      onClick={() => setExpandedId(expanded ? null : req.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 10, height: 10, borderRadius: 2, flexShrink: 0,
                          background: getLeaveTypeColor(req.leaveTypeCode),
                        }} />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--gray-900)' }}>
                            {leaveTypes.find(t => t.code === req.leaveTypeCode)?.name ?? req.leaveTypeCode}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                            {fmtDate(req.startDate)} – {fmtDate(req.endDate)} · {req.daysRequested} day{req.daysRequested !== 1 ? 's' : ''}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={`badge ${STATUS_BADGE[req.status] ?? 'badge-gray'}`}>{req.status}</span>
                        {expanded ? <ChevronUp size={14} color="var(--gray-400)" /> : <ChevronDown size={14} color="var(--gray-400)" />}
                      </div>
                    </div>

                    {expanded && (
                      <div style={{ padding: '0 16px 14px', borderTop: '1px solid rgba(100,116,139,0.10)' }}>
                        {req.reason && (
                          <p style={{ fontSize: 13, color: 'var(--gray-600)', margin: '12px 0 8px' }}>
                            <strong>Reason:</strong> {req.reason}
                          </p>
                        )}
                        {req.rejectionReason && (
                          <p style={{ fontSize: 13, color: 'var(--danger)', marginBottom: 8 }}>
                            <strong>Rejected:</strong> {req.rejectionReason}
                          </p>
                        )}
                        {req.approvedBy && (
                          <p style={{ fontSize: 12, color: 'var(--gray-500)', marginBottom: 8 }}>
                            Approved by {req.approvedBy} on {fmtDate(req.approvedAt)}
                          </p>
                        )}
                        <p style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                          Submitted {fmtDate(req.submittedAt)}
                        </p>
                        {req.status === 'Pending' && (
                          <button
                            className="btn btn-danger btn-sm"
                            style={{ marginTop: 10 }}
                            onClick={() => handleCancel(req.id)}
                          >
                            Cancel Request
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
        )}

        {/* Balances */}
        {activeTab === 'balances' && (
          balances.length === 0
            ? <div className="empty-state"><p>No balance data available yet.</p></div>
            : balances.map(bal => {
                const lt = leaveTypes.find(t => t.code === bal.leaveTypeCode);
                const pct = bal.entitledDays > 0
                  ? Math.min(100, (bal.usedDays / bal.entitledDays) * 100)
                  : 0;
                return (
                  <div key={bal.id ?? bal.leaveTypeCode} className="emp-card" style={{ padding: 16, marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{
                          width: 10, height: 10, borderRadius: 2,
                          background: getLeaveTypeColor(bal.leaveTypeCode),
                        }} />
                        <span style={{ fontWeight: 600, fontSize: 14 }}>{lt?.name ?? bal.leaveTypeCode}</span>
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--gray-800)' }}>
                        {parseFloat(bal.remaining).toFixed(1)} <span style={{ fontWeight: 400, color: 'var(--gray-400)' }}>/ {bal.entitledDays} days</span>
                      </span>
                    </div>
                    <div className="leave-balance-bar">
                      <div
                        className={`leave-balance-bar-fill ${pct > 80 ? 'danger' : pct > 50 ? 'warning' : ''}`}
                        style={{ width: `${pct}%`, background: getLeaveTypeColor(bal.leaveTypeCode) }}
                      />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--gray-400)' }}>
                      <span>Used: {parseFloat(bal.usedDays).toFixed(1)}</span>
                      {bal.pendingDays > 0 && <span>Pending: {parseFloat(bal.pendingDays).toFixed(1)}</span>}
                      <span>Remaining: {parseFloat(bal.remaining).toFixed(1)}</span>
                    </div>
                  </div>
                );
              })
        )}

        {/* ── CALENDAR TAB ── */}
        {activeTab === 'calendar' && (
          <div className="emp-card" style={{ padding: 16 }}>

            {/* Month navigation */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => setEmpCalMonth(new Date(empCalYear, empCalMonthNum - 1, 1))}
              >
                <ChevronLeft size={16} />
              </button>
              <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--gray-900)' }}>
                {empCalMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' })}
              </span>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => setEmpCalMonth(new Date(empCalYear, empCalMonthNum + 1, 1))}
              >
                <ChevronRight size={16} />
              </button>
            </div>

            {/* Day-of-week headers (Mon first — UAE calendar convention) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => (
                <div key={d} style={{
                  textAlign: 'center', fontSize: 10, fontWeight: 600,
                  color: 'var(--gray-400)', padding: '2px 0',
                }}>
                  {d}
                </div>
              ))}
            </div>

            {/* Day grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
              {/* Empty cells to offset the first day of the month */}
              {Array.from({ length: (empCalFirstDay + 6) % 7 }).map((_, i) => (
                <div key={`ep-${i}`} style={{ height: 40 }} />
              ))}

              {/* Day cells */}
              {Array.from({ length: empCalDaysInMonth }).map((_, i) => {
                const day      = i + 1;
                const dateStr  = `${empCalYear}-${String(empCalMonthNum + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                const todayIso = new Date().toISOString().split('T')[0];
                const isToday   = dateStr === todayIso;
                const isHol     = holidays.includes(dateStr);
                const isWeekend = (() => { const d = new Date(dateStr).getDay(); return d === 5 || d === 6; })();
                const dayLeaves = getEmpDayLeaves(dateStr);
                const mainLeave = dayLeaves[0];
                const lt        = mainLeave ? leaveTypes.find(t => t.code === mainLeave.leaveTypeCode) : null;
                const isApproved = mainLeave?.status === 'Approved';

                return (
                  <div
                    key={day}
                    title={
                      mainLeave
                        ? `${lt?.name || mainLeave.leaveTypeCode} — ${mainLeave.status}`
                        : isHol ? 'Public Holiday' : undefined
                    }
                    style={{
                      height: 40,
                      borderRadius: 6,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 12,
                      fontWeight: isToday ? 700 : 400,
                      background: lt
                        ? lt.color + (isApproved ? '55' : '33')
                        : isToday   ? 'var(--primary-light)'
                        : isHol     ? '#fef9c3'
                        : isWeekend ? 'var(--gray-50)'
                        : 'transparent',
                      color: lt
                        ? lt.color
                        : isToday   ? 'var(--primary)'
                        : isHol     ? '#92400e'
                        : isWeekend ? 'var(--gray-400)'
                        : 'var(--gray-700)',
                      outline:       isToday && !mainLeave ? '2px solid var(--primary)' : 'none',
                      outlineOffset: '-2px',
                      cursor:        mainLeave ? 'help' : 'default',
                    }}
                  >
                    {day}
                    {/* Public holiday dot (only when not on leave) */}
                    {isHol && !mainLeave && (
                      <div style={{
                        width: 4, height: 4, borderRadius: '50%',
                        background: '#f59e0b', marginTop: 1,
                      }} />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            {(() => {
              const usedCodes = [...new Set(
                requests
                  .filter(r => ['Approved', 'Pending', 'ManagerApproved'].includes(r.status))
                  .map(r => r.leaveTypeCode)
              )];
              return usedCodes.length === 0 ? (
                <p style={{ marginTop: 14, fontSize: 12, color: 'var(--gray-400)', textAlign: 'center' }}>
                  No leave on record yet.
                </p>
              ) : (
                <div style={{
                  marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: 10,
                  borderTop: '1px solid var(--gray-100)', paddingTop: 12,
                }}>
                  {usedCodes.map(code => {
                    const lt = leaveTypes.find(t => t.code === code);
                    if (!lt) return null;
                    return (
                      <span key={code} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--gray-600)' }}>
                        <span style={{ width: 10, height: 10, borderRadius: 2, background: lt.color, display: 'inline-block' }} />
                        {lt.name}
                      </span>
                    );
                  })}
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--gray-500)' }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                    Public Holiday
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--gray-400)', marginLeft: 4 }}>
                    Solid = Approved · Faded = Pending
                  </span>
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}

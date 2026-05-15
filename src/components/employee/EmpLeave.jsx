import { useEffect, useState } from 'react';
import { Plus, X, ChevronDown, ChevronUp, AlertCircle, CheckCircle } from 'lucide-react';
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
  const [activeTab, setActiveTab]     = useState('requests'); // 'requests' | 'balances'
  const [expandedId, setExpandedId]   = useState(null);
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
      </div>
    </div>
  );
}

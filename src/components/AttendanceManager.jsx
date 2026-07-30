/**
 * AttendanceManager.jsx — Main Attendance Tracking page for Workloop
 *
 * Tabs: Dashboard | Clock | Records | Absences | Overtime | Regularisation | Reports | Settings
 *
 * Integrations:
 *   - Employee Records: reads employee list, shift assignments, termination status
 *   - Leave Management: reads approved leaves, public holidays, Ramadan period
 *   - Payroll: provides absence deductions, overtime earnings, period close signal
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Clock, Users, AlertCircle, BarChart2, Settings, CheckCircle,
  Plus, X, Check, Download, ChevronLeft, ChevronRight, Save,
  AlertTriangle, Calendar, RefreshCw, Lock, Info, Fingerprint
} from 'lucide-react';
import BiometricImport from './BiometricImport';
import { useAuth } from '../context/AuthContext';
import { useCompany } from '../context/CompanyContext';
import { getEmployees } from '../utils/storage';
import { getLeaveRequests, getPublicHolidays, getLeaveSettings } from '../utils/leaveStorage';
import {
  getAttendanceSettings, saveAttendanceSettings,
  getShifts, saveShift, deleteShift, getShiftForEmployee,
  getClockEvents, recordClockEvent, recordManualClockEvent,
  getAttendanceRecords, upsertAttendanceRecord, computeAndSaveAttendance,
  getAttendancePeriods, getAttendancePeriod, closeAttendancePeriod,
  getRegularisationRequests, submitRegularisationRequest,
  approveRegularisationRequest, rejectRegularisationRequest,
  addAttendanceAuditLog,
} from '../utils/attendanceStorage';
import {
  ATTENDANCE_STATUS, STATUS_COLORS, STATUS_LABELS,
  isWeekendDay, isPublicHolidayDay, isRamadanDay,
  getExpectedHours, calculateOvertimePay, calculateHourlyRate,
  getPayrollSummaryFromAttendance, checkConsecutiveAbsences,
  formatHours, getWorkingDaysInMonth,
} from '../utils/attendanceEngine';
import { formatDateUAE, formatAED } from '../utils/uaeValidators';

// Today's date in the UAE calendar (UTC+4) — matches EmpAttendance.jsx's
// todayUAE(), which is the date employee clock-in/out events are filed under.
function todayUAE() {
  return new Date(Date.now() + 4 * 60 * 60000).toISOString().split('T')[0];
}

// ── Status Badge ──────────────────────────────────────────────────────────────
function AttendanceBadge({ status }) {
  const color = STATUS_COLORS[status] || '#6b7280';
  const label = STATUS_LABELS[status] || status;
  return (
    <span style={{ background: color + '22', color, border: `1px solid ${color}44`, borderRadius:999, padding:'2px 8px', fontSize:11.5, fontWeight:500, whiteSpace:'nowrap' }}>
      {label}
    </span>
  );
}

// ── Shift Modal ───────────────────────────────────────────────────────────────
function ShiftModal({ shift, onSave, onClose }) {
  const [form, setForm] = useState(shift || {
    name: '', shiftType: 'fixed', startTime: '08:00', endTime: '17:00',
    breakMinutes: 60, expectedHours: 8, lateGraceMinutes: 10,
    earlyDepartureGraceMinutes: 10, isOvernight: false, isActive: true,
  });
  const [saving, setSaving] = useState(false);
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try { await onSave(form); onClose(); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth:560 }}>
        <div className="modal-header">
          <h3>{shift?.id ? 'Edit Shift' : 'New Shift'}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          <div className="form-grid form-grid-2">
            <div className="form-group" style={{ gridColumn:'1/-1' }}>
              <label>Shift Name *</label>
              <input className="form-control" value={form.name} onChange={e => f('name', e.target.value)} placeholder="e.g. Morning Shift"/>
            </div>
            <div className="form-group">
              <label>Shift Type</label>
              <select className="form-control" value={form.shiftType} onChange={e => f('shiftType', e.target.value)}>
                <option value="fixed">Fixed</option>
                <option value="flexible">Flexible (min hours only)</option>
                <option value="split">Split Shift</option>
                <option value="overnight">Overnight</option>
              </select>
            </div>
            <div className="form-group">
              <label>Expected Hours/Day</label>
              <input className="form-control" type="number" min={1} max={12} step={0.5} value={form.expectedHours} onChange={e => f('expectedHours', parseFloat(e.target.value))}/>
              <span className="hint">Art. 17: max 8 hrs/day ordinary working hours</span>
            </div>
            {form.shiftType !== 'flexible' && (
              <>
                <div className="form-group">
                  <label>Start Time</label>
                  <input className="form-control" type="time" value={form.startTime || ''} onChange={e => f('startTime', e.target.value)}/>
                </div>
                <div className="form-group">
                  <label>End Time</label>
                  <input className="form-control" type="time" value={form.endTime || ''} onChange={e => f('endTime', e.target.value)}/>
                </div>
              </>
            )}
            {form.shiftType === 'flexible' && (
              <div className="form-group">
                <label>Minimum Hours/Day</label>
                <input className="form-control" type="number" min={1} max={12} step={0.5} value={form.minHoursFlexible || ''} onChange={e => f('minHoursFlexible', parseFloat(e.target.value))}/>
              </div>
            )}
            <div className="form-group">
              <label>Break Duration (minutes, unpaid)</label>
              <input className="form-control" type="number" min={0} max={120} value={form.breakMinutes} onChange={e => f('breakMinutes', parseInt(e.target.value))}/>
            </div>
            <div className="form-group">
              <label>Late Grace Period (minutes)</label>
              <input className="form-control" type="number" min={0} max={60} value={form.lateGraceMinutes} onChange={e => f('lateGraceMinutes', parseInt(e.target.value))}/>
            </div>
            <div className="form-group">
              <label>Early Departure Grace (minutes)</label>
              <input className="form-control" type="number" min={0} max={60} value={form.earlyDepartureGraceMinutes} onChange={e => f('earlyDepartureGraceMinutes', parseInt(e.target.value))}/>
            </div>
            <div className="form-group">
              <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
                <input type="checkbox" checked={form.isOvernight} onChange={e => f('isOvernight', e.target.checked)}/>
                Overnight shift (spans midnight)
              </label>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || !form.name.trim()}>
            {saving ? 'Saving…' : 'Save Shift'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function AttendanceManager() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const biometricEnabled = activeCompany?.enableBiometricImport !== false;
  const [tab, setTab]               = useState('dashboard');
  const [loading, setLoading]       = useState(true);
  const initialLoadDone = useRef(false);
  const [employees, setEmployees]   = useState([]);
  const [shifts, setShifts]         = useState([]);
  const [settings, setSettings]     = useState(null);
  const [settingsForm, setSettingsForm] = useState(null);
  const [leaveSettings, setLeaveSettings] = useState(null);
  const [approvedLeaves, setApprovedLeaves] = useState([]);
  const [holidayDates, setHolidayDates] = useState([]);
  const [records, setRecords]       = useState([]);
  const [periods, setPeriods]       = useState([]);
  const [regularisations, setRegularisations] = useState([]);
  const [saving, setSaving]         = useState(false);
  const [msg, setMsg]               = useState(null);
  const [shiftModal, setShiftModal] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
  });
  const [filterEmp, setFilterEmp]   = useState('');
  const [clockEmp, setClockEmp]     = useState('');
  const [manualEntry, setManualEntry] = useState(false);
  const [manualForm, setManualForm] = useState({ employeeId:'', eventType:'CLOCK_IN', eventTime:'', notes:'' });
  const [approvalModal, setApprovalModal] = useState(null);
  const [approvalReason, setApprovalReason] = useState('');

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [emps, sh, sett, leaveSett, leaves, hols, recs, pers, regs] = await Promise.all([
        getEmployees(),
        getShifts().catch(() => []),
        getAttendanceSettings().catch(() => null),
        getLeaveSettings().catch(() => null),
        getLeaveRequests({ status: 'Approved' }).catch(() => []),
        getPublicHolidays().catch(() => []),
        getAttendanceRecords({ period: selectedMonth }).catch(() => []),
        getAttendancePeriods().catch(() => []),
        getRegularisationRequests().catch(() => []),
      ]);
      setEmployees(emps);
      setShifts(sh);
      const defaultSettings = {
        workingDays: ['Mon','Tue','Wed','Thu'], weekendDays: ['Fri','Sat'],
        defaultHoursPerDay: 8, lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10,
        overtimeRequiresApproval: true, maxDailyOvertimeHours: 2,
        lateDeductionPolicy: 'none', lateDeductionAmount: 0,
        wfhEnabled: false, regularisationMaxDaysPerMonth: 2, regularisationWindowDays: 7,
        biometricApiEnabled: false, biometricApiKey: '',
      };
      setSettings(sett || defaultSettings);
      setSettingsForm(sett || defaultSettings);
      setLeaveSettings(leaveSett);
      setApprovedLeaves(leaves);
      const holidayDates = hols.map(h => h.date);
      setHolidayDates(holidayDates);
      setPeriods(pers);
      setRegularisations(regs);
      if (emps.length > 0) setClockEmp(emps[0].id);

      // Compute & persist today's attendance record for each active employee
      // so the dashboard ("Present Today" etc.) reflects same-day clock-ins
      // without waiting for an end-of-day batch process.
      const today = todayUAE();
      let todayRecs = recs;
      if (selectedMonth === today.slice(0, 7)) {
        const activeEmps = emps.filter(e => e.active);
        await Promise.all(activeEmps.map(async emp => {
          const shift = await getShiftForEmployee(emp.id, today).catch(() => null);
          await computeAndSaveAttendance({
            employee: emp,
            date: today,
            shift,
            settings: sett || defaultSettings,
            approvedLeaves: leaves,
            holidayDates,
            ramadanStart: leaveSett?.ramadanStart,
            ramadanEnd: leaveSett?.ramadanEnd,
          }).catch(() => null);
        }));
        todayRecs = await getAttendanceRecords({ period: selectedMonth }).catch(() => recs);
      }
      setRecords(todayRecs);
    } catch (err) {
      console.error('AttendanceManager loadAll:', err);
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [selectedMonth]); // eslint-disable-line react-hooks/exhaustive-deps

  // Initial load + reload when month changes (full loading screen)
  useEffect(() => { initialLoadDone.current = false; loadAll(); }, [loadAll]);

  // Auto-refresh every 30 s — silent (no loading flash) so the page stays usable
  const pollRef = useRef(null);
  useEffect(() => {
    pollRef.current = setInterval(() => { loadAll(true); }, 30000);
    return () => clearInterval(pollRef.current);
  }, [loadAll]);

  const showMsg = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await saveAttendanceSettings(settingsForm);
      setSettings(settingsForm);
      showMsg('success', 'Attendance settings saved.');
    } catch (e) { showMsg('danger', 'Failed to save: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleSaveShift = async (shift) => {
    const saved = await saveShift(shift);
    const fresh = await getShifts();
    setShifts(fresh);
    showMsg('success', 'Shift saved.');
    return saved;
  };

  const handleDeleteShift = async (id) => {
    await deleteShift(id);
    setShifts(prev => prev.filter(s => s.id !== id));
    showMsg('success', 'Shift removed.');
  };

  const handleClockIn = async () => {
    if (!clockEmp) return;
    setSaving(true);
    try {
      await recordClockEvent({ employeeId: clockEmp, eventType: 'CLOCK_IN', method: 'WEB' });
      showMsg('success', 'Clocked in successfully.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Clock-in failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleClockOut = async () => {
    if (!clockEmp) return;
    setSaving(true);
    try {
      await recordClockEvent({ employeeId: clockEmp, eventType: 'CLOCK_OUT', method: 'WEB' });
      showMsg('success', 'Clocked out successfully.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Clock-out failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleManualEntry = async () => {
    if (!manualForm.employeeId || !manualForm.eventTime) return;
    setSaving(true);
    try {
      await recordManualClockEvent({
        employeeId: manualForm.employeeId,
        eventType:  manualForm.eventType,
        eventTime:  new Date(manualForm.eventTime).toISOString(),
        notes:      manualForm.notes,
        enteredBy:  user?.id,
      });
      showMsg('success', 'Manual entry recorded.');
      setManualForm({ employeeId:'', eventType:'CLOCK_IN', eventTime:'', notes:'' });
      setManualEntry(false);
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleResolveAbsence = async (record, resolutionType, notes = '') => {
    setSaving(true);
    try {
      await upsertAttendanceRecord({
        ...record,
        resolutionType,
        resolutionNotes: notes,
        resolvedBy: user?.email || 'HR',
        status: resolutionType === 'UNAUTHORISED' ? ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE : ATTENDANCE_STATUS.PRESENT,
        absenceDeduction: resolutionType === 'UNAUTHORISED'
          ? (parseFloat(employees.find(e => e.id === record.employeeId)?.basicSalary) || 0) / 30
          : 0,
      });
      await addAttendanceAuditLog({
        employeeId: record.employeeId,
        attendanceDate: record.date,
        action: 'Absence Resolved',
        actor: user?.email || 'HR',
        oldValue: 'UNEXPLAINED_ABSENCE',
        newValue: resolutionType,
        reason: notes,
      });
      showMsg('success', 'Absence resolved.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleApproveOT = async (record) => {
    setSaving(true);
    try {
      await upsertAttendanceRecord({ ...record, overtimeApproved: true, overtimeApprovedBy: user?.email || 'HR' });
      showMsg('success', 'Overtime approved.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleApproveReg = async (id) => {
    // Sanity-check the requested clock times before we patch the attendance
    // record. All fields already exist on the loaded request row.
    const req = regularisations.find(r => r.id === id);
    if (req) {
      const ci = req.correctClockIn;
      const co = req.correctClockOut;
      if (ci && co) {
        const inMs  = new Date(ci).getTime();
        const outMs = new Date(co).getTime();
        if (isNaN(inMs) || isNaN(outMs)) {
          showMsg('danger', 'Regularisation has invalid clock times. Ask the employee to resubmit.');
          return;
        }
        if (outMs <= inMs) {
          showMsg('danger', 'Clock-out must be after clock-in. Please reject and ask the employee to resubmit.');
          return;
        }
        if (outMs - inMs > 24 * 60 * 60 * 1000) {
          showMsg('danger', 'Clock-in / clock-out span exceeds 24 hours. Please reject and ask the employee to resubmit.');
          return;
        }
        if (req.attendanceDate) {
          // Both times must fall on the requested attendance date (local calendar day).
          const day = req.attendanceDate.slice(0, 10);
          const inDay  = new Date(inMs).toISOString().slice(0, 10);
          const outDay = new Date(outMs).toISOString().slice(0, 10);
          if (inDay !== day || outDay !== day) {
            showMsg('danger', `Clock times must fall on the requested date (${day}). Please reject and ask the employee to resubmit.`);
            return;
          }
        }
      }
    }
    setSaving(true);
    try {
      await approveRegularisationRequest(id, user?.email || 'HR');
      showMsg('success', 'Regularisation approved.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleRejectReg = async (id, reason) => {
    setSaving(true);
    try {
      await rejectRegularisationRequest(id, reason, user?.email || 'HR');
      setApprovalModal(null);
      showMsg('success', 'Regularisation rejected.');
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed: ' + e.message); }
    finally { setSaving(false); }
  };

  const handleClosePeriod = async () => {
    const openItems = records.filter(r => r.missingClockOut || r.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE && !r.resolutionType).length;
    if (openItems > 0) {
      showMsg('warning', `Cannot close period: ${openItems} unresolved item${openItems !== 1 ? 's' : ''} (missing clock-outs or unexplained absences).`);
      return;
    }
    setSaving(true);
    try {
      await closeAttendancePeriod(selectedMonth, user?.email || 'HR');
      showMsg('success', `Attendance period ${selectedMonth} closed. Payroll can now proceed.`);
      await loadAll();
    } catch (e) { showMsg('danger', 'Failed to close period: ' + e.message); }
    finally { setSaving(false); }
  };

  const exportRecordsCSV = () => {
    const headers = ['Date','Employee','Department','Status','Clock In','Clock Out','Hours','Late (min)','Early Dep (min)','OT Hours','OT Amount (AED)'];
    const rows = filteredRecords.map(r => {
      const emp = employees.find(e => e.id === r.employeeId);
      return [
        formatDateUAE(r.date), emp?.name || '—', emp?.department || '—',
        STATUS_LABELS[r.status] || r.status,
        r.clockInTime ? new Date(r.clockInTime).toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit' }) : '—',
        r.clockOutTime ? new Date(r.clockOutTime).toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit' }) : '—',
        r.totalHours?.toFixed(2) || '0',
        r.lateMinutes || 0,
        r.earlyDepartureMinutes || 0,
        r.overtimeHours?.toFixed(2) || '0',
        r.overtimeAmount?.toFixed(2) || '0',
      ];
    });
    const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type:'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `attendance_${selectedMonth}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  // ── Derived data ────────────────────────────────────────────────────────────
  const todayStr = todayUAE();
  const todayRecords = records.filter(r => r.date === todayStr);
  // MISSING_CLOCK_OUT on today's date means the employee clocked in and
  // hasn't clocked out yet — i.e. they are currently present.
  const presentToday = todayRecords.filter(r => [ATTENDANCE_STATUS.PRESENT, ATTENDANCE_STATUS.LATE, ATTENDANCE_STATUS.OVERTIME, ATTENDANCE_STATUS.PRESENT_REMOTE, ATTENDANCE_STATUS.MISSING_CLOCK_OUT].includes(r.status));
  const absentToday  = todayRecords.filter(r => r.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE || r.status === ATTENDANCE_STATUS.ABSENT);
  const lateToday    = todayRecords.filter(r => r.lateMinutes > 0);
  const onLeaveToday = approvedLeaves.filter(l => l.startDate <= todayStr && l.endDate >= todayStr);
  // Derive missing clock-out dynamically: any record with a clock-in but no clock-out
  // on a past day. The DB field r.missingClockOut is not set by the employee RPC,
  // so relying on it would always produce an empty list.
  const missingClockOut = records.filter(r =>
    r.clockInTime && !r.clockOutTime && r.date < todayStr
  );
  const unexplainedAbsences = records.filter(r => r.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE && !r.resolutionType);
  const pendingOT    = records.filter(r => r.overtimeHours > 0 && !r.overtimeApproved);
  const pendingRegs  = regularisations.filter(r => r.status === 'Pending');
  const currentPeriod = periods.find(p => p.period === selectedMonth);
  const periodClosed  = currentPeriod?.status === 'closed';

  const filteredRecords = records.filter(r => !filterEmp || r.employeeId === filterEmp);

  const ramadanStart = leaveSettings?.ramadanStart;
  const ramadanEnd   = leaveSettings?.ramadanEnd;
  const ramadanActive = leaveSettings?.ramadanActive;

  const weekendDays = settings?.weekendDays || ['Fri','Sat'];

  const TABS = [
    { id:'dashboard',      label:'Dashboard',      icon:BarChart2 },
    { id:'clock',          label:'Clock In/Out',   icon:Clock },
    { id:'records',        label:`Records`,        icon:Calendar },
    { id:'absences',       label:`Absences${unexplainedAbsences.length > 0 ? ` (${unexplainedAbsences.length})` : ''}`, icon:AlertTriangle },
    { id:'overtime',       label:`Overtime${pendingOT.length > 0 ? ` (${pendingOT.length})` : ''}`, icon:AlertCircle },
    { id:'regularisation', label:`Corrections${pendingRegs.length > 0 ? ` (${pendingRegs.length})` : ''}`, icon:RefreshCw },
    { id:'reports',        label:'Reports',        icon:Download },
    ...(biometricEnabled ? [{ id:'biometric', label:'Biometric Import', icon:Fingerprint }] : []),
    { id:'settings',       label:'Settings',       icon:Settings },
  ];

  if (loading) return <div style={{ padding:40, textAlign:'center', color:'var(--gray-400)' }}>Loading attendance module…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Attendance</h2>
        <div className="page-header-actions">
          <div style={{ display:'flex', alignItems:'center', gap:4 }}>
            <button className="btn btn-ghost btn-icon btn-sm" title="Previous month" onClick={() => {
              const [y, m] = selectedMonth.split('-').map(Number);
              const d = new Date(y, m - 2, 1);
              setSelectedMonth(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
            }}><ChevronLeft size={16}/></button>
            <select className="form-control" style={{ width:160 }} value={selectedMonth}
              onChange={e => setSelectedMonth(e.target.value)}>
              {Array.from({ length:24 }, (_, i) => {
                const d = new Date(); d.setMonth(d.getMonth() - i);
                const val = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
                return <option key={val} value={val}>{d.toLocaleString('en-AE', { month:'long', year:'numeric' })}</option>;
              })}
            </select>
            <button className="btn btn-ghost btn-icon btn-sm" title="Next month" onClick={() => {
              const [y, m] = selectedMonth.split('-').map(Number);
              const d = new Date(y, m, 1);
              const next = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
              const now = new Date();
              const max = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
              if (next <= max) setSelectedMonth(next);
            }}><ChevronRight size={16}/></button>
          </div>
          <button className="btn btn-outline btn-sm" onClick={() => loadAll()} disabled={loading} title="Refresh">
            <RefreshCw size={14}/> Refresh
          </button>
          {!periodClosed ? (
            <button className="btn btn-outline btn-sm" onClick={handleClosePeriod} disabled={saving}>
              <Lock size={14}/> Close Period
            </button>
          ) : (
            <span className="badge badge-green" style={{ padding:'6px 12px' }}><CheckCircle size={12} style={{ marginRight:4 }}/>Period Closed</span>
          )}
        </div>
      </div>

      <div className="page-body">
        {msg && <div className={`alert alert-${msg.type} mb-4`}><AlertCircle size={15}/>{msg.text}</div>}

        {/* Ramadan notice */}
        {ramadanActive && (
          <div className="alert alert-info mb-4">
            <Info size={15}/>
            <strong>Ramadan Period Active</strong> ({formatDateUAE(ramadanStart)} – {formatDateUAE(ramadanEnd)}):
            Art. 17 — Expected working hours reduced by 2 hrs/day for all employees. Overtime threshold adjusted accordingly.
          </div>
        )}

        {/* Art. 44 — consecutive absence warning */}
        {employees.map(emp => {
          const empRecs = records.filter(r => r.employeeId === emp.id);
          const { flagged, consecutiveDays, since } = checkConsecutiveAbsences(empRecs, weekendDays, holidayDates);
          if (!flagged) return null;
          return (
            <div key={emp.id} className="alert alert-danger mb-2">
              <AlertTriangle size={15}/>
              <strong>Art. 44 Warning:</strong> {emp.name} has been absent for {consecutiveDays} consecutive working days since {formatDateUAE(since)}.
              UAE Labour Law Art. 44 threshold reached — HR action required.
            </div>
          );
        })}

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

        {/* ── DASHBOARD TAB ── */}
        {tab === 'dashboard' && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Present Today</div>
                <div className="stat-value" style={{ color:'var(--success)' }}>{presentToday.length}</div>
                <div className="stat-sub">of {employees.filter(e => e.employmentStatus !== 'Terminated').length} active</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">On Leave Today</div>
                <div className="stat-value" style={{ color:'var(--primary)' }}>{onLeaveToday.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Absent / Unexplained</div>
                <div className="stat-value" style={{ color: absentToday.length > 0 ? 'var(--danger)' : 'var(--gray-400)' }}>{absentToday.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Late Today</div>
                <div className="stat-value" style={{ color: lateToday.length > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{lateToday.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Missing Clock-Out</div>
                <div className="stat-value" style={{ color: missingClockOut.length > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{missingClockOut.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Pending OT Approval</div>
                <div className="stat-value" style={{ color: pendingOT.length > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{pendingOT.length}</div>
              </div>
            </div>

            {/* Late arrivals today */}
            {lateToday.length > 0 && (
              <div className="card mb-4">
                <div className="card-header"><h3>Late Arrivals Today</h3></div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Employee</th><th>Department</th><th>Clock In</th><th>Late By</th></tr></thead>
                    <tbody>
                      {lateToday.map(r => {
                        const emp = employees.find(e => e.id === r.employeeId);
                        return (
                          <tr key={r.id}>
                            <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                            <td className="text-muted">{emp?.department || '—'}</td>
                            <td>{r.clockInTime ? new Date(r.clockInTime).toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit' }) : '—'}</td>
                            <td><span className="badge badge-amber">{r.lateMinutes} min</span></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Unexplained absences */}
            {unexplainedAbsences.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h3>Unexplained Absences — {selectedMonth}</h3>
                  <span className="badge badge-red">{unexplainedAbsences.length}</span>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Employee</th><th>Date</th><th>Department</th><th>Action</th></tr></thead>
                    <tbody>
                      {unexplainedAbsences.slice(0, 10).map(r => {
                        const emp = employees.find(e => e.id === r.employeeId);
                        return (
                          <tr key={r.id}>
                            <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                            <td>{formatDateUAE(r.date)}</td>
                            <td className="text-muted">{emp?.department || '—'}</td>
                            <td>
                              <div className="flex gap-2">
                                <button className="btn btn-danger btn-sm" onClick={() => handleResolveAbsence(r, 'UNAUTHORISED', 'Marked as unauthorised absence')}>
                                  Unauthorised
                                </button>
                                <button className="btn btn-outline btn-sm" onClick={() => handleResolveAbsence(r, 'WFH', 'Approved as WFH')}>
                                  WFH
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

        {/* ── CLOCK IN/OUT TAB ── */}
        {tab === 'clock' && (
          <div className="form-grid form-grid-2" style={{ gap:16 }}>
            <div className="card">
              <div className="card-header"><h3><Clock size={15} style={{ marginRight:6 }}/>Clock In / Out</h3></div>
              <div className="card-body">
                <div className="form-group mb-4">
                  <label>Employee</label>
                  <select className="form-control" value={clockEmp} onChange={e => setClockEmp(e.target.value)}>
                    {employees.filter(e => e.employmentStatus !== 'Terminated').map(e => (
                      <option key={e.id} value={e.id}>{e.name}</option>
                    ))}
                  </select>
                </div>
                <div style={{ display:'flex', gap:12 }}>
                  <button className="btn btn-success" style={{ flex:1, padding:'14px' }} onClick={handleClockIn} disabled={saving}>
                    <Clock size={18}/> Clock In
                  </button>
                  <button className="btn btn-danger" style={{ flex:1, padding:'14px' }} onClick={handleClockOut} disabled={saving}>
                    <Clock size={18}/> Clock Out
                  </button>
                </div>
                <div style={{ marginTop:16, textAlign:'center', fontSize:12, color:'var(--gray-500)' }}>
                  Current time: {new Date().toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit', timeZone:'Asia/Dubai' })} (UAE GMT+4)
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3>Manual Entry (HR)</h3>
                <button className="btn btn-outline btn-sm" onClick={() => setManualEntry(!manualEntry)}>
                  {manualEntry ? 'Cancel' : <><Plus size={13}/> Add Manual Entry</>}
                </button>
              </div>
              {manualEntry && (
                <div className="card-body">
                  <div className="form-grid form-grid-2">
                    <div className="form-group">
                      <label>Employee</label>
                      <select className="form-control" value={manualForm.employeeId} onChange={e => setManualForm(p => ({ ...p, employeeId: e.target.value }))}>
                        <option value="">Select…</option>
                        {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Event Type</label>
                      <select className="form-control" value={manualForm.eventType} onChange={e => setManualForm(p => ({ ...p, eventType: e.target.value }))}>
                        <option value="CLOCK_IN">Clock In</option>
                        <option value="CLOCK_OUT">Clock Out</option>
                      </select>
                    </div>
                    <div className="form-group" style={{ gridColumn:'1/-1' }}>
                      <label>Date & Time *</label>
                      <input className="form-control" type="datetime-local" value={manualForm.eventTime} onChange={e => setManualForm(p => ({ ...p, eventTime: e.target.value }))}/>
                    </div>
                    <div className="form-group" style={{ gridColumn:'1/-1' }}>
                      <label>Notes (required for manual entries)</label>
                      <input className="form-control" value={manualForm.notes} onChange={e => setManualForm(p => ({ ...p, notes: e.target.value }))} placeholder="Reason for manual entry"/>
                    </div>
                  </div>
                  <button className="btn btn-primary mt-3" onClick={handleManualEntry} disabled={saving || !manualForm.employeeId || !manualForm.eventTime}>
                    <Check size={14}/> Save Manual Entry
                  </button>
                </div>
              )}
              {!manualEntry && (
                <div style={{ padding:'20px', color:'var(--gray-500)', fontSize:13 }}>
                  Use manual entry to record clock events on behalf of an employee. All manual entries are flagged as "MANUAL" in the audit trail.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── RECORDS TAB ── */}
        {tab === 'records' && (
          <div className="card">
            <div className="card-header">
              <h3>Attendance Records — {selectedMonth}</h3>
              <div style={{ display:'flex', gap:8 }}>
                <select className="form-control" style={{ width:180 }} value={filterEmp} onChange={e => setFilterEmp(e.target.value)}>
                  <option value="">All Employees</option>
                  {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
                <button className="btn btn-outline btn-sm" onClick={exportRecordsCSV}><Download size={14}/> CSV</button>
              </div>
            </div>
            {filteredRecords.length === 0 ? (
              <div className="empty-state"><Calendar size={40}/><h3>No records</h3><p>No attendance records for this period.</p></div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th><th>Employee</th><th>Status</th>
                      <th>Clock In</th><th>Clock Out</th><th>Hours</th>
                      <th>Late</th><th>OT Hours</th><th>OT Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRecords.map(r => {
                      const emp = employees.find(e => e.id === r.employeeId);
                      return (
                        <tr key={r.id || r.date + r.employeeId}>
                          <td>{formatDateUAE(r.date)}</td>
                          <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                          <td><AttendanceBadge status={r.status}/></td>
                          <td className="text-sm">{r.clockInTime ? new Date(r.clockInTime).toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit' }) : '—'}</td>
                          <td className="text-sm">{r.clockOutTime ? new Date(r.clockOutTime).toLocaleTimeString('en-AE', { hour:'2-digit', minute:'2-digit' }) : r.missingClockOut ? <span className="badge badge-amber">Missing</span> : '—'}</td>
                          <td>{r.totalHours > 0 ? formatHours(r.totalHours) : '—'}</td>
                          <td>{r.lateMinutes > 0 ? <span className="badge badge-amber">{r.lateMinutes}m</span> : '—'}</td>
                          <td>{r.overtimeHours > 0 ? <span className="badge badge-green">{formatHours(r.overtimeHours)}</span> : '—'}</td>
                          <td>{r.overtimeAmount > 0 ? formatAED(r.overtimeAmount) : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── ABSENCES TAB ── */}
        {tab === 'absences' && (
          <div className="card">
            <div className="card-header">
              <h3>Unexplained Absences</h3>
              <span className="badge badge-red">{unexplainedAbsences.length} unresolved</span>
            </div>
            {unexplainedAbsences.length === 0 ? (
              <div className="empty-state"><CheckCircle size={40} style={{ color:'var(--success)' }}/><h3>No unexplained absences</h3></div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Employee</th><th>Date</th><th>Department</th><th>Resolution</th></tr></thead>
                  <tbody>
                    {unexplainedAbsences.map(r => {
                      const emp = employees.find(e => e.id === r.employeeId);
                      return (
                        <tr key={r.id || r.date + r.employeeId}>
                          <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                          <td>{formatDateUAE(r.date)}</td>
                          <td className="text-muted">{emp?.department || '—'}</td>
                          <td>
                            <div className="flex gap-2">
                              <button className="btn btn-danger btn-sm" onClick={() => handleResolveAbsence(r, 'UNAUTHORISED', 'Unauthorised absence — payroll deduction applied')}>
                                Unauthorised
                              </button>
                              {settings?.wfhEnabled && (
                                <button className="btn btn-outline btn-sm" onClick={() => handleResolveAbsence(r, 'WFH', 'Approved as WFH')}>
                                  WFH
                                </button>
                              )}
                            </div>
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

        {/* ── OVERTIME TAB ── */}
        {tab === 'overtime' && (
          <div className="card">
            <div className="card-header">
              <h3>Overtime Records — {selectedMonth}</h3>
              <span className="badge badge-amber">{pendingOT.length} pending approval</span>
            </div>
            {records.filter(r => r.overtimeHours > 0).length === 0 ? (
              <div className="empty-state"><AlertCircle size={40}/><h3>No overtime records</h3></div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Employee</th><th>Date</th><th>OT Hours</th><th>Type</th><th>Amount (AED)</th><th>Approved</th><th></th></tr>
                  </thead>
                  <tbody>
                    {records.filter(r => r.overtimeHours > 0).map(r => {
                      const emp = employees.find(e => e.id === r.employeeId);
                      return (
                        <tr key={r.id || r.date + r.employeeId}>
                          <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                          <td>{formatDateUAE(r.date)}</td>
                          <td>{formatHours(r.overtimeHours)}</td>
                          <td className="text-sm text-muted">{r.overtimeType || 'STANDARD'}</td>
                          <td>{formatAED(r.overtimeAmount)}</td>
                          <td>
                            {r.overtimeApproved
                              ? <span className="badge badge-green"><CheckCircle size={11} style={{ marginRight:3 }}/>Approved by {r.overtimeApprovedBy}</span>
                              : <span className="badge badge-amber">Pending</span>}
                          </td>
                          <td>
                            {!r.overtimeApproved && (
                              <button className="btn btn-success btn-sm" onClick={() => handleApproveOT(r)}>
                                <Check size={13}/> Approve
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

        {/* ── REGULARISATION TAB ── */}
        {tab === 'regularisation' && (
          <div className="card">
            <div className="card-header">
              <h3>Attendance Correction Requests</h3>
              <span className="badge badge-amber">{pendingRegs.length} pending</span>
            </div>
            {regularisations.length === 0 ? (
              <div className="empty-state"><RefreshCw size={40}/><h3>No correction requests</h3></div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Employee</th><th>Date</th><th>Correct In</th><th>Correct Out</th><th>Reason</th><th>Status</th><th></th></tr>
                  </thead>
                  <tbody>
                    {regularisations.map(r => {
                      const emp = employees.find(e => e.id === r.employeeId);
                      return (
                        <tr key={r.id}>
                          <td style={{ fontWeight:500 }}>{emp?.name || '—'}</td>
                          <td>{formatDateUAE(r.attendanceDate)}</td>
                          <td className="font-mono text-sm">{r.correctClockIn}</td>
                          <td className="font-mono text-sm">{r.correctClockOut}</td>
                          <td className="text-muted text-sm">{r.reason}</td>
                          <td>
                            <span className={`badge ${r.status === 'Approved' ? 'badge-green' : r.status === 'Rejected' ? 'badge-red' : 'badge-amber'}`}>
                              {r.status}
                            </span>
                          </td>
                          <td>
                            {r.status === 'Pending' && (
                              <div className="flex gap-2">
                                <button className="btn btn-success btn-sm" onClick={() => handleApproveReg(r.id)}><Check size={13}/></button>
                                <button className="btn btn-danger btn-sm" onClick={() => setApprovalModal({ id: r.id, action: 'Reject' })}><X size={13}/></button>
                              </div>
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

        {/* ── REPORTS TAB ── */}
        {tab === 'reports' && (
          <div>
            <div className="card mb-4">
              <div className="card-header">
                <h3>Monthly Summary — {selectedMonth}</h3>
                <button className="btn btn-outline btn-sm" onClick={exportRecordsCSV}><Download size={14}/> Export CSV</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Employee</th><th>Dept</th><th>Present</th><th>Absent</th><th>On Leave</th><th>Late</th><th>OT Hours</th><th>OT Amount</th><th>Deductions</th></tr>
                  </thead>
                  <tbody>
                    {employees.filter(e => e.employmentStatus !== 'Terminated').map(emp => {
                      const empRecs = records.filter(r => r.employeeId === emp.id);
                      const present = empRecs.filter(r => [ATTENDANCE_STATUS.PRESENT, ATTENDANCE_STATUS.LATE, ATTENDANCE_STATUS.OVERTIME, ATTENDANCE_STATUS.PRESENT_REMOTE].includes(r.status)).length;
                      const absent  = empRecs.filter(r => r.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE || r.status === ATTENDANCE_STATUS.ABSENT).length;
                      const onLeave = empRecs.filter(r => r.status === ATTENDANCE_STATUS.ON_LEAVE).length;
                      const late    = empRecs.filter(r => r.lateMinutes > 0).length;
                      const otHours = empRecs.reduce((s, r) => s + (r.overtimeHours || 0), 0);
                      const otAmt   = empRecs.reduce((s, r) => s + (r.overtimeAmount || 0), 0);
                      const deds    = empRecs.reduce((s, r) => s + (r.absenceDeduction || 0) + (r.lateDeduction || 0), 0);
                      return (
                        <tr key={emp.id}>
                          <td style={{ fontWeight:500 }}>{emp.name}</td>
                          <td className="text-muted text-sm">{emp.department || '—'}</td>
                          <td style={{ color:'var(--success)' }}>{present}</td>
                          <td style={{ color: absent > 0 ? 'var(--danger)' : 'var(--gray-400)' }}>{absent}</td>
                          <td style={{ color:'var(--primary)' }}>{onLeave}</td>
                          <td style={{ color: late > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{late}</td>
                          <td>{otHours > 0 ? formatHours(otHours) : '—'}</td>
                          <td>{otAmt > 0 ? formatAED(otAmt) : '—'}</td>
                          <td style={{ color: deds > 0 ? 'var(--danger)' : 'var(--gray-400)' }}>{deds > 0 ? `-${formatAED(deds)}` : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── BIOMETRIC IMPORT TAB ── */}
        {tab === 'biometric' && biometricEnabled && (
          <BiometricImport employees={employees} />
        )}

        {/* ── SETTINGS TAB ── */}
        {tab === 'settings' && settingsForm && (
          <div>
            <div className="card mb-4">
              <div className="card-header">
                <h3>Attendance Configuration</h3>
                <button className="btn btn-primary btn-sm" onClick={handleSaveSettings} disabled={saving}>
                  <Save size={14}/> {saving ? 'Saving…' : 'Save Settings'}
                </button>
              </div>
              <div className="card-body">
                <div className="form-grid form-grid-2">
                  <div className="form-group">
                    <label>Default Hours Per Day</label>
                    <input className="form-control" type="number" min={1} max={12} step={0.5} value={settingsForm.defaultHoursPerDay}
                      onChange={e => setSettingsForm(p => ({ ...p, defaultHoursPerDay: parseFloat(e.target.value) }))}/>
                    <span className="hint">Art. 17: max 8 hrs/day ordinary working hours</span>
                  </div>
                  <div className="form-group">
                    <label>Late Grace Period (minutes)</label>
                    <input className="form-control" type="number" min={0} max={60} value={settingsForm.lateGraceMinutes}
                      onChange={e => setSettingsForm(p => ({ ...p, lateGraceMinutes: parseInt(e.target.value) }))}/>
                  </div>
                  <div className="form-group">
                    <label>Early Departure Grace (minutes)</label>
                    <input className="form-control" type="number" min={0} max={60} value={settingsForm.earlyDepartureGraceMinutes}
                      onChange={e => setSettingsForm(p => ({ ...p, earlyDepartureGraceMinutes: parseInt(e.target.value) }))}/>
                  </div>
                  <div className="form-group">
                    <label>Max Daily Overtime Hours (alert threshold)</label>
                    <input className="form-control" type="number" min={0} max={4} step={0.5} value={settingsForm.maxDailyOvertimeHours}
                      onChange={e => setSettingsForm(p => ({ ...p, maxDailyOvertimeHours: parseFloat(e.target.value) }))}/>
                    <span className="hint">Art. 19: max 2 hrs/day overtime — alert HR if exceeded</span>
                  </div>
                  <div className="form-group">
                    <label>Late Deduction Policy</label>
                    <select className="form-control" value={settingsForm.lateDeductionPolicy}
                      onChange={e => setSettingsForm(p => ({ ...p, lateDeductionPolicy: e.target.value }))}>
                      <option value="none">No deduction</option>
                      <option value="per_minute">Per minute (AED/min)</option>
                      <option value="per_occurrence">Per occurrence (flat AED)</option>
                    </select>
                  </div>
                  {settingsForm.lateDeductionPolicy !== 'none' && (
                    <div className="form-group">
                      <label>Deduction Amount (AED)</label>
                      <input className="form-control" type="number" min={0} step={0.01} value={settingsForm.lateDeductionAmount}
                        onChange={e => setSettingsForm(p => ({ ...p, lateDeductionAmount: parseFloat(e.target.value) }))}/>
                    </div>
                  )}
                  <div className="form-group">
                    <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
                      <input type="checkbox" checked={settingsForm.overtimeRequiresApproval}
                        onChange={e => setSettingsForm(p => ({ ...p, overtimeRequiresApproval: e.target.checked }))}/>
                      Overtime requires pre-approval
                    </label>
                  </div>
                  <div className="form-group">
                    <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
                      <input type="checkbox" checked={settingsForm.wfhEnabled}
                        onChange={e => setSettingsForm(p => ({ ...p, wfhEnabled: e.target.checked }))}/>
                      Enable Work-From-Home (WFH) status (Min. Res. 279/2022)
                    </label>
                  </div>
                  <div className="form-group">
                    <label>Regularisation: Max days/month without justification</label>
                    <input className="form-control" type="number" min={0} max={10} value={settingsForm.regularisationMaxDaysPerMonth}
                      onChange={e => setSettingsForm(p => ({ ...p, regularisationMaxDaysPerMonth: parseInt(e.target.value) }))}/>
                  </div>
                  <div className="form-group">
                    <label>Regularisation: Submission window (days)</label>
                    <input className="form-control" type="number" min={1} max={30} value={settingsForm.regularisationWindowDays}
                      onChange={e => setSettingsForm(p => ({ ...p, regularisationWindowDays: parseInt(e.target.value) }))}/>
                    <span className="hint">Employees must submit corrections within this many days</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Shifts */}
            <div className="card">
              <div className="card-header">
                <h3>Shifts</h3>
                <button className="btn btn-primary btn-sm" onClick={() => setShiftModal({})}>
                  <Plus size={14}/> New Shift
                </button>
              </div>
              {shifts.length === 0 ? (
                <div className="empty-state"><Clock size={40}/><h3>No shifts configured</h3><p>Create a shift to assign to employees.</p></div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Name</th><th>Type</th><th>Hours</th><th>Start</th><th>End</th><th>Break</th><th>Late Grace</th><th></th></tr></thead>
                    <tbody>
                      {shifts.map(s => (
                        <tr key={s.id}>
                          <td style={{ fontWeight:500 }}>{s.name}</td>
                          <td className="text-sm text-muted">{s.shiftType}</td>
                          <td>{s.expectedHours}h</td>
                          <td className="font-mono text-sm">{s.startTime || '—'}</td>
                          <td className="font-mono text-sm">{s.endTime || '—'}</td>
                          <td>{s.breakMinutes}m</td>
                          <td>{s.lateGraceMinutes}m</td>
                          <td>
                            <div className="flex gap-2">
                              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setShiftModal(s)}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                              </button>
                              <button className="btn btn-ghost btn-icon btn-sm text-danger" onClick={() => handleDeleteShift(s.id)}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Shift Modal */}
      {shiftModal !== null && (
        <ShiftModal
          shift={shiftModal?.id ? shiftModal : null}
          onSave={handleSaveShift}
          onClose={() => setShiftModal(null)}
        />
      )}

      {/* Rejection Modal */}
      {approvalModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth:440 }}>
            <div className="modal-header">
              <h3>Reject Correction Request</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setApprovalModal(null)}><X size={18}/></button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Rejection Reason *</label>
                <textarea className="form-control" rows={3} value={approvalReason}
                  onChange={e => setApprovalReason(e.target.value)} placeholder="Enter reason…" style={{ resize:'vertical' }}/>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setApprovalModal(null)} disabled={saving}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleRejectReg(approvalModal.id, approvalReason)}
                disabled={saving || !approvalReason.trim()}>
                {saving ? 'Saving…' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
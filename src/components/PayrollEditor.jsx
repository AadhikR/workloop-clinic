import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Download, Eye, Upload, AlertCircle, Plus, ChevronDown, CheckCircle, FileText, Info, Send, Lock, ShieldCheck, RefreshCw, GitCompare, Search, Undo2, X, ListChecks, Clock } from 'lucide-react';
import { generateSIF, generateSIFFilename, generateCorrectedSIF } from '../utils/sifGenerator';
import { parseCSV, readFileAsText } from '../utils/csvImport';
import { createPayslipRecords, saveWpsTracking,
         submitPayrollForApproval, approvePayroll, rejectPayroll, recallPayrollApproval } from '../utils/storage';
import { createNotifications } from '../utils/notificationStorage';
import AllowDeductPanel from './AllowDeductPanel';
import SIFPreviewModal from './SIFPreviewModal';
import { downloadPayslip, downloadAllPayslips } from '../utils/payslipGenerator';
import { calculatePayrollLeaveDeductions } from '../utils/leaveEngine';
import { getLeaveRequests } from '../utils/leaveStorage';
import { getAttendancePayrollData, getOvertimeFromRoster } from '../utils/attendanceStorage';
import { getAdvances } from '../utils/storage';
import { formatDateUAE, daysUntil, validateBankRoutingCode } from '../utils/uaeValidators';
import { getApprovedUnpaidExpenses, markExpensesPaid } from '../utils/expenseStorage';
import { getPayrollSummaryFromAttendance } from '../utils/attendanceEngine';
import { calculatePayrollEntry, calculatePayrollTotals, withCalculatedPayrollFields } from '../utils/payrollCalculator';
import { validatePayrollRun } from '../utils/payrollValidation';
import { getAdvanceInstallmentForPeriod, stageAdvancesForPayroll } from '../utils/advanceSchedule';
import { saveAdvanceRepayment } from '../utils/storage';

function getMonthName(month) {
  return ['January','February','March','April','May','June',
          'July','August','September','October','November','December'][month - 1];
}

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function normaliseEntry(e) {
  return {
    allowance: e.allowance ?? e.variableAllowance ?? 0,
    increment: e.increment ?? 0,
    bonus: e.bonus ?? 0,
    otherPay: e.otherPay ?? 0,
    leaveDeduction: e.leaveDeduction ?? 0, // editable leave deduction (pre-filled from Leave module)
    additionalAllowances: e.additionalAllowances ?? [],
    deductions: e.deductions ?? [],
    ...e,
  };
}

/** Add, replace, or remove a reserved payroll integration line item. */
function updateAutoPayrollItem(entries, employeeId, field, label, amount = null, metadata = {}) {
  return entries.map(entry => {
    if (entry.employeeId !== employeeId) return entry;
    const remaining = (entry[field] || []).filter(item => item.label !== label);
    return {
      ...entry,
      [field]: amount === null
        ? remaining
        : [...remaining, { label, amount: parseFloat(amount.toFixed(2)), recurrence: 'one_time', source: 'automatic', ...metadata }],
    };
  });
}

function PayrollBreakdownRow({ label, amount, source, deduction = false, total = false }) {
  const numericAmount = parseFloat(amount) || 0;
  if (!total && numericAmount === 0) return null;
  return (
    <div className={`payroll-breakdown-row${total ? ' total' : ''}`}>
      <div>
        <span>{label}</span>
        {source && <small>{source}</small>}
      </div>
      <strong className={deduction ? 'deduction' : ''}>
        {deduction && numericAmount > 0 ? '− ' : ''}AED {numericAmount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
      </strong>
    </div>
  );
}

// ── WPS tracking helpers (Feature 9) ─────────────────────────────────────────
const WPS_STATUS_LABELS = {
  draft:             'Not Submitted',
  sif_generated:     'SIF Generated',
  submitted:         'Submitted to Bank',
  confirmed:         'Confirmed',
  partial_rejection: 'Partial Rejection',
  failed:            'Failed',
};
const WPS_STATUS_BADGES = {
  draft:             'badge-yellow',
  sif_generated:     'badge-blue',
  submitted:         'badge-amber',
  confirmed:         'badge-green',
  partial_rejection: 'badge-amber',
  failed:            'badge-red',
};
const WPS_ENTRY_BADGES = { pending: 'badge-yellow', paid: 'badge-green', rejected: 'badge-red' };
const WPS_ENTRY_LABELS = { pending: 'Pending', paid: 'Paid', rejected: 'Rejected' };

// ── Payslip download handler ─────────────────────────────────────────────────
function handleDownloadPayslip(company, employees, payroll, entry) {
  const emp = employees.find(e => e.id === entry.employeeId);
  if (!emp) return;
  downloadPayslip(company, emp, payroll, entry);
}

export default function PayrollEditor({ payroll, employees, company, onSave, onBack }) {
  const [entries, setEntries] = useState(payroll.entries.map(normaliseEntry));
  const [meta, setMeta] = useState({
    paymentDate: payroll.paymentDate,
    sequenceNo: payroll.sequenceNo,
    scrBankRoutingCode: payroll.scrBankRoutingCode,
    description: payroll.description,
  });
  const [preview, setPreview]           = useState(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitting, setSubmitting]       = useState(false);
  const [importMsg, setImportMsg] = useState(null);
  const [showPanel, setShowPanel] = useState(false);
  const [saveStatus, setSaveStatus] = useState('saved'); // saved | unsaved | saving | failed
  const [saveError, setSaveError] = useState('');
  const [leaveDeductions, setLeaveDeductions] = useState({}); // { [employeeId]: deductionResult }
  const [attendanceData, setAttendanceData]   = useState(null); // { periodClosed, payrollReady, byEmployee }
  const [advanceData, setAdvanceData]         = useState({}); // { [employeeId]: advance[] }
  const [advancesLoaded, setAdvancesLoaded]   = useState(false);
  const [expenseData, setExpenseData]         = useState({}); // { [employeeId]: expense[] } — approved+unpaid
  const [rosterOvertime, setRosterOvertime]   = useState({}); // { [employeeId]: { overtimeHours, plannedHours, actualHours } }
  const [attendanceWarning, setAttendanceWarning] = useState(false);
  const autoSaveTimer = useRef(null);
  const fileRef = useRef();

  // WPS tracking state (Feature 9) — initialised from payroll prop
  const [wpsStatus,        setWpsStatus]        = useState(payroll.wpsStatus      ?? 'draft');
  const [wpsSubmittedAt,   setWpsSubmittedAt]   = useState(payroll.wpsSubmittedAt ? payroll.wpsSubmittedAt.slice(0, 10) : '');
  const [wpsConfirmedAt,   setWpsConfirmedAt]   = useState(payroll.wpsConfirmedAt ? payroll.wpsConfirmedAt.slice(0, 10) : '');
  const [wpsReferenceNo,   setWpsReferenceNo]   = useState(payroll.wpsReferenceNo ?? '');
  const [wpsEntryStatuses, setWpsEntryStatuses] = useState(() => {
    const map = {};
    for (const e of payroll.entries) {
      map[e.employeeId] = {
        status: e.wpsPaymentStatus   ?? 'pending',
        reason: e.wpsRejectionReason ?? '',
      };
    }
    return map;
  });
  const [wpsSaving, setWpsSaving] = useState(false);
  const [wpsSaveOk, setWpsSaveOk] = useState(false);

  // Payroll Approval state (Feature 17)
  const [approvalStatus,  setApprovalStatus]  = useState(payroll.approvalStatus  ?? 'draft');
  const [approvalBusy,    setApprovalBusy]    = useState(false);
  const [approvalMsg,     setApprovalMsg]     = useState(null); // { type, text }
  const [rejectOpen,      setRejectOpen]      = useState(false);
  const [rejectReason,    setRejectReason]    = useState('');
  const [approvedBy]                          = useState(payroll.approvedBy      ?? '');
  const [, setApprovedAt]                     = useState(payroll.approvedAt      ?? null);
  const [submittedBy,     setSubmittedBy]     = useState(payroll.submittedBy     ?? '');
  const [rejectionReason, setRejectionReason] = useState(payroll.rejectionReason ?? '');

  const isLocked = payroll.status === 'generated';
  const approvalLocked = !isLocked && (approvalStatus === 'pending_approval' || approvalStatus === 'approved');
  const editingLocked  = isLocked || approvalLocked;

  // View Changes modal state (PAY-7)
  const [showChanges, setShowChanges] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const [entrySearch, setEntrySearch] = useState('');
  const [entryFilter, setEntryFilter] = useState('all');
  const [detailEmployeeId, setDetailEmployeeId] = useState(null);

  // WPS per-employee search (PAY-14)
  const [wpsSearch, setWpsSearch] = useState('');

  // Load leave deductions for this payroll period and pre-fill entry fields
  useEffect(() => {
    const [y, m] = payroll.period.split('-').map(Number);
    const periodStart = `${y}-${String(m).padStart(2,'0')}-01`;
    const daysInMonth = new Date(y, m, 0).getDate();
    const periodEnd   = `${y}-${String(m).padStart(2,'0')}-${String(daysInMonth).padStart(2,'0')}`;

    getLeaveRequests({ status: 'Approved', year: y }).then(leaves => {
      const deductMap = {};
      for (const emp of employees) {
        const empLeaves = leaves.filter(l => l.employeeId === emp.id);
        if (empLeaves.length > 0) {
          const result = calculatePayrollLeaveDeductions(empLeaves, periodStart, periodEnd, emp.basicSalary);
          if (result.totalDeduction > 0) {
            deductMap[emp.id] = result;
          }
        }
      }
      setLeaveDeductions(deductMap);

      // Pre-fill leaveDeduction on entries that don't already have a manual override
      setEntries(prev => prev.map(entry => {
        const calc = deductMap[entry.employeeId];
        // Only pre-fill if the entry has no existing leaveDeduction value (0 or undefined)
        if (calc && (!entry.leaveDeduction || entry.leaveDeduction === 0)) {
          return { ...entry, leaveDeduction: parseFloat(calc.totalDeduction.toFixed(2)) };
        }
        return entry;
      }));
    }).catch(() => {}); // leave module may not be set up yet — fail silently
  }, [payroll.period, employees]);

  // Load only advances scheduled for this exact payroll period. Settled,
  // cancelled, pending, and out-of-period advances are intentionally omitted.
  useEffect(() => {
    getAdvances().then(all => {
      const byEmp = {};
      for (const entry of payroll.entries.map(normaliseEntry)) {
        const due = all.filter(advance =>
          advance.employeeId === entry.employeeId &&
          getAdvanceInstallmentForPeriod(advance, payroll.period) > 0
        );
        if (due.length) byEmp[entry.employeeId] = due;
      }
      setAdvanceData(byEmp);
    }).catch(() => setAdvanceData({})).finally(() => setAdvancesLoaded(true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payroll.period]);

  // Load approved+unpaid expenses — shown as informational panel; marked paid on submit (Feature 14)
  useEffect(() => {
    getApprovedUnpaidExpenses().then(all => {
      const byEmp = {};
      for (const exp of all) {
        if (!byEmp[exp.employeeId]) byEmp[exp.employeeId] = [];
        byEmp[exp.employeeId].push(exp);
      }
      setExpenseData(byEmp);
    }).catch(() => {}); // expense_claims table may not exist yet — fail silently
  }, []);

  // Load roster-derived overtime for this payroll period (Feature 5.2)
  useEffect(() => {
    const [y, m] = payroll.period.split('-').map(Number);
    getOvertimeFromRoster(y, m).then(setRosterOvertime).catch(() => {});
  }, [payroll.period]);

  // Load attendance data for this payroll period (Connection C)
  // Art. 56: Payroll must not run against unclosed attendance period
  useEffect(() => {
    getAttendancePayrollData(payroll.period).then(data => {
      setAttendanceData(data);
      setAttendanceWarning(!data.periodClosed);
    }).catch(() => {}); // attendance module may not be set up yet — fail silently
  }, [payroll.period]);

  const payrollPayload = useCallback((updatedEntries, updatedMeta, overrides = {}) => ({
    ...payroll,
    ...updatedMeta,
    ...overrides,
    sequenceNo: updatedMeta.sequenceNo,
    entries: updatedEntries.map(withCalculatedPayrollFields),
  }), [payroll]);

  const saveNow = useCallback(async (updatedEntries, updatedMeta, overrides = {}) => {
    const payload = payrollPayload(updatedEntries, updatedMeta, overrides);
    setSaveStatus('saving');
    setSaveError('');
    try {
      await onSave(payload);
      setSaveStatus('saved');
      return payload;
    } catch (err) {
      console.error('Payroll save failed:', err);
      setSaveStatus('failed');
      setSaveError(err.message || 'Could not save payroll changes.');
      throw err;
    }
  }, [onSave, payrollPayload]);

  // Auto-save helper — debounced 800ms after last change
  const triggerAutoSave = useCallback((updatedEntries, updatedMeta) => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    setSaveStatus('unsaved');
    setSaveError('');
    autoSaveTimer.current = setTimeout(async () => {
      try {
        await saveNow(updatedEntries, updatedMeta);
      } catch { /* visible failed state is rendered in the header */ }
    }, 800);
  }, [saveNow]);

  useEffect(() => () => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
  }, []);

  // Reconcile the system-generated advance deduction after advance data loads.
  // This removes stale deductions immediately when an advance is settled or when
  // the opened payroll is not one of its scheduled months.
  useEffect(() => {
    if (!advancesLoaded || editingLocked) return;
    const next = entries.map(entry => {
      const remaining = (entry.deductions || []).filter(item => item.label !== 'Advance Repayment');
      const staging = stageAdvancesForPayroll(advanceData[entry.employeeId] || [], payroll.period, entry);
      const staged = staging.staged;
      const total = staging.total;
      return {
        ...entry,
        deductions: total > 0 ? [...remaining, {
          label: 'Advance Repayment',
          amount: total,
          source: 'automatic',
          recurrence: 'one_time',
          payrollPeriod: payroll.period,
          advanceRepayments: staged.map(item => ({ id: item.advance.id, amount: item.amount })),
        }] : remaining,
      };
    });
    if (JSON.stringify(next) === JSON.stringify(entries)) return;
    setEntries(next);
    saveNow(next, meta).catch(() => { /* visible failed state is rendered in the header */ });
  // Reconcile only when the fetched monthly staging changes; entry edits should
  // not repeatedly recreate a deduction the user explicitly undid.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [advancesLoaded, advanceData, editingLocked, leaveDeductions]);

  const [year, month] = payroll.period.split('-').map(Number);
  const daysInMonth = getDaysInMonth(year, month);

  const updateEntry = (idx, field, value) => {
    setEntries(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      triggerAutoSave(next, meta);
      return next;
    });
  };

  const getEmp = (id) => employees.find(e => e.id === id);
  const activeEntries = entries.filter(e => !e.excluded);

  // PAY-10: per-employee doc expiry warnings (within 90 days or already expired)
  const empExpiryWarnings = useMemo(() => {
    const warnings = {};
    for (const emp of employees) {
      const w = [];
      const check = (label, dateStr) => {
        if (!dateStr) return;
        const d = daysUntil(dateStr);
        if (d < 0)   w.push(`${label}: EXPIRED`);
        else if (d <= 90) w.push(`${label}: expires ${formatDateUAE(dateStr)}`);
      };
      check('Visa', emp.visaExpiry);
      check('Emirates ID', emp.emiratesIdExpiry);
      check('Passport', emp.passportExpiry);
      check('Labour Card', emp.labourCardExpiry);
      if (emp.licenceAuthority && emp.licenceAuthority !== 'None') check('Licence', emp.licenceExpiry);
      if (w.length) warnings[emp.id] = w;
    }
    return warnings;
  }, [employees]);

  // PAY-7: compute changed fields vs employee profile defaults
  const changeRows = useMemo(() => entries.flatMap(entry => {
    const emp = getEmp(entry.employeeId);
    if (!emp) return [];
    const rows = [];
    const fmtN = v => parseFloat(v) || 0;
    const diff = (label, entryVal, defaultVal) => {
      if (Math.abs(fmtN(entryVal) - fmtN(defaultVal)) > 0.001)
        rows.push({ emp, label, def: fmtN(defaultVal), run: fmtN(entryVal) });
    };
    diff('Basic Salary',        entry.basicSalary,        emp.basicSalary);
    diff('Housing Allowance',   entry.housingAllowance ?? emp.housingAllowance, emp.housingAllowance);
    diff('Transport Allowance', entry.transportAllowance ?? emp.transportAllowance, emp.transportAllowance);
    diff('Other Allowance',     entry.allowance,          emp.allowance ?? 0);
    if (fmtN(entry.increment) !== 0)     rows.push({ emp, label: 'Increment',      def: 0, run:  fmtN(entry.increment) });
    if (fmtN(entry.bonus) !== 0)         rows.push({ emp, label: 'Bonus',          def: 0, run:  fmtN(entry.bonus) });
    if (fmtN(entry.otherPay) !== 0)      rows.push({ emp, label: 'Other Pay',      def: 0, run:  fmtN(entry.otherPay) });
    if (fmtN(entry.leaveDeduction) !== 0) rows.push({ emp, label: 'Leave Deduction', def: 0, run: -fmtN(entry.leaveDeduction) });
    (entry.additionalAllowances || []).forEach(a => {
      if (parseFloat(a.amount)) rows.push({ emp, label: `+ ${a.label || 'Extra Allowance'}`, def: 0, run: parseFloat(a.amount) });
    });
    (entry.deductions || []).forEach(d => {
      if (parseFloat(d.amount)) rows.push({ emp, label: `- ${d.label || 'Deduction'}`, def: 0, run: -parseFloat(d.amount) });
    });
    if (entry.excluded) rows.push({ emp, label: 'Excluded from run', def: '—', run: 'Yes' });
    return rows;
  }), [entries, employees]); // eslint-disable-line react-hooks/exhaustive-deps

  const payrollTotals   = calculatePayrollTotals(activeEntries);
  const totalBasic      = payrollTotals.basicSalary;
  const totalAllowance  = activeEntries.reduce((s, e) => s + (parseFloat(e.allowance) || 0), 0);
  const totalIncrement  = activeEntries.reduce((s, e) => s + (parseFloat(e.increment) || 0), 0);
  const totalBonus      = activeEntries.reduce((s, e) => s + (parseFloat(e.bonus) || 0), 0);
  const totalOtherPay   = activeEntries.reduce((s, e) => s + (parseFloat(e.otherPay) || 0), 0);
  const totalAddAllow   = activeEntries.reduce((s, e) => s + (e.additionalAllowances || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const totalDeductions = activeEntries.reduce((s, e) => s + (e.deductions || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const grandTotal      = payrollTotals.netPay;

  const buildPayroll = () => ({
    ...payroll,
    ...meta,
    sequenceNo: parseInt(meta.sequenceNo),
    entries: entries.map(withCalculatedPayrollFields),
  });

  const validation = useMemo(() => validatePayrollRun({
    entries,
    employees,
    company,
    meta,
    period: payroll.period,
    attendanceClosed: attendanceData ? attendanceData.periodClosed : null,
  }), [entries, employees, company, meta, payroll.period, attendanceData]);
  const sifDocumentWarnings = validation.warnings.filter(current => [
    'visa_expired',
    'emirates_id_expired',
    'labour_card_expired',
    'passport_expired',
    'professional_licence_expired',
  ].includes(current.code));

  const changedEmployeeIds = useMemo(() => new Set(changeRows.map(row => row.emp.id)), [changeRows]);
  const getEntryStatus = useCallback(entry => {
    if (entry.excluded) return 'excluded';
    if ((validation.byEmployee[entry.employeeId] || []).some(current => current.severity === 'error')) return 'needs_review';
    if (changedEmployeeIds.has(entry.employeeId)) return 'changed';
    return 'ready';
  }, [validation.byEmployee, changedEmployeeIds]);

  const filteredEntries = useMemo(() => {
    const query = entrySearch.trim().toLowerCase();
    return entries.filter(entry => {
      const emp = employees.find(employee => employee.id === entry.employeeId);
      const matchesSearch = !query || [emp?.name, emp?.empNo, emp?.molId]
        .some(value => String(value || '').toLowerCase().includes(query));
      const status = getEntryStatus(entry);
      return matchesSearch && (entryFilter === 'all' || status === entryFilter);
    });
  }, [entries, employees, entrySearch, entryFilter, getEntryStatus]);

  const detailEntry = detailEmployeeId ? entries.find(entry => entry.employeeId === detailEmployeeId) : null;
  const detailEmployee = detailEmployeeId ? employees.find(employee => employee.id === detailEmployeeId) : null;
  const detailCalc = detailEntry ? calculatePayrollEntry(detailEntry) : null;

  const openValidationIssue = current => {
    if (current.employeeId) {
      setEntryFilter('all');
      setEntrySearch('');
      setDetailEmployeeId(current.employeeId);
    }
    setShowValidation(false);
  };

  const pendingAutomaticAdjustmentCount = useMemo(() => {
    const employeeIds = new Set();

    for (const [employeeId, advances] of Object.entries(advanceData)) {
      const entry = entries.find(current => current.employeeId === employeeId);
      const applied = (entry?.deductions || []).some(item => item.label === 'Advance Repayment');
      if (entry && !applied && stageAdvancesForPayroll(advances, payroll.period, entry).total > 0) {
        employeeIds.add(employeeId);
      }
    }

    for (const [employeeId, expenses] of Object.entries(expenseData)) {
      const entry = entries.find(current => current.employeeId === employeeId);
      const applied = (entry?.additionalAllowances || []).some(item => item.label === 'Expense Reimbursement');
      const amount = expenses.reduce((sum, expense) => sum + (expense.amount || 0), 0);
      if (entry && !applied && amount > 0) employeeIds.add(employeeId);
    }

    for (const [employeeId, overtime] of Object.entries(rosterOvertime)) {
      const entry = entries.find(current => current.employeeId === employeeId);
      const employee = employees.find(current => current.id === employeeId);
      const applied = (entry?.additionalAllowances || []).some(item => item.label === 'Overtime (Roster)');
      const amount = (overtime?.overtimeHours || 0) * ((parseFloat(employee?.basicSalary) || 0) / 208) * 1.25;
      if (entry && !applied && amount > 0) employeeIds.add(employeeId);
    }

    return employeeIds.size;
  }, [advanceData, expenseData, rosterOvertime, entries, employees, payroll.period]);

  const applyAllAutomaticAdjustments = () => {
    let next = entries;
    for (const [employeeId, advances] of Object.entries(advanceData)) {
      const entry = next.find(current => current.employeeId === employeeId);
      const staging = stageAdvancesForPayroll(advances, payroll.period, entry);
      const amount = staging.total;
      if (amount > 0) next = updateAutoPayrollItem(next, employeeId, 'deductions', 'Advance Repayment', amount, {
        payrollPeriod: payroll.period,
        advanceRepayments: staging.staged.map(item => ({ id: item.advance.id, amount: item.amount })),
      });
    }
    for (const [employeeId, expenses] of Object.entries(expenseData)) {
      const amount = expenses.reduce((sum, expense) => sum + (expense.amount || 0), 0);
      if (amount > 0) next = updateAutoPayrollItem(next, employeeId, 'additionalAllowances', 'Expense Reimbursement', amount);
    }
    for (const [employeeId, overtime] of Object.entries(rosterOvertime)) {
      if (!overtime?.overtimeHours) continue;
      const employee = employees.find(current => current.id === employeeId);
      const hourlyRate = (parseFloat(employee?.basicSalary) || 0) / 208;
      const amount = overtime.overtimeHours * hourlyRate * 1.25;
      if (amount > 0) next = updateAutoPayrollItem(next, employeeId, 'additionalAllowances', 'Overtime (Roster)', amount);
    }
    setEntries(next);
    triggerAutoSave(next, meta);
  };

  const applyPayrollItem = (employeeId, field, label, amount = null, metadata = {}) => {
    const next = updateAutoPayrollItem(entries, employeeId, field, label, amount, metadata);
    setEntries(next);
    saveNow(next, meta).catch(() => { /* visible failed state is rendered in the header */ });
  };

  const doDownload = (p) => {
    const content = generateSIF(company, employees, p);
    const filename = generateSIFFilename(company, p);
    // Use Uint8Array + application/octet-stream so the browser treats this as raw binary.
    // text/plain allows some browsers (e.g. macOS Safari) to re-normalise CRLF → LF,
    // which would put all lines back into a single row when the bank parses the file.
    const bytes = new TextEncoder().encode(content);
    const blob = new Blob([bytes], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
    return { content, filename };
  };

  const handlePreview = () => {
    if (!canGenerate) { setShowValidation(true); return; }
    const p = buildPayroll();
    const content = generateSIF(company, employees, p);
    const filename = generateSIFFilename(company, p);
    setPreview({ content, filename, payroll: p });
  };

  const handleDownload = async () => {
    if (!canGenerate) { setShowValidation(true); return; }

    const p = buildPayroll();
    doDownload(p);
    // Auto-transition wps_status draft → sif_generated on first SIF download (Feature 9)
    if (isLocked && wpsStatus === 'draft') {
      const next = 'sif_generated';
      setWpsStatus(next);
      try {
        await saveWpsTracking(p.id, {
          wpsStatus: next,
          wpsSubmittedAt: wpsSubmittedAt || null,
          wpsConfirmedAt: wpsConfirmedAt || null,
          wpsReferenceNo,
        });
        onSave({ ...p, wpsStatus: next });
      } catch (err) {
        console.error('WPS auto-transition failed:', err);
      }
    }
  };

  const handleDownloadCorrectedSIF = () => {
    const rejectedIds = Object.entries(wpsEntryStatuses)
      .filter(([, v]) => v.status === 'rejected')
      .map(([k]) => k);
    if (!rejectedIds.length) return;
    const correctedEntries = entries.map(entry => ({
      ...entry,
      excluded: entry.excluded || !rejectedIds.includes(entry.employeeId),
    }));
    const correctedValidation = validatePayrollRun({
      entries: correctedEntries,
      employees,
      company,
      meta,
      period: payroll.period,
      attendanceClosed: true,
    });
    if (!correctedValidation.ready) { setShowValidation(true); return; }
    const p = buildPayroll();
    const content  = generateCorrectedSIF(company, employees, p, rejectedIds);
    const filename = 'CORRECTED_' + generateSIFFilename(company, p);
    const bytes = new TextEncoder().encode(content);
    const blob  = new Blob([bytes], { type: 'application/octet-stream' });
    const url   = URL.createObjectURL(blob);
    const a     = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const handleWpsSave = async () => {
    setWpsSaving(true);
    try {
      await saveWpsTracking(payroll.id, {
        wpsStatus,
        wpsSubmittedAt: wpsSubmittedAt || null,
        wpsConfirmedAt: wpsConfirmedAt || null,
        wpsReferenceNo,
      });
      // Also persist entry-level WPS statuses through the full save
      const updatedEntries = entries.map(e => ({
        ...e,
        wpsPaymentStatus:   wpsEntryStatuses[e.employeeId]?.status ?? 'pending',
        wpsRejectionReason: wpsEntryStatuses[e.employeeId]?.reason ?? '',
      }));
      onSave({
        ...buildPayroll(),
        entries: updatedEntries,
        wpsStatus,
        wpsSubmittedAt: wpsSubmittedAt || null,
        wpsConfirmedAt: wpsConfirmedAt || null,
        wpsReferenceNo,
      });
      setWpsSaveOk(true);
      setTimeout(() => setWpsSaveOk(false), 3000);
    } catch (err) {
      console.error('WPS save failed:', err);
    } finally {
      setWpsSaving(false);
    }
  };

  const handleSubmitPayroll = async () => {
    setSubmitting(true);
    try {
      // Refresh advance state immediately before finalisation so an advance
      // settled/cancelled after this editor opened cannot remain deducted.
      const latestAdvances = await getAdvances();
      const current = buildPayroll();
      const refreshedEntries = current.entries.map(entry => {
        const employeeAdvances = latestAdvances.filter(advance => advance.employeeId === entry.employeeId);
        const staging = stageAdvancesForPayroll(employeeAdvances, current.period, entry);
        const remaining = (entry.deductions || []).filter(item => item.label !== 'Advance Repayment');
        return withCalculatedPayrollFields({
          ...entry,
          deductions: staging.total > 0 ? [...remaining, {
            label: 'Advance Repayment',
            amount: staging.total,
            source: 'automatic',
            recurrence: 'one_time',
            payrollPeriod: current.period,
            advanceRepayments: staging.staged.map(item => ({ id: item.advance.id, amount: item.amount })),
          }] : remaining,
        });
      });
      const p = { ...current, entries: refreshedEntries };
      const finalised = { ...p, status: 'generated' };
      await onSave(finalised);

      // Record only the advance installments embedded in this payroll. The RPC
      // is idempotent per advance+payroll and updates outstanding/settled state.
      const advanceRepayments = finalised.entries
        .filter(entry => !entry.excluded)
        .flatMap(entry => (entry.deductions || [])
          .filter(item => item.label === 'Advance Repayment')
          .flatMap(item => item.advanceRepayments || []));
      for (const repayment of advanceRepayments) {
        await saveAdvanceRepayment({
          advanceId: repayment.id,
          payrollRunId: finalised.id,
          amount: repayment.amount,
          paidDate: finalised.paymentDate,
        });
      }

      await createPayslipRecords(finalised);

      // Notify employees with linked portal accounts that their payslip is ready
      const payslipNotifs = (finalised.entries || [])
        .filter(e => !e.excluded)
        .map(e => {
          const emp = employees.find(em => em.id === e.employeeId);
          if (!emp?.authUserId) return null;
          const net = calculatePayrollEntry(e).netPay;
          return {
            recipientUserId:   emp.authUserId,
            type:              'payslip_available',
            title:             'Payslip available',
            body:              `Your payslip for ${finalised.period} is ready. Net pay: AED ${net.toLocaleString('en-AE', { minimumFractionDigits: 2 })}.`,
            relatedEntityType: 'payroll_run',
            relatedEntityId:   `${finalised.id}_${e.employeeId}`,
          };
        })
        .filter(Boolean);
      if (payslipNotifs.length > 0) {
        createNotifications(payslipNotifs).catch(() => {});
      }

      // Mark approved expenses as paid and link to this payroll run (Feature 14)
      const reimbursedEmployeeIds = new Set(finalised.entries
        .filter(entry => !entry.excluded && (entry.additionalAllowances || []).some(item => item.label === 'Expense Reimbursement'))
        .map(entry => entry.employeeId));
      const allExpenseIds = Object.entries(expenseData)
        .filter(([employeeId]) => reimbursedEmployeeIds.has(employeeId))
        .flatMap(([, expenses]) => expenses.map(expense => expense.id));
      if (allExpenseIds.length > 0) {
        markExpensesPaid(allExpenseIds, finalised.id).catch(() => {});
      }
    } catch (err) {
      console.error('Payroll finalisation failed:', err);
      alert('Payroll could not be finalised: ' + (err.message || 'Unknown error'));
    } finally {
      setSubmitting(false);
      setConfirmSubmit(false);
    }
  };

  const handleMetaChange = (field, value) => {
    setMeta(prev => {
      const next = { ...prev, [field]: value };
      triggerAutoSave(entries, next);
      return next;
    });
  };

  const handleSaveDraft = async () => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    try {
      await saveNow(entries, meta, { status: payroll.status === 'generated' ? 'generated' : 'draft' });
    } catch { /* visible failed state is rendered in the header */ }
  };

  // ── Payroll Approval handlers (Feature 17) ──────────────────────────────────
  const flashApproval = (type, text) => {
    setApprovalMsg({ type, text });
    setTimeout(() => setApprovalMsg(null), 5000);
  };

  const handleSubmitForApproval = async () => {
    if (!validation.ready || saveStatus !== 'saved') {
      setShowValidation(true);
      return;
    }
    setApprovalBusy(true);
    try {
      await submitPayrollForApproval(payroll.id);
      setApprovalStatus('pending_approval');
      setRejectionReason('');
      onSave({ ...buildPayroll(), approvalStatus: 'pending_approval' });
    } catch (err) {
      flashApproval('error', err.message);
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleApprovePayroll = async () => {
    setApprovalBusy(true);
    try {
      await approvePayroll(payroll.id);
      const now = new Date().toISOString();
      setApprovalStatus('approved');
      setApprovedAt(now);
      onSave({ ...buildPayroll(), approvalStatus: 'approved' });
    } catch (err) {
      flashApproval('error', err.message);
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleRejectPayroll = async () => {
    if (!rejectReason.trim()) return;
    setApprovalBusy(true);
    try {
      await rejectPayroll(payroll.id, rejectReason.trim());
      setApprovalStatus('draft');
      setRejectionReason(rejectReason.trim());
      setRejectOpen(false);
      setRejectReason('');
      onSave({ ...buildPayroll(), approvalStatus: 'draft', rejectionReason: rejectReason.trim() });
    } catch (err) {
      flashApproval('error', err.message);
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleRecallApproval = async () => {
    setApprovalBusy(true);
    try {
      await recallPayrollApproval(payroll.id);
      setApprovalStatus('draft');
      setSubmittedBy('');
      onSave({ ...buildPayroll(), approvalStatus: 'draft' });
    } catch (err) {
      flashApproval('error', err.message);
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleCSVImport = async (file) => {
    try {
      const text = await readFileAsText(file);
      const { payrollEntries } = parseCSV(text);
      if (!payrollEntries.length) {
        setImportMsg({ type: 'warning', text: 'No valid rows found in CSV.' });
        return;
      }
      let matched = 0;
      const next = entries.map(entry => {
        const emp = getEmp(entry.employeeId);
        if (!emp) return entry;
        const csvRow = payrollEntries.find(r => r.molId === emp.molId);
        if (csvRow) {
          matched++;
          return {
            ...entry,
            basicSalary: csvRow.basicSalary || entry.basicSalary,
            allowance: csvRow.variableAllowance || entry.allowance || 0,
          };
        }
        return entry;
      });
      setEntries(next);
      triggerAutoSave(next, meta);
      setImportMsg({ type: 'success', text: `Updated ${matched} employee entries from CSV.` });
      setTimeout(() => setImportMsg(null), 5000);
    } catch (err) {
      setImportMsg({ type: 'danger', text: 'Failed to parse CSV: ' + err.message });
    }
  };

  const canGenerate = validation.ready && saveStatus === 'saved';

  const hdrClickable = {
    cursor: 'pointer',
    color: 'var(--primary)',
    textDecoration: 'underline dotted',
    display: 'flex',
    alignItems: 'center',
    gap: 3,
    whiteSpace: 'nowrap',
  };

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost btn-sm" onClick={onBack}>← Back</button>
          <h2>
            Payroll: {getMonthName(month)} {year}
            <span
              className={`badge ${isLocked ? 'badge-green' : 'badge-yellow'}`}
              style={{ marginLeft: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}
            >
              {isLocked ? <><Lock size={11} /> Finalised</> : 'Draft'}
            </span>
          </h2>
        </div>
        <div className="page-header-actions">
          <span className={`payroll-save-state ${saveStatus}`}>
            {saveStatus === 'saving' && <><RefreshCw size={13} className="spin-icon" /> Saving…</>}
            {saveStatus === 'saved' && <><CheckCircle size={13} /> All changes saved</>}
            {saveStatus === 'unsaved' && <><Clock size={13} /> Unsaved changes</>}
            {saveStatus === 'failed' && <><AlertCircle size={13} /> Save failed</>}
          </span>
          {saveStatus === 'failed' && (
            <button className="btn btn-outline btn-sm" onClick={handleSaveDraft} title={saveError}>Retry Save</button>
          )}
          {!editingLocked && (
            <>
              <button className="btn btn-outline btn-sm" onClick={() => fileRef.current.click()}>
                <Upload size={14} /> Import CSV
              </button>
              <button className="btn btn-outline btn-sm" onClick={handleSaveDraft}>Save Draft</button>
            </>
          )}
          {/* Approval action buttons (Feature 17) */}
          {approvalStatus === 'pending_approval' && (
            <button className="btn btn-outline btn-sm" onClick={handleRecallApproval} disabled={approvalBusy}>
              ← Recall
            </button>
          )}
          <input
            ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }}
            onChange={e => { if (e.target.files[0]) handleCSVImport(e.target.files[0]); e.target.value = ''; }}
          />
          <button
            className="btn btn-outline btn-sm"
            title="View per-employee changes from profile defaults"
            onClick={() => setShowChanges(true)}
          >
            <GitCompare size={14} /> View Changes
          </button>
          <button
            className={`btn btn-sm ${validation.ready ? 'btn-outline' : 'btn-danger'}`}
            onClick={() => setShowValidation(true)}
          >
            <ListChecks size={14} /> Validate ({validation.errors.length})
          </button>
          <button
            className="btn btn-outline btn-sm"
            title="Download payslips for all active employees"
            onClick={() => downloadAllPayslips(company, employees, buildPayroll())}
            disabled={!canGenerate}
          >
            <FileText size={14} /> All Payslips
          </button>
          <button className="btn btn-outline btn-sm" onClick={handlePreview}>
            <Eye size={14} /> Preview SIF
          </button>
          <button className="btn btn-success btn-sm" onClick={handleDownload}>
            <Download size={14} /> Download SIF
          </button>
          {isLocked && Object.values(wpsEntryStatuses).some(v => v.status === 'rejected') && (
            <button className="btn btn-outline btn-sm" onClick={handleDownloadCorrectedSIF} title="Download SIF for rejected employees only">
              <RefreshCw size={14} /> Corrected SIF
            </button>
          )}
          {/* Draft: submit for approval (Feature 17) */}
          {!isLocked && approvalStatus === 'draft' && (
            <button className="btn btn-primary btn-sm" onClick={handleSubmitForApproval} disabled={approvalBusy}>
              <Send size={14} /> {approvalBusy ? 'Submitting…' : 'Submit for Approval'}
            </button>
          )}
          {/* Pending approval: approve/reject (Feature 17) */}
          {approvalStatus === 'pending_approval' && (
            <>
              <button className="btn btn-sm" style={{ background:'var(--danger)', color:'#fff', border:'none' }}
                onClick={() => setRejectOpen(true)} disabled={approvalBusy}>
                Reject
              </button>
              <button className="btn btn-sm" style={{ background:'var(--success)', color:'#fff', border:'none' }}
                onClick={handleApprovePayroll} disabled={approvalBusy}>
                {approvalBusy ? 'Approving…' : '✓ Approve'}
              </button>
            </>
          )}
          {/* Approved: generate payroll (Feature 17) */}
          {!isLocked && approvalStatus === 'approved' && (
            <button className="btn btn-primary btn-sm" onClick={() => canGenerate ? setConfirmSubmit(true) : setShowValidation(true)}>
              <Send size={14} /> Generate Payroll
            </button>
          )}
        </div>
      </div>

      <div className="page-body">
        {isLocked && (
          <div className="alert alert-success mb-4">
            <Lock size={16} />
            <div>
              <strong>Payroll finalised — locked.</strong> This run has been submitted and payslips have been distributed to employees.
              Download the SIF file or individual payslips using the buttons above.
            </div>
          </div>
        )}

        {/* ── Approval status banners (Feature 17) ── */}
        {approvalMsg && (
          <div className={`alert alert-${approvalMsg.type === 'error' ? 'danger' : 'success'} mb-4`}>
            <AlertCircle size={14} /> {approvalMsg.text}
          </div>
        )}

        {sifDocumentWarnings.length > 0 && (
          <div className="alert alert-warning mb-4" style={{ alignItems: 'center' }}>
            <AlertCircle size={18} />
            <div style={{ flex: 1 }}>
              <strong>Compliance reminder — {sifDocumentWarnings.length} expired document{sifDocumentWarnings.length !== 1 ? 's' : ''}.</strong>
              <div style={{ fontSize: 12, marginTop: 3 }}>
                {new Set(sifDocumentWarnings.map(current => current.employeeId)).size} employee{new Set(sifDocumentWarnings.map(current => current.employeeId)).size !== 1 ? 's are' : ' is'} affected. You may continue, but review and update these records promptly.
              </div>
            </div>
            <button className="btn btn-outline btn-sm" onClick={() => setShowValidation(true)}>
              Review reminders
            </button>
          </div>
        )}

        {/* Rejection notice — draft payroll that was previously rejected */}
        {!isLocked && approvalStatus === 'draft' && rejectionReason && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={16} />
            <div>
              <strong>Returned for correction.</strong> Reason: {rejectionReason}
            </div>
          </div>
        )}

        {/* Pending approval notice */}
        {approvalStatus === 'pending_approval' && (
          <div className="alert alert-info mb-4" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
              <Info size={16} /> PENDING APPROVAL
              {submittedBy && <span style={{ fontWeight: 400, fontSize: 13 }}>— submitted by {submittedBy}</span>}
            </div>
            <div style={{ fontSize: 13 }}>
              Payroll is locked. Review all entries carefully, then use <strong>Approve</strong> or <strong>Reject</strong> above.
              Use <strong>Recall</strong> to unlock for further editing.
            </div>
            {/* Reject reason form */}
            {rejectOpen && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', width: '100%', marginTop: 4 }}>
                <input
                  className="form-control"
                  style={{ flex: 1 }}
                  placeholder="Rejection reason (required)…"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  autoFocus
                />
                <button
                  className="btn btn-sm"
                  style={{ background: 'var(--danger)', color: '#fff', border: 'none', whiteSpace: 'nowrap' }}
                  onClick={handleRejectPayroll}
                  disabled={!rejectReason.trim() || approvalBusy}
                >
                  Confirm Reject
                </button>
                <button className="btn btn-sm btn-outline" onClick={() => setRejectOpen(false)} disabled={approvalBusy}>
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {/* Approved notice */}
        {!isLocked && approvalStatus === 'approved' && (
          <div className="alert alert-success mb-4">
            <CheckCircle size={16} />
            <div>
              <strong>Approved{approvedBy ? ` by ${approvedBy}` : ''}.</strong>{' '}
              Payroll is ready. Click <strong>Generate Payroll</strong> above to create payslips and lock this run.
            </div>
          </div>
        )}

        {/* ── WPS Payment Tracking (Feature 9) — visible only on locked payrolls ── */}
        {isLocked && (
          <div className="card mb-4">
            <div className="card-header">
              <h3>
                <ShieldCheck size={15} style={{ marginRight: 6, color: 'var(--primary)' }} />
                WPS Payment Tracking
              </h3>
              <span className={`badge ${WPS_STATUS_BADGES[wpsStatus] ?? 'badge-yellow'}`}>
                {WPS_STATUS_LABELS[wpsStatus] ?? wpsStatus}
              </span>
            </div>
            <div className="card-body">
              <div className="form-grid form-grid-3">
                <div className="form-group">
                  <label>WPS Status</label>
                  <select className="form-control" value={wpsStatus} onChange={e => setWpsStatus(e.target.value)}>
                    <option value="draft">Not Submitted</option>
                    <option value="sif_generated">SIF Generated</option>
                    <option value="submitted">Submitted to Bank</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="partial_rejection">Partial Rejection</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Bank Reference No.</label>
                  <input
                    className="form-control font-mono"
                    placeholder="e.g. WPS-2026-04-001"
                    value={wpsReferenceNo}
                    onChange={e => setWpsReferenceNo(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Submitted to Bank On</label>
                  <input
                    className="form-control"
                    type="date"
                    value={wpsSubmittedAt}
                    onChange={e => setWpsSubmittedAt(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Bank Confirmation Date</label>
                  <input
                    className="form-control"
                    type="date"
                    value={wpsConfirmedAt}
                    onChange={e => setWpsConfirmedAt(e.target.value)}
                  />
                </div>
              </div>

              {/* Per-employee WPS payment status */}
              {activeEntries.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--gray-600)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Per-Employee Payment Status
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <div style={{ position: 'relative' }}>
                        <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)', pointerEvents: 'none' }} />
                        <input
                          className="form-control"
                          style={{ paddingLeft: 28, fontSize: 12, height: 32, width: 180 }}
                          placeholder="Filter employees…"
                          value={wpsSearch}
                          onChange={e => setWpsSearch(e.target.value)}
                        />
                      </div>
                      <button
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: 12, whiteSpace: 'nowrap' }}
                        onClick={() => setWpsEntryStatuses(prev => {
                          const next = { ...prev };
                          for (const entry of activeEntries) {
                            next[entry.employeeId] = { ...((prev[entry.employeeId]) || {}), status: 'paid' };
                          }
                          return next;
                        })}
                      >
                        ✓ Mark All Paid
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {activeEntries.filter(entry => {
                      const emp = getEmp(entry.employeeId);
                      return emp && (!wpsSearch || emp.name.toLowerCase().includes(wpsSearch.toLowerCase()));
                    }).map(entry => {
                      const emp     = getEmp(entry.employeeId);
                      if (!emp) return null;
                      const empWps  = wpsEntryStatuses[entry.employeeId] ?? { status: 'pending', reason: '' };
                      return (
                        <div key={entry.employeeId} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 10px', background: 'var(--gray-50)', borderRadius: 8 }}>
                          <div style={{ minWidth: 160, fontSize: 13, fontWeight: 500, color: 'var(--gray-800)' }}>{emp.name}</div>
                          <select
                            className="form-control"
                            style={{ width: 160, fontSize: 12, padding: '4px 8px' }}
                            value={empWps.status}
                            onChange={e => setWpsEntryStatuses(prev => ({
                              ...prev,
                              [entry.employeeId]: { ...prev[entry.employeeId], status: e.target.value },
                            }))}
                          >
                            <option value="pending">Pending</option>
                            <option value="paid">Paid</option>
                            <option value="rejected">Rejected</option>
                          </select>
                          {empWps.status === 'rejected' && (
                            <input
                              className="form-control"
                              style={{ flex: 1, fontSize: 12, padding: '4px 8px' }}
                              placeholder="Rejection reason (e.g. Invalid IBAN)"
                              value={empWps.reason}
                              onChange={e => setWpsEntryStatuses(prev => ({
                                ...prev,
                                [entry.employeeId]: { ...prev[entry.employeeId], reason: e.target.value },
                              }))}
                            />
                          )}
                          <span className={`badge ${WPS_ENTRY_BADGES[empWps.status] ?? 'badge-yellow'}`} style={{ fontSize: 11, minWidth: 64, textAlign: 'center' }}>
                            {WPS_ENTRY_LABELS[empWps.status] ?? empWps.status}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 16 }}>
                <button className="btn btn-primary btn-sm" onClick={handleWpsSave} disabled={wpsSaving}>
                  <ShieldCheck size={13} /> {wpsSaving ? 'Saving…' : 'Save WPS Status'}
                </button>
                {wpsSaveOk && (
                  <span style={{ fontSize: 13, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CheckCircle size={14} /> Saved
                  </span>
                )}
                {Object.values(wpsEntryStatuses).some(v => v.status === 'rejected') && (
                  <button className="btn btn-outline btn-sm" onClick={handleDownloadCorrectedSIF} style={{ marginLeft: 'auto' }}>
                    <RefreshCw size={13} /> Download Corrected SIF ({Object.values(wpsEntryStatuses).filter(v => v.status === 'rejected').length} rejected)
                  </button>
                )}
              </div>

              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--gray-500)' }}>
                <Info size={11} style={{ marginRight: 4 }} />
                WPS status updates are saved independently of payroll entries. The Corrected SIF contains only rejected employees and should be re-submitted after fixing the issue.
              </div>
            </div>
          </div>
        )}
        {importMsg && (
          <div className={`alert alert-${importMsg.type} mb-4`}>
            <AlertCircle size={16} /> {importMsg.text}
          </div>
        )}
        {!company?.molEmployerId && (
          <div className="alert alert-danger mb-4">
            <AlertCircle size={16} />
            Company MOL Employer ID is not set. Please configure it in <strong>Company Settings</strong> first.
          </div>
        )}

        {/* ── Payroll Meta ── */}
        <div className="card mb-4">
          <div className="card-header"><h3>Payroll Run Details</h3></div>
          <div className="card-body">
            <div className="form-grid form-grid-3">
              <div className="form-group">
                <label>Payment Date</label>
                <input className="form-control" type="date" value={meta.paymentDate} disabled={editingLocked}
                  onChange={e => handleMetaChange('paymentDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label>File Creation Time (HHMM)</label>
                <input className="form-control font-mono" maxLength={4} value={meta.sequenceNo}
                  placeholder="e.g. 1430" disabled={editingLocked}
                  onChange={e => handleMetaChange('sequenceNo', e.target.value.replace(/\D/g, '').slice(0, 4))} />
                <span className="hint">4-digit time in HHMM format — used in SCR line &amp; filename</span>
              </div>
              <div className="form-group">
                <label>SCR Bank Routing Code</label>
                <input className="form-control font-mono" value={meta.scrBankRoutingCode} disabled={editingLocked}
                  onChange={e => handleMetaChange('scrBankRoutingCode', e.target.value.trim())} />
                {(() => {
                  // Warning-only: some historical payroll runs used non-9-digit
                  // codes, so we do not block SIF generation on format. Show a
                  // hint when the current value looks wrong.
                  if (!meta.scrBankRoutingCode) return null;
                  const check = validateBankRoutingCode(meta.scrBankRoutingCode);
                  if (check.valid) return null;
                  return (
                    <span className="hint" style={{ color: 'var(--warning)' }}>
                      {check.message} — banks may reject the SIF.
                    </span>
                  );
                })()}
              </div>
              <div className="form-group" style={{ gridColumn: '1/-1' }}>
                <label>Description</label>
                <input className="form-control" value={meta.description} disabled={editingLocked}
                  onChange={e => handleMetaChange('description', e.target.value)} />
              </div>
            </div>
          </div>
        </div>

        {/* ── Stats ── */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Employees</div>
            <div className="stat-value">{activeEntries.length}</div>
            <div className="stat-sub">{entries.length - activeEntries.length} excluded</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Gross Earnings</div>
            <div className="stat-value">{payrollTotals.grossEarnings.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Deductions</div>
            <div className="stat-value" style={{ color: 'var(--danger)' }}>{payrollTotals.totalDeductions.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Net Payroll</div>
            <div className="stat-value" style={{ color: 'var(--primary)' }}>
              {grandTotal.toLocaleString('en-AE')}
            </div>
            <div className="stat-sub">AED — {daysInMonth} days</div>
          </div>
        </div>

        {/* ── Attendance Warning (Art. 56 — period must be closed before payroll) ── */}
        {attendanceWarning && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={16}/>
            <div>
              <strong>Art. 56 — Attendance Not Finalised:</strong> The attendance period for {payroll.period} has not been closed yet.
              UAE Labour Law requires payroll to be based on finalised attendance data.
              Please close the attendance period in the <strong>Attendance</strong> module before running payroll.
            </div>
          </div>
        )}

        {pendingAutomaticAdjustmentCount > 0 && !editingLocked && (
          <div className="payroll-auto-review card mb-4">
            <div>
              <span className="payroll-auto-review-icon"><RefreshCw size={17} /></span>
              <div>
                <h3>{pendingAutomaticAdjustmentCount} employee{pendingAutomaticAdjustmentCount !== 1 ? 's have' : ' has'} unapplied automatic payroll adjustments</h3>
                <p>Review and apply current advance repayments, approved expenses, and roster overtime. Existing matching items are updated, never duplicated.</p>
              </div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={applyAllAutomaticAdjustments}>
              <CheckCircle size={14} /> Apply all adjustments
            </button>
          </div>
        )}

        {/* ── Attendance Line Items Panel (Connection C) ── */}
        {attendanceData && Object.keys(attendanceData.byEmployee || {}).length > 0 && (
          <div className="card mb-4">
            <div className="card-header">
              <h3><Info size={15} style={{ marginRight:6, color:'var(--primary)' }}/>Attendance-Derived Payroll Items</h3>
              <span className={`badge ${attendanceData.periodClosed ? 'badge-green' : 'badge-amber'}`}>
                {attendanceData.periodClosed ? '✓ Period Closed' : 'Period Open'}
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Employee</th><th>Item</th><th>Type</th><th className="text-right">Amount (AED)</th></tr>
                </thead>
                <tbody>
                  {Object.entries(attendanceData.byEmployee).map(([empId, empRecords]) => {
                    const emp = employees.find(e => e.id === empId);
                    const summary = getPayrollSummaryFromAttendance(empRecords, emp?.basicSalary || 0);
                    return summary.lineItems.map((item, i) => (
                      <tr key={`${empId}-${i}`}>
                        <td style={{ fontWeight: i === 0 ? 500 : 400, color: i === 0 ? 'var(--gray-800)' : 'var(--gray-400)' }}>
                          {i === 0 ? emp?.name : ''}
                        </td>
                        <td className="text-sm">{item.label}</td>
                        <td>
                          <span className={`badge ${item.type === 'deduction' ? 'badge-red' : 'badge-green'}`}>
                            {item.type === 'deduction' ? 'Deduction' : 'Earning'}
                          </span>
                        </td>
                        <td className="text-right" style={{ color: item.type === 'deduction' ? 'var(--danger)' : 'var(--success)', fontWeight:600 }}>
                          {item.type === 'deduction' ? '-' : '+'}{item.amount.toLocaleString('en-AE', { minimumFractionDigits:2 })}
                        </td>
                      </tr>
                    ));
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/>
              Absence deductions (Art. 56), overtime earnings (Art. 19), and late deductions are pulled from the Attendance module.
              Apply them as named deductions/additions via the Allowances &amp; Deductions panel below.
            </div>
          </div>
        )}

        {/* ── Salary Advance Repayments Panel ── */}
        {Object.keys(advanceData).length > 0 && (() => {
          // Idempotent apply: adds an "Advance Repayment" deduction line to the
          // employee entry. If a line with that label already exists it is
          // replaced (so re-clicking after a value change stays consistent).
          const advanceLabel = 'Advance Repayment';
          return (
          <div className="card mb-4">
            <div className="card-header">
              <h3><Info size={15} style={{ marginRight:6, color:'var(--primary)' }}/>Active Salary Advance Repayments</h3>
              <span className="badge badge-blue">
                {Object.keys(advanceData).length} employee{Object.keys(advanceData).length !== 1 ? 's' : ''} with active advances
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Advance Reason</th>
                    <th className="text-right">Original Amount</th>
                    <th className="text-right">Outstanding Balance</th>
                    <th className="text-right">Monthly Deduction</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(advanceData).map(([empId, advs]) => {
                    const emp = employees.find(e => e.id === empId);
                    const entry = entries.find(e => e.employeeId === empId);
                    const staging = stageAdvancesForPayroll(advs, payroll.period, entry);
                    const stagedById = new Map(staging.staged.map(item => [item.advance.id, item]));
                    const totalDeduction = staging.total;
                    return advs.map((adv, i) => {
                      const stagedItem = stagedById.get(adv.id);
                      const applied = (entry?.deductions || []).some(d => d.label === advanceLabel);
                      return (
                        <tr key={adv.id}>
                          <td style={{ fontWeight: i === 0 ? 500 : 400, color: i === 0 ? 'var(--gray-800)' : 'var(--gray-400)' }}>
                            {i === 0 ? emp?.name : ''}
                          </td>
                          <td className="text-sm">{adv.reason}</td>
                          <td className="text-right text-sm">
                            {adv.amount.toLocaleString('en-AE', { minimumFractionDigits:2 })}
                          </td>
                          <td className="text-right" style={{ color:'var(--primary)', fontWeight:600 }}>
                            {adv.outstandingBalance.toLocaleString('en-AE', { minimumFractionDigits:2 })}
                          </td>
                          <td className="text-right" style={{ color:'var(--danger)', fontWeight:600 }}>
                            -{(stagedItem?.amount || 0).toLocaleString('en-AE', { minimumFractionDigits:2 })}
                            {stagedItem?.cappedForWps && <div style={{ fontSize: 9, color: 'var(--warning)' }}>WPS capped</div>}
                          </td>
                          <td>
                            {i === 0 && (
                              applied ? (
                                <div className="payroll-applied-action">
                                  <span className="payroll-applied-label"><CheckCircle size={13} /> Applied</span>
                                  <button type="button" className="payroll-undo-btn" onClick={() => applyPayrollItem(empId, 'deductions', advanceLabel)} disabled={editingLocked}>
                                    <Undo2 size={12} /> Undo
                                  </button>
                                </div>
                              ) : (
                                <button type="button" className="btn btn-primary btn-sm payroll-apply-btn" onClick={() => applyPayrollItem(empId, 'deductions', advanceLabel, totalDeduction, {
                                  payrollPeriod: payroll.period,
                                  advanceRepayments: staging.staged.map(item => ({ id: item.advance.id, amount: item.amount })),
                                })} disabled={editingLocked}>
                                  <Plus size={13} strokeWidth={2.5} /> Apply to Payroll
                                </button>
                              )
                            )}
                          </td>
                        </tr>
                      );
                    });
                  })}
                </tbody>
                <tfoot>
                  <tr style={{ background:'var(--danger-light)', fontWeight:700 }}>
                    <td colSpan={4} style={{ textAlign:'right', paddingRight:12, color:'var(--danger)' }}>
                      Total Advance Deductions This Month
                    </td>
                    <td className="text-right" style={{ color:'var(--danger)' }}>
                      -{Object.entries(advanceData)
                          .reduce((sum, [employeeId, advances]) => {
                            const entry = entries.find(current => current.employeeId === employeeId);
                            return sum + stageAdvancesForPayroll(advances, payroll.period, entry).total;
                          }, 0)
                          .toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/>
              Click <strong>Apply to Payroll</strong> to add the monthly repayment as an "Advance Repayment" deduction on that employee's entry.
              Use <strong>Undo</strong> to remove it if needed.
            </div>
          </div>
          );
        })()}

        {/* ── Roster Overtime Panel (Feature 5.2) ── */}
        {Object.keys(rosterOvertime).length > 0 && (() => {
          const empIds = Object.keys(rosterOvertime).filter(id => rosterOvertime[id].overtimeHours > 0);
          if (!empIds.length) return null;

          const overtimeLabel = 'Overtime (Roster)';
          return (
            <div className="card mb-4">
              <div className="card-header">
                <h3><Info size={15} style={{ marginRight:6, color:'var(--accent)' }}/>Roster Overtime — Auto-Calculated</h3>
                <span className="badge badge-blue">
                  {empIds.length} employee{empIds.length !== 1 ? 's' : ''} with overtime hours
                </span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th className="text-right">Planned Hrs</th>
                      <th className="text-right">Actual Hrs</th>
                      <th className="text-right">OT Hrs</th>
                      <th className="text-right">OT Pay (AED)</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {empIds.map(empId => {
                      const ot    = rosterOvertime[empId];
                      const entry = entries.find(e => e.employeeId === empId);
                      const emp   = employees.find(e => e.id === empId);
                      if (!emp) return null;
                      const hourlyRate  = (parseFloat(emp.basicSalary) || 0) / 208; // 26d × 8h
                      const overtimePay = ot.overtimeHours * hourlyRate * 1.25;      // Art. 19 UAE Labour Law
                      const applied     = (entry?.additionalAllowances || []).some(a => a.label === overtimeLabel);
                      return (
                        <tr key={empId}>
                          <td><strong>{emp.name}</strong></td>
                          <td className="text-right">{ot.plannedHours.toFixed(1)}</td>
                          <td className="text-right">{ot.actualHours.toFixed(1)}</td>
                          <td className="text-right" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                            +{ot.overtimeHours.toFixed(1)}
                          </td>
                          <td className="text-right" style={{ fontWeight: 600 }}>
                            {overtimePay.toFixed(2)}
                          </td>
                          <td>
                            {applied ? (
                              <div className="payroll-applied-action">
                                <span className="payroll-applied-label"><CheckCircle size={13} /> Applied</span>
                                <button type="button" className="payroll-undo-btn" onClick={() => applyPayrollItem(empId, 'additionalAllowances', overtimeLabel)} disabled={editingLocked}>
                                  <Undo2 size={12} /> Undo
                                </button>
                              </div>
                            ) : (
                              <button type="button" className="btn btn-primary btn-sm payroll-apply-btn" onClick={() => applyPayrollItem(empId, 'additionalAllowances', overtimeLabel, overtimePay)} disabled={editingLocked}>
                                <Plus size={13} strokeWidth={2.5} /> Apply to Payroll
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
                <Info size={12} style={{ marginRight:4 }}/>
                Computed from <strong>Roster actual vs planned hours</strong>. Rate: <strong>1.25× hourly</strong> (Art. 19, UAE Labour Law No. 33/2021). Hourly = Basic ÷ 208 (26d × 8h). Click "Apply to Payroll" to add as an allowance line item.
              </div>
            </div>
          );
        })()}

        {/* ── Expense Reimbursements Panel (Feature 14) ── */}
        {Object.keys(expenseData).length > 0 && (() => {
          const expenseLabel = 'Expense Reimbursement';
          return (
          <div className="card mb-4">
            <div className="card-header">
              <h3><Info size={15} style={{ marginRight:6, color:'var(--success)' }}/>Approved Expense Reimbursements</h3>
              <span className="badge badge-green">
                {Object.keys(expenseData).length} employee{Object.keys(expenseData).length !== 1 ? 's' : ''} with pending reimbursements
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Category</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th className="text-right">Amount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(expenseData).map(([empId, exps]) => {
                    const emp = employees.find(e => e.id === empId);
                    const totalAmount = exps.reduce((s, e) => s + (e.amount || 0), 0);
                    return exps.map((exp, i) => {
                      const entry = entries.find(e => e.employeeId === empId);
                      const applied = (entry?.additionalAllowances || []).some(a => a.label === expenseLabel);
                      return (
                        <tr key={exp.id}>
                          <td style={{ fontWeight: i === 0 ? 500 : 400, color: i === 0 ? 'var(--gray-800)' : 'var(--gray-400)' }}>
                            {i === 0 ? emp?.name : ''}
                          </td>
                          <td style={{ textTransform:'capitalize' }}>{exp.category?.replace('_',' ')}</td>
                          <td>{formatDateUAE(exp.expenseDate)}</td>
                          <td style={{ maxWidth:200, overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis' }}>
                            {exp.description}
                          </td>
                          <td className="text-right" style={{ fontWeight:600, color:'var(--success)' }}>
                            +{exp.amount.toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                          </td>
                          <td>
                            {i === 0 && (
                              applied ? (
                                <div className="payroll-applied-action">
                                  <span className="payroll-applied-label"><CheckCircle size={13} /> Applied</span>
                                  <button type="button" className="payroll-undo-btn" onClick={() => applyPayrollItem(empId, 'additionalAllowances', expenseLabel)} disabled={editingLocked}>
                                    <Undo2 size={12} /> Undo
                                  </button>
                                </div>
                              ) : (
                                <button type="button" className="btn btn-primary btn-sm payroll-apply-btn" onClick={() => applyPayrollItem(empId, 'additionalAllowances', expenseLabel, totalAmount)} disabled={editingLocked}>
                                  <Plus size={13} strokeWidth={2.5} /> Apply to Payroll
                                </button>
                              )
                            )}
                          </td>
                        </tr>
                      );
                    });
                  })}
                </tbody>
                <tfoot>
                  <tr style={{ background:'rgba(22,163,74,0.06)', fontWeight:700 }}>
                    <td colSpan={4} style={{ textAlign:'right', paddingRight:12, color:'var(--success)' }}>
                      Total Reimbursements
                    </td>
                    <td className="text-right" style={{ color:'var(--success)' }}>
                      +{Object.values(expenseData)
                          .flat()
                          .reduce((s, e) => s + e.amount, 0)
                          .toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/>
              Click <strong>Apply to Payroll</strong> to add the reimbursement as an "Expense Reimbursement" allowance line.
              Use <strong>Undo</strong> to remove it if needed. These claims are automatically marked <strong>Paid</strong> when payroll is submitted.
            </div>
          </div>
          );
        })()}

        {/* ── Leave Deductions Panel ── */}
        {Object.keys(leaveDeductions).length > 0 && (
          <div className="card mb-4">
            <div className="card-header">
              <h3><Info size={15} style={{ marginRight:6, color:'var(--warning)' }}/>Leave Deductions This Period</h3>
              <span className="badge badge-amber">{Object.keys(leaveDeductions).length} employee{Object.keys(leaveDeductions).length !== 1 ? 's' : ''} affected</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Leave Type</th>
                    <th>Days</th>
                    <th className="text-right">Deduction (AED)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(leaveDeductions).map(([empId, ded]) => {
                    const emp = employees.find(e => e.id === empId);
                    return ded.lineItems.map((item, i) => (
                      <tr key={`${empId}-${i}`}>
                        <td style={{ fontWeight: i === 0 ? 500 : 400, color: i === 0 ? 'var(--gray-800)' : 'var(--gray-400)' }}>
                          {i === 0 ? emp?.name : ''}
                        </td>
                        <td className="text-sm">{item.label}</td>
                        <td>{item.days}</td>
                        <td className="text-right" style={{ color:'var(--danger)', fontWeight:600 }}>
                          -{item.amount.toLocaleString('en-AE', { minimumFractionDigits:2 })}
                        </td>
                      </tr>
                    ));
                  })}
                </tbody>
                <tfoot>
                  <tr style={{ background:'var(--danger-light)', fontWeight:700 }}>
                    <td colSpan={3} style={{ textAlign:'right', paddingRight:12, color:'var(--danger)' }}>
                      Total Leave Deductions
                    </td>
                    <td className="text-right" style={{ color:'var(--danger)' }}>
                      -{Object.values(leaveDeductions).reduce((s, d) => s + d.totalDeduction, 0).toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/> These deductions are calculated from approved leave requests in the Leave module. Apply them manually in the Deductions column below, or add them as named deductions via Allowances &amp; Deductions.
            </div>
          </div>
        )}

        {/* ── Entry Table ── */}
        <div className="card payroll-entries-card">
          <div className="card-header payroll-entries-header">
            <div>
              <h3>Employee Salary Entries</h3>
              <p className="text-sm text-muted" style={{ marginTop: 3 }}>Review exceptions first, then open an employee for a full pay breakdown.</p>
            </div>
            <div className="payroll-entries-toolbar">
              <div className="payroll-entry-search">
                <Search size={13} />
                <input
                  value={entrySearch}
                  onChange={event => setEntrySearch(event.target.value)}
                  placeholder="Search employee…"
                  aria-label="Search payroll employees"
                />
              </div>
              <select className="form-control payroll-status-filter" value={entryFilter} onChange={event => setEntryFilter(event.target.value)}>
                <option value="all">All employees</option>
                <option value="needs_review">Needs review</option>
                <option value="changed">Changed</option>
                <option value="ready">Ready</option>
                <option value="excluded">Excluded</option>
              </select>
              {!isLocked && (
                <button className="btn btn-outline btn-sm" onClick={() => setShowPanel(true)}>
                  <Plus size={13} /> Allowances &amp; Deductions
                </button>
              )}
              <span className="text-sm text-muted">
                Period: {getMonthName(month)} {year} (1–{daysInMonth})
              </span>
            </div>
          </div>

          <div className="table-wrap payroll-table">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 34 }}>✓</th>
                  <th style={{ width: 125 }}>Employee / Status</th>
                  <th style={{ width: 105 }}>MOL ID</th>
                  <th style={{ width: 76 }}>Basic</th>
                  <th style={{ width: 76 }}>Housing</th>
                  <th style={{ width: 76 }}>Transport</th>
                  <th style={{ width: 76 }}>Allowance</th>
                  <th style={{ width: 76 }}>Increment</th>
                  <th style={{ width: 76 }}>Bonus/Incentive</th>
                  <th style={{ width: 76 }}>Other Pay</th>
                  <th style={{ width: 76, color:'var(--danger)' }}>Leave Ded.</th>
                  <th
                    style={{ width: 72 }}
                    title={isLocked ? undefined : 'Click to add named additional allowances per employee'}
                    onClick={() => !isLocked && setShowPanel(true)}
                  >
                    {isLocked
                      ? <span>Add. Allow</span>
                      : <span style={hdrClickable}>Add. Allow <ChevronDown size={11} /></span>}
                  </th>
                  <th
                    style={{ width: 72 }}
                    title={isLocked ? undefined : 'Click to add named deductions per employee'}
                    onClick={() => !isLocked && setShowPanel(true)}
                  >
                    {isLocked
                      ? <span>Deductions</span>
                      : <span style={{ ...hdrClickable, color: 'var(--danger)' }}>Deductions <ChevronDown size={11} /></span>}
                  </th>
                  <th style={{ width: 92, background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>
                    Gross Earnings
                  </th>
                  <th style={{ width: 92 }}>Net Pay</th>
                  <th style={{ width: 48 }}>Payslip</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry) => {
                  const emp = getEmp(entry.employeeId);
                  if (!emp) return null;
                  const idx = entries.findIndex(current => current.employeeId === entry.employeeId);
                  const calc = calculatePayrollEntry(entry);
                  const addAllow = (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
                  const deds = (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);
                  const entryStatus = getEntryStatus(entry);
                  return (
                    <tr key={entry.employeeId} className={entry.excluded ? 'excluded' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={!entry.excluded}
                          disabled={editingLocked}
                          onChange={() => updateEntry(idx, 'excluded', !entry.excluded)}
                        />
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        <button type="button" className="payroll-employee-link" onClick={() => setDetailEmployeeId(emp.id)}>
                          {emp.name}
                        </button>
                        <span className={`payroll-row-status ${entryStatus}`}>{entryStatus.replace('_', ' ')}</span>
                        {empExpiryWarnings[emp.id] && (
                          <span
                            title={empExpiryWarnings[emp.id].join('\n')}
                            style={{ marginLeft: 6, color: 'var(--warning)', fontSize: 14, cursor: 'help', verticalAlign: 'middle' }}
                            aria-label="Document expiry warning"
                          >⚠</span>
                        )}
                      </td>
                      <td className="font-mono text-sm">{emp.molId}</td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.basicSalary} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'basicSalary', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.housingAllowance ?? emp.housingAllowance ?? 0} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'housingAllowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.transportAllowance ?? emp.transportAllowance ?? 0} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'transportAllowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.allowance} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'allowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.increment} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'increment', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.bonus} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'bonus', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.otherPay} disabled={editingLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'otherPay', e.target.value)} />
                      </td>
                      <td style={{ position:'relative' }}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={entry.leaveDeduction ?? 0}
                          disabled={editingLocked || entry.excluded}
                          placeholder="0.00"
                          title="Auto-filled from approved leave. Edit to override."
                          style={{ color: (parseFloat(entry.leaveDeduction) || 0) > 0 ? 'var(--danger)' : undefined }}
                          onChange={e => updateEntry(idx, 'leaveDeduction', parseFloat(e.target.value) || 0)}
                        />
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: addAllow > 0 ? 'var(--success)' : 'var(--gray-400)', cursor: editingLocked ? 'default' : 'pointer' }}
                        onClick={() => !editingLocked && setShowPanel(true)}
                        title={editingLocked ? undefined : 'Click to edit'}
                      >
                        {addAllow > 0 ? `+${addAllow.toLocaleString('en-AE')}` : '—'}
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: deds > 0 ? 'var(--danger)' : 'var(--gray-400)', cursor: editingLocked ? 'default' : 'pointer' }}
                        onClick={() => !editingLocked && setShowPanel(true)}
                        title={editingLocked ? undefined : 'Click to edit'}
                      >
                        {deds > 0 ? `-${deds.toLocaleString('en-AE')}` : '—'}
                      </td>
                      <td
                        className="text-right font-bold"
                        style={{
                          background: 'var(--primary-light)',
                          color: entry.excluded ? 'var(--gray-400)' : 'var(--primary-dark)',
                        }}
                      >
                        {calc.grossEarnings.toLocaleString('en-AE')}
                      </td>
                     <td
                       className="text-right font-bold"
                       style={{ color: entry.excluded ? 'var(--gray-400)' : 'var(--gray-800)' }}
                     >
                        {calc.netPay.toLocaleString('en-AE')}
                     </td>
                     <td>
                       {!entry.excluded && canGenerate && (
                         <button
                           className="btn btn-ghost btn-icon btn-sm"
                           title={`Download payslip for ${emp.name}`}
                           onClick={() => handleDownloadPayslip(company, employees, buildPayroll(), entry)}
                         >
                           <FileText size={13} />
                         </button>
                       )}
                     </td>
                   </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--gray-50)', fontWeight: 700, fontSize: 13 }}>
                  <td colSpan={3} style={{ textAlign: 'right', paddingRight: 12, color: 'var(--gray-600)' }}>TOTALS</td>
                  <td style={{ paddingLeft: 8, textAlign: 'right' }}>{totalBasic.toLocaleString('en-AE')}</td>
                  <td className="text-right" style={{ color: 'var(--gray-600)' }}>
                    {activeEntries.reduce((s,e) => s+(parseFloat(e.housingAllowance??0)||0),0).toLocaleString('en-AE')}
                  </td>
                  <td className="text-right" style={{ color: 'var(--gray-600)' }}>
                    {activeEntries.reduce((s,e) => s+(parseFloat(e.transportAllowance??0)||0),0).toLocaleString('en-AE')}
                  </td>
                  <td className="text-right">{totalAllowance.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalIncrement.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalBonus.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalOtherPay.toLocaleString('en-AE')}</td>
                  <td className="text-right" style={{ color: 'var(--danger)', fontWeight:600 }}>
                    {activeEntries.reduce((s, e) => s + (parseFloat(e.leaveDeduction) || 0), 0) > 0
                      ? `-${activeEntries.reduce((s, e) => s + (parseFloat(e.leaveDeduction) || 0), 0).toLocaleString('en-AE', { minimumFractionDigits:2 })}`
                      : '—'}
                  </td>
                  <td className="text-right" style={{ color: 'var(--success)' }}>
                    {totalAddAllow > 0 ? `+${totalAddAllow.toLocaleString('en-AE')}` : '—'}
                  </td>
                  <td className="text-right" style={{ color: 'var(--danger)' }}>
                    {totalDeductions > 0 ? `-${totalDeductions.toLocaleString('en-AE')}` : '—'}
                  </td>
                  <td className="text-right" style={{ background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>
                    {payrollTotals.grossEarnings.toLocaleString('en-AE')}
                  </td>
                  <td className="text-right" style={{ color: 'var(--primary)' }}>
                    {grandTotal.toLocaleString('en-AE')}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>

      {/* ── Panels / Modals ── */}

      {showValidation && (
        <div className="modal-overlay">
          <div className="modal payroll-validation-modal">
            <div className="modal-header">
              <div>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ListChecks size={17} /> Payroll Validation
                </h3>
                <p className="text-sm text-muted" style={{ marginTop: 3 }}>
                  Resolve blocking errors before submitting payroll for approval.
                </p>
              </div>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowValidation(false)} aria-label="Close validation">
                <X size={17} />
              </button>
            </div>
            <div className="modal-body">
              <div className={`payroll-validation-summary ${validation.ready ? 'ready' : 'blocked'}`}>
                {validation.ready ? <CheckCircle size={22} /> : <AlertCircle size={22} />}
                <div>
                  <strong>{validation.ready ? 'Payroll is ready for approval' : `${validation.errors.length} blocking issue${validation.errors.length !== 1 ? 's' : ''}`}</strong>
                  <p>{activeEntries.length} employees included · {validation.warnings.length} warning{validation.warnings.length !== 1 ? 's' : ''}</p>
                </div>
              </div>

              {saveStatus !== 'saved' && (
                <button type="button" className="payroll-validation-item error" onClick={handleSaveDraft}>
                  <AlertCircle size={15} />
                  <span><strong>Payroll changes are not safely saved.</strong><small>{saveStatus === 'failed' ? saveError : 'Wait for autosave or click to save now.'}</small></span>
                  <span>Save now →</span>
                </button>
              )}

              {validation.errors.map((current, index) => (
                <button
                  type="button"
                  className="payroll-validation-item error"
                  key={`${current.code}-${current.employeeId || 'run'}-${index}`}
                  onClick={() => openValidationIssue(current)}
                >
                  <AlertCircle size={15} />
                  <span>{current.message}</span>
                  {current.employeeId && <span>Review →</span>}
                </button>
              ))}
              {validation.warnings.map((current, index) => (
                <button
                  type="button"
                  className="payroll-validation-item warning"
                  key={`${current.code}-${current.employeeId || 'run'}-${index}`}
                  onClick={() => openValidationIssue(current)}
                >
                  <Info size={15} />
                  <span>{current.message}</span>
                  {current.employeeId && <span>Review →</span>}
                </button>
              ))}
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowValidation(false)}>Close</button>
              {!validation.ready && (
                <button className="btn btn-primary" onClick={() => { setEntryFilter('needs_review'); setShowValidation(false); }}>
                  Review affected employees
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {detailEntry && detailEmployee && detailCalc && (
        <div className="payroll-drawer-backdrop" onClick={() => setDetailEmployeeId(null)}>
          <aside className="payroll-detail-drawer" onClick={event => event.stopPropagation()} aria-label={`${detailEmployee.name} payroll details`}>
            <div className="payroll-drawer-header">
              <div>
                <span className={`payroll-row-status ${getEntryStatus(detailEntry)}`}>{getEntryStatus(detailEntry).replace('_', ' ')}</span>
                <h3>{detailEmployee.name}</h3>
                <p>{detailEmployee.empNo || 'No employee number'} · MOL {detailEmployee.molId || 'missing'}</p>
              </div>
              <button className="btn btn-ghost btn-icon" onClick={() => setDetailEmployeeId(null)} aria-label="Close employee details">
                <X size={18} />
              </button>
            </div>

            <div className="payroll-drawer-body">
              {(validation.byEmployee[detailEmployee.id] || []).length > 0 && (
                <div className="payroll-drawer-issues">
                  {(validation.byEmployee[detailEmployee.id] || []).map((current, index) => (
                    <div key={`${current.code}-${index}`} className={current.severity}>
                      <AlertCircle size={14} /> {current.message}
                    </div>
                  ))}
                </div>
              )}

              <section className="payroll-breakdown-section">
                <h4>Earnings</h4>
                <PayrollBreakdownRow label="Basic salary" amount={detailCalc.basicSalary} source="Employee profile" />
                <PayrollBreakdownRow label="Housing allowance" amount={detailCalc.housingAllowance} source="Employee profile" />
                <PayrollBreakdownRow label="Transport allowance" amount={detailCalc.transportAllowance} source="Employee profile" />
                <PayrollBreakdownRow label="Other fixed allowance" amount={detailCalc.otherFixedAllowance} source="Employee profile" />
                <PayrollBreakdownRow label="Increment" amount={detailCalc.increment} source="This payroll" />
                <PayrollBreakdownRow label="Bonus / incentive" amount={detailCalc.bonus} source="This payroll" />
                <PayrollBreakdownRow label="Other earnings" amount={detailCalc.otherPay} source="This payroll" />
                {(detailEntry.additionalAllowances || []).map((item, index) => (
                  <PayrollBreakdownRow
                    key={`earning-${index}`}
                    label={item.label || 'Additional earning'}
                    amount={parseFloat(item.amount) || 0}
                    source={item.source === 'automatic' ? 'Automatic' : item.recurrence === 'recurring' ? 'Recurring' : 'Manual'}
                  />
                ))}
                <PayrollBreakdownRow label="Gross earnings" amount={detailCalc.grossEarnings} total />
              </section>

              <section className="payroll-breakdown-section deductions">
                <h4>Deductions</h4>
                <PayrollBreakdownRow label="Leave deduction" amount={detailCalc.leaveDeduction} source="Leave module" deduction />
                {(detailEntry.deductions || []).map((item, index) => (
                  <PayrollBreakdownRow
                    key={`deduction-${index}`}
                    label={item.label || 'Deduction'}
                    amount={parseFloat(item.amount) || 0}
                    source={item.source === 'automatic' ? 'Automatic' : item.recurrence === 'recurring' ? 'Recurring' : 'Manual'}
                    deduction
                  />
                ))}
                <PayrollBreakdownRow label="Total deductions" amount={detailCalc.totalDeductions} total deduction />
              </section>

              <div className="payroll-net-result">
                <span>Net Pay</span>
                <strong>AED {detailCalc.netPay.toLocaleString('en-AE', { minimumFractionDigits: 2 })}</strong>
              </div>
            </div>
            <div className="payroll-drawer-footer">
              {!editingLocked && <button className="btn btn-outline" onClick={() => { setDetailEmployeeId(null); setShowPanel(true); }}>Edit adjustments</button>}
              <button className="btn btn-primary" onClick={() => setDetailEmployeeId(null)}>Done</button>
            </div>
          </aside>
        </div>
      )}

      {/* View Changes modal (PAY-7) */}
      {showChanges && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 680 }}>
            <div className="modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitCompare size={16} /> Payroll Changes vs Employee Defaults
              </h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowChanges(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              {changeRows.length === 0 ? (
                <p style={{ color: 'var(--gray-500)', textAlign: 'center', padding: '24px 0' }}>
                  All entries match employee profile defaults — no changes.
                </p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--gray-50)', fontWeight: 600 }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--gray-200)' }}>Employee</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--gray-200)' }}>Field</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid var(--gray-200)' }}>Default</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid var(--gray-200)' }}>This Run</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid var(--gray-200)' }}>Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changeRows.map((r, i) => {
                      const delta = typeof r.run === 'number' && typeof r.def === 'number' ? r.run - r.def : null;
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                          <td style={{ padding: '7px 12px', fontWeight: 500 }}>{r.emp.name}</td>
                          <td style={{ padding: '7px 12px', color: 'var(--gray-600)' }}>{r.label}</td>
                          <td style={{ padding: '7px 12px', textAlign: 'right', color: 'var(--gray-500)' }}>
                            {typeof r.def === 'number' ? r.def.toLocaleString('en-AE') : r.def}
                          </td>
                          <td style={{ padding: '7px 12px', textAlign: 'right', fontWeight: 600 }}>
                            {typeof r.run === 'number' ? r.run.toLocaleString('en-AE') : r.run}
                          </td>
                          <td style={{ padding: '7px 12px', textAlign: 'right', color: delta > 0 ? 'var(--success)' : delta < 0 ? 'var(--danger)' : 'var(--gray-400)' }}>
                            {delta !== null ? (delta >= 0 ? '+' : '') + delta.toLocaleString('en-AE') : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
            <div className="modal-footer">
              <span style={{ fontSize: 12, color: 'var(--gray-500)', flex: 1 }}>
                {changeRows.length} change{changeRows.length !== 1 ? 's' : ''} across {new Set(changeRows.map(r => r.emp.id)).size} employee{new Set(changeRows.map(r => r.emp.id)).size !== 1 ? 's' : ''}
              </span>
              <button className="btn btn-outline" onClick={() => setShowChanges(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showPanel && (
        <AllowDeductPanel
          entries={entries}
          employees={employees}
          onClose={() => setShowPanel(false)}
          onSave={(updated) => {
            setEntries(updated);
            triggerAutoSave(updated, meta);
            setShowPanel(false);
          }}
        />
      )}

      {/* ── Submit Payroll confirmation ── */}
      {confirmSubmit && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3>Submit Payroll</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setConfirmSubmit(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: 12 }}>
                You are about to submit payroll for <strong>{getMonthName(month)} {year}</strong>.
              </p>
              <p style={{ marginBottom: 12 }}>
                Payslips will be generated for <strong>{activeEntries.length} employee{activeEntries.length !== 1 ? 's' : ''}</strong> and made visible in their Employee Portal.
              </p>
              <p style={{ fontSize: 13, color: 'var(--gray-500)' }}>
                If payroll has been submitted before for this period, the existing payslips will be updated with the latest figures.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setConfirmSubmit(false)} disabled={submitting}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleSubmitPayroll} disabled={submitting}>
                {submitting ? 'Submitting…' : 'Confirm & Submit Payroll'}
              </button>
            </div>
          </div>
        </div>
      )}

      {preview && (
        <SIFPreviewModal
          sifContent={preview.content}
          filename={preview.filename}
          onClose={() => setPreview(null)}
          onDownload={() => {
            doDownload(preview.payroll);
            setPreview(null);
          }}
        />
      )}

    </div>
  );
}

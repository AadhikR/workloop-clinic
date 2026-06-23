import { useState, useRef, useEffect, useCallback } from 'react';
import { Download, Eye, Upload, AlertCircle, Plus, ChevronDown, CheckCircle, FileText, Info, Send, Lock, ShieldCheck, RefreshCw } from 'lucide-react';
import { generateSIF, generateSIFFilename, generateCorrectedSIF } from '../utils/sifGenerator';
import { parseCSV, readFileAsText } from '../utils/csvImport';
import { savePayroll, createPayslipRecords, saveWpsTracking,
         submitPayrollForApproval, approvePayroll, rejectPayroll, recallPayrollApproval,
         saveComplianceOverride } from '../utils/storage';
import { createNotifications } from '../utils/notificationStorage';
import AllowDeductPanel, { computeFinalAllowance } from './AllowDeductPanel';
import SIFPreviewModal from './SIFPreviewModal';
import { downloadPayslip, downloadAllPayslips } from '../utils/payslipGenerator';
import { calculatePayrollLeaveDeductions } from '../utils/leaveEngine';
import { getLeaveRequests } from '../utils/leaveStorage';
import { getAttendancePayrollData, getOvertimeFromRoster } from '../utils/attendanceStorage';
import { getAdvances } from '../utils/storage';
import { getApprovedUnpaidExpenses, markExpensesPaid } from '../utils/expenseStorage';
import { getPayrollSummaryFromAttendance, formatHours } from '../utils/attendanceEngine';

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
  const [autoSaved, setAutoSaved] = useState(false);
  const [leaveDeductions, setLeaveDeductions] = useState({}); // { [employeeId]: deductionResult }
  const [attendanceData, setAttendanceData]   = useState(null); // { periodClosed, payrollReady, byEmployee }
  const [advanceData, setAdvanceData]         = useState({}); // { [employeeId]: advance[] }
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
  const [approvedBy,      setApprovedBy]      = useState(payroll.approvedBy      ?? '');
  const [approvedAt,      setApprovedAt]      = useState(payroll.approvedAt      ?? null);
  const [submittedBy,     setSubmittedBy]     = useState(payroll.submittedBy     ?? '');
  const [rejectionReason, setRejectionReason] = useState(payroll.rejectionReason ?? '');

  // Licence compliance gate state (Feature 7.1)
  const [licenceGate, setLicenceGate] = useState(null); // { expiredStaff, overrideReason, pendingDownload }
  const [licenceOverrideReason, setLicenceOverrideReason] = useState('');

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

  // Load active advances for all employees — shown as an informational panel
  useEffect(() => {
    getAdvances().then(all => {
      const active = all.filter(a => a.status === 'active');
      const byEmp = {};
      for (const adv of active) {
        if (!byEmp[adv.employeeId]) byEmp[adv.employeeId] = [];
        byEmp[adv.employeeId].push(adv);
      }
      setAdvanceData(byEmp);
    }).catch(() => {}); // salary_advances table may not exist yet — fail silently
  }, []);

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

  // Auto-save helper — debounced 800ms after last change
  const triggerAutoSave = useCallback((updatedEntries, updatedMeta) => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(async () => {
      const p = {
        ...payroll,
        ...updatedMeta,
        sequenceNo: updatedMeta.sequenceNo,
        entries: updatedEntries.map(e => ({
          ...e,
          variableAllowance: computeFinalAllowance(e),
        })),
      };
      try {
        await savePayroll(p);
        onSave(p);
        setAutoSaved(true);
        setTimeout(() => setAutoSaved(false), 2000);
      } catch (err) {
        console.error('Auto-save failed:', err);
      }
    }, 800);
  }, [payroll, onSave]);

  const isLocked = payroll.status === 'generated';
  // approvalLocked: editing is frozen while pending review or after approval (but not yet generated)
  const approvalLocked = !isLocked && (approvalStatus === 'pending_approval' || approvalStatus === 'approved');
  const editingLocked  = isLocked || approvalLocked;

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

  const totalBasic      = activeEntries.reduce((s, e) => s + (parseFloat(e.basicSalary) || 0), 0);
  const totalAllowance  = activeEntries.reduce((s, e) => s + (parseFloat(e.allowance) || 0), 0);
  const totalIncrement  = activeEntries.reduce((s, e) => s + (parseFloat(e.increment) || 0), 0);
  const totalBonus      = activeEntries.reduce((s, e) => s + (parseFloat(e.bonus) || 0), 0);
  const totalOtherPay   = activeEntries.reduce((s, e) => s + (parseFloat(e.otherPay) || 0), 0);
  const totalDuCost     = activeEntries.reduce((s, e) => s + (parseFloat(e.duCost) || 0), 0);
  const totalAddAllow   = activeEntries.reduce((s, e) => s + (e.additionalAllowances || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const totalDeductions = activeEntries.reduce((s, e) => s + (e.deductions || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const totalFinal      = activeEntries.reduce((s, e) => s + computeFinalAllowance(e), 0);
  const grandTotal      = totalBasic + totalFinal;

  const buildPayroll = () => ({
    ...payroll,
    ...meta,
    sequenceNo: parseInt(meta.sequenceNo),
    entries: entries.map(e => ({
      ...e,
      variableAllowance: computeFinalAllowance(e),
    })),
  });

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
    const p = buildPayroll();
    const content = generateSIF(company, employees, p);
    const filename = generateSIFFilename(company, p);
    setPreview({ content, filename, payroll: p });
  };

  const handleDownload = async () => {
    // Feature 7.1 — Licence compliance gate: check for expired professional licences
    const today = new Date().toISOString().split('T')[0];
    const expiredStaff = entries
      .filter(e => !e.excluded)
      .map(e => employees.find(emp => emp.id === e.employeeId))
      .filter(emp => emp && emp.licenceAuthority && emp.licenceAuthority !== 'None'
                     && emp.licenceExpiry && emp.licenceExpiry < today);
    if (expiredStaff.length > 0 && !licenceGate) {
      setLicenceGate({ expiredStaff });
      return; // show confirmation modal
    }
    if (licenceGate) {
      // HR overriding — log the override then proceed
      if (licenceOverrideReason.trim().length < 10) {
        alert('Please provide a reason for the compliance override (minimum 10 characters).');
        return;
      }
      try {
        await saveComplianceOverride({
          overrideType: 'payroll_sif',
          employeeIds:  licenceGate.expiredStaff.map(e => e.id),
          reason:       licenceOverrideReason.trim(),
        });
      } catch (err) {
        console.error('Compliance override log failed:', err);
      }
      setLicenceGate(null);
      setLicenceOverrideReason('');
    }

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
      const p = buildPayroll();
      const finalised = { ...p, status: 'generated' };
      onSave(finalised);
      await createPayslipRecords(finalised);

      // Notify employees with linked portal accounts that their payslip is ready
      const payslipNotifs = (finalised.entries || [])
        .filter(e => !e.excluded)
        .map(e => {
          const emp = employees.find(em => em.id === e.employeeId);
          if (!emp?.authUserId) return null;
          const net = (parseFloat(e.basicSalary) || 0) + (parseFloat(e.variableAllowance) || 0);
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
      const allExpenseIds = Object.values(expenseData).flat().map(e => e.id);
      if (allExpenseIds.length > 0) {
        markExpensesPaid(allExpenseIds, finalised.id).catch(() => {});
      }
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

  const handleSaveDraft = () => {
    onSave({ ...buildPayroll(), status: payroll.status === 'generated' ? 'generated' : 'draft' });
  };

  // ── Payroll Approval handlers (Feature 17) ──────────────────────────────────
  const flashApproval = (type, text) => {
    setApprovalMsg({ type, text });
    setTimeout(() => setApprovalMsg(null), 5000);
  };

  const handleSubmitForApproval = async () => {
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
      setImportMsg({ type: 'success', text: `Updated ${matched} employee entries from CSV.` });
      setTimeout(() => setImportMsg(null), 5000);
    } catch (err) {
      setImportMsg({ type: 'danger', text: 'Failed to parse CSV: ' + err.message });
    }
  };

  const canGenerate = company?.molEmployerId && meta.paymentDate && meta.scrBankRoutingCode && activeEntries.length > 0;

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
          {autoSaved && (
            <span className="auto-save-indicator">
              <CheckCircle size={14} /> Auto-saved
            </span>
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
            title="Download payslips for all active employees"
            onClick={() => downloadAllPayslips(company, employees, buildPayroll())}
            disabled={!canGenerate}
          >
            <FileText size={14} /> All Payslips
          </button>
          <button className="btn btn-outline btn-sm" onClick={handlePreview} disabled={!canGenerate}>
            <Eye size={14} /> Preview SIF
          </button>
          <button className="btn btn-success btn-sm" onClick={handleDownload} disabled={!canGenerate}>
            <Download size={14} /> Download SIF
          </button>
          {isLocked && Object.values(wpsEntryStatuses).some(v => v.status === 'rejected') && (
            <button className="btn btn-outline btn-sm" onClick={handleDownloadCorrectedSIF} title="Download SIF for rejected employees only">
              <RefreshCw size={14} /> Corrected SIF
            </button>
          )}
          {/* Draft: submit for approval (Feature 17) */}
          {!isLocked && approvalStatus === 'draft' && (
            <button className="btn btn-primary btn-sm" onClick={handleSubmitForApproval} disabled={!canGenerate || approvalBusy}>
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
            <button className="btn btn-primary btn-sm" onClick={() => setConfirmSubmit(true)} disabled={!canGenerate}>
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
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--gray-600)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Per-Employee Payment Status
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {activeEntries.map(entry => {
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
            <div className="stat-label">Total Basic</div>
            <div className="stat-value">{totalBasic.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total WPS Allowance</div>
            <div className="stat-value">{totalFinal.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED (Final Allowance)</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Grand Total (WPS)</div>
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
        {Object.keys(advanceData).length > 0 && (
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
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(advanceData).map(([empId, advs]) => {
                    const emp = employees.find(e => e.id === empId);
                    return advs.map((adv, i) => (
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
                          -{adv.monthlyDeduction.toLocaleString('en-AE', { minimumFractionDigits:2 })}
                        </td>
                      </tr>
                    ));
                  })}
                </tbody>
                <tfoot>
                  <tr style={{ background:'var(--danger-light)', fontWeight:700 }}>
                    <td colSpan={4} style={{ textAlign:'right', paddingRight:12, color:'var(--danger)' }}>
                      Total Advance Deductions This Month
                    </td>
                    <td className="text-right" style={{ color:'var(--danger)' }}>
                      -{Object.values(advanceData)
                          .flat()
                          .reduce((s, a) => s + a.monthlyDeduction, 0)
                          .toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/>
              Add these deductions to employee entries via the <strong>Allowances &amp; Deductions</strong> panel, using label "Advance Repayment".
            </div>
          </div>
        )}

        {/* ── Roster Overtime Panel (Feature 5.2) ── */}
        {Object.keys(rosterOvertime).length > 0 && (() => {
          const empIds = Object.keys(rosterOvertime).filter(id => rosterOvertime[id].overtimeHours > 0);
          if (!empIds.length) return null;

          const applyOvertimeToEntry = (employeeId, overtimePay) => {
            setEntries(prev => prev.map(entry => {
              if (entry.employeeId !== employeeId) return entry;
              const existing = (entry.additionalAllowances || []);
              const alreadyApplied = existing.some(a => a.label === 'Overtime (Roster)');
              if (alreadyApplied) return entry; // idempotent — don't double-apply
              return {
                ...entry,
                additionalAllowances: [...existing, { label: 'Overtime (Roster)', amount: parseFloat(overtimePay.toFixed(2)) }],
              };
            }));
          };

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
                      const applied     = (entry?.additionalAllowances || []).some(a => a.label === 'Overtime (Roster)');
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
                              <span className="badge badge-green" style={{ fontSize: 11 }}>✓ Applied</span>
                            ) : (
                              <button
                                className="btn btn-secondary"
                                style={{ fontSize: 11, padding: '3px 10px' }}
                                onClick={() => applyOvertimeToEntry(empId, overtimePay)}
                                disabled={editingLocked}
                              >
                                Apply to Payroll
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
        {Object.keys(expenseData).length > 0 && (
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
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(expenseData).map(([empId, exps]) => {
                    const emp = employees.find(e => e.id === empId);
                    return exps.map((exp, i) => (
                      <tr key={exp.id}>
                        <td style={{ fontWeight: i === 0 ? 500 : 400, color: i === 0 ? 'var(--gray-800)' : 'var(--gray-400)' }}>
                          {i === 0 ? emp?.name : ''}
                        </td>
                        <td style={{ textTransform:'capitalize' }}>{exp.category?.replace('_',' ')}</td>
                        <td>{exp.expenseDate}</td>
                        <td style={{ maxWidth:200, overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis' }}>
                          {exp.description}
                        </td>
                        <td className="text-right" style={{ fontWeight:600, color:'var(--success)' }}>
                          +{exp.amount.toLocaleString('en-AE', { minimumFractionDigits:2 })} AED
                        </td>
                      </tr>
                    ));
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
                  </tr>
                </tfoot>
              </table>
            </div>
            <div style={{ padding:'10px 20px', fontSize:12, color:'var(--gray-500)', borderTop:'1px solid var(--gray-100)' }}>
              <Info size={12} style={{ marginRight:4 }}/>
              These expenses will be automatically marked as <strong>Paid</strong> when payroll is submitted.
              Add them to employee entries via <strong>Allowances &amp; Deductions</strong> (label: "Expense Reimbursement") so they appear in the SIF.
            </div>
          </div>
        )}

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
        <div className="card">
          <div className="card-header">
            <h3>Employee Salary Entries</h3>
            <div className="flex items-center gap-2">
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
                  <th style={{ width: 36 }}>✓</th>
                  <th>Name</th>
                  <th>MOL ID</th>
                  <th style={{ width: 110 }}>Basic</th>
                  <th style={{ width: 100 }}>Housing</th>
                  <th style={{ width: 100 }}>Transport</th>
                  <th style={{ width: 110 }}>Allowance</th>
                  <th style={{ width: 100 }}>Increment</th>
                  <th style={{ width: 110 }}>Bonus/Incentive</th>
                  <th style={{ width: 100 }}>Other Pay</th>
                  <th style={{ width: 100, color:'var(--danger)' }}>Leave Ded.</th>
                  <th
                    style={{ width: 90 }}
                    title={isLocked ? undefined : 'Click to add named additional allowances per employee'}
                    onClick={() => !isLocked && setShowPanel(true)}
                  >
                    {isLocked
                      ? <span>Add. Allow</span>
                      : <span style={hdrClickable}>Add. Allow <ChevronDown size={11} /></span>}
                  </th>
                  <th
                    style={{ width: 90 }}
                    title={isLocked ? undefined : 'Click to add named deductions per employee'}
                    onClick={() => !isLocked && setShowPanel(true)}
                  >
                    {isLocked
                      ? <span>Deductions</span>
                      : <span style={{ ...hdrClickable, color: 'var(--danger)' }}>Deductions <ChevronDown size={11} /></span>}
                  </th>
                  <th style={{ width: 100, background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>
                    Final Allow.
                  </th>
                  <th style={{ width: 100 }}>Total (AED)</th>
                  <th style={{ width: 60 }}>Payslip</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, idx) => {
                  const emp = getEmp(entry.employeeId);
                  if (!emp) return null;
                  const finalAllow = computeFinalAllowance(entry);
                  const addAllow = (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
                  const deds = (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);
                  const total = (parseFloat(entry.basicSalary) || 0) + finalAllow;
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
                      <td style={{ fontWeight: 500 }}>{emp.name}</td>
                      <td className="font-mono text-sm">{emp.molId}</td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.basicSalary} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'basicSalary', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.housingAllowance ?? emp.housingAllowance ?? 0} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'housingAllowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.transportAllowance ?? emp.transportAllowance ?? 0} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'transportAllowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.allowance} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'allowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.increment} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'increment', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.bonus} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'bonus', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.otherPay} disabled={isLocked || entry.excluded}
                          onChange={e => updateEntry(idx, 'otherPay', e.target.value)} />
                      </td>
                      <td style={{ position:'relative' }}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={entry.leaveDeduction ?? 0}
                          disabled={isLocked || entry.excluded}
                          placeholder="0.00"
                          title="Auto-filled from approved leave. Edit to override."
                          style={{ color: (parseFloat(entry.leaveDeduction) || 0) > 0 ? 'var(--danger)' : undefined }}
                          onChange={e => updateEntry(idx, 'leaveDeduction', parseFloat(e.target.value) || 0)}
                        />
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: addAllow > 0 ? 'var(--success)' : 'var(--gray-400)', cursor: isLocked ? 'default' : 'pointer' }}
                        onClick={() => !isLocked && setShowPanel(true)}
                        title={isLocked ? undefined : 'Click to edit'}
                      >
                        {addAllow > 0 ? `+${addAllow.toLocaleString('en-AE')}` : '—'}
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: deds > 0 ? 'var(--danger)' : 'var(--gray-400)', cursor: isLocked ? 'default' : 'pointer' }}
                        onClick={() => !isLocked && setShowPanel(true)}
                        title={isLocked ? undefined : 'Click to edit'}
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
                        {finalAllow.toLocaleString('en-AE')}
                      </td>
                     <td
                       className="text-right font-bold"
                       style={{ color: entry.excluded ? 'var(--gray-400)' : 'var(--gray-800)' }}
                     >
                       {total.toLocaleString('en-AE')}
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
                    {totalFinal.toLocaleString('en-AE')}
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
      {showPanel && (
        <AllowDeductPanel
          entries={entries}
          employees={employees}
          onClose={() => setShowPanel(false)}
          onSave={(updated) => { setEntries(updated); setShowPanel(false); }}
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

      {/* Feature 7.1 — Licence compliance override gate */}
      {licenceGate && (
        <div className="modal-overlay" style={{ zIndex: 2000 }}>
          <div className="modal" style={{ maxWidth: 520 }}>
            <div className="modal-header" style={{ background: '#fff5f5', borderBottom: '1px solid #fecaca' }}>
              <h3 style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertCircle size={18} /> Expired Professional Licences
              </h3>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--gray-700)', marginBottom: 12 }}>
                The following staff members have <strong>expired professional licences</strong>.
                Generating a SIF for these employees may violate DHA/DOH/MOH regulations.
              </p>
              <table className="table" style={{ marginBottom: 16 }}>
                <thead><tr><th>Employee</th><th>Authority</th><th>Expired</th></tr></thead>
                <tbody>
                  {licenceGate.expiredStaff.map(emp => (
                    <tr key={emp.id} style={{ background: '#fff5f5' }}>
                      <td style={{ fontWeight: 500 }}>{emp.name}</td>
                      <td><span className="badge badge-red">{emp.licenceAuthority}</span></td>
                      <td style={{ color: 'var(--danger)', fontSize: 13 }}>{emp.licenceExpiry}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="form-group">
                <label style={{ color: 'var(--danger)', fontWeight: 600 }}>
                  Override Reason (HR authority required) *
                </label>
                <textarea
                  className="form-control"
                  rows={3}
                  value={licenceOverrideReason}
                  onChange={e => setLicenceOverrideReason(e.target.value)}
                  placeholder="State the clinical justification for proceeding despite expired licences (min 10 characters)…"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => { setLicenceGate(null); setLicenceOverrideReason(''); }}>
                Cancel — Resolve Licences First
              </button>
              <button className="btn btn-danger" onClick={handleDownload} disabled={licenceOverrideReason.trim().length < 10}>
                <Download size={14} /> Override &amp; Download SIF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * RosterManager.jsx — Clinical Duty Rota (Feature 2.1 + Feature 8)
 *
 * Tabs:
 *   1. Templates — Create/edit shift templates with short code (D/N/M/A) + category
 *   2. Roster    — Monthly grid: compact code-based cells, dept-scoped, totals, CSV export
 *   3. Swaps     — Review and approve/reject employee shift-swap requests
 */
import { useState, useEffect, useRef } from 'react';
import {
  Plus, Edit2, Trash2, Check, X,
  ChevronLeft, ChevronRight, Send, AlertCircle, Download,
} from 'lucide-react';
import { getEmployees, getAllEmployeeDocuments, saveComplianceOverride } from '../utils/storage';
import { getDeptStaffingRules } from '../utils/staffingStorage';
import { getLeaveRequests } from '../utils/leaveStorage';
import { createNotifications } from '../utils/notificationStorage';
import { CLINICAL_DOC_TYPES } from './EmployeeModal';
import { useCompany } from '../context/CompanyContext';
import {
  getShifts, saveShift, deleteShift,
  getRosterForMonth, saveRosterAssignment, deleteRosterAssignment, publishRoster,
  getShiftSwapRequests, updateShiftSwapRequest,
} from '../utils/attendanceStorage';
import { formatDateUAE, clampNumber } from '../utils/uaeValidators';

// ── helpers ───────────────────────────────────────────────────────────────────

function pad2(n) { return String(n).padStart(2, '0'); }

function fmtTime(t) {
  if (!t) return '—';
  return String(t).slice(0, 5);
}

function autoExpectedHours(startTime, endTime, breakMinutes) {
  if (!startTime || !endTime) return 8;
  const [sh, sm] = startTime.split(':').map(Number);
  const [eh, em] = endTime.split(':').map(Number);
  let mins = (eh * 60 + em) - (sh * 60 + sm);
  if (mins < 0) mins += 24 * 60;
  mins -= (breakMinutes || 0);
  return Math.round(Math.max(0, mins) / 60 * 10) / 10;
}

const PALETTE = [
  '#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#84cc16', '#f97316', '#ec4899',
];

const SHIFT_CATEGORIES = [
  { value: 'morning',   label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'night',     label: 'Night' },
  { value: 'flexible',  label: 'Flexible / Other' },
];

const CATEGORY_LABELS = {
  morning:   '☀ Morning',
  afternoon: '🌤 Afternoon',
  night:     '🌙 Night',
  flexible:  'Flexible / Other',
};

const CATEGORY_COLORS = {
  morning:   '#f59e0b',
  afternoon: '#06b6d4',
  night:     '#6366f1',
  flexible:  '#10b981',
};

const EMPTY_FORM = {
  name: '', code: '', color: '#6366f1', shiftCategory: 'morning',
  startTime: '09:00', endTime: '18:00',
  breakMinutes: 60, expectedHours: 8,
  lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10,
  minStaff: 1,
};

// ── CSV export ────────────────────────────────────────────────────────────────

function exportRosterCsv({ year, month, daysInMonth, employees, shifts, rosterData, rosterMonth }) {
  const monthLabel = rosterMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' });
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  function getCode(empId, day) {
    const dateStr = `${year}-${pad2(month)}-${pad2(day)}`;
    const a = rosterData[`${empId}_${dateStr}`];
    if (!a) return 'O';
    const sh = shifts.find(s => s.id === a.shiftId);
    return sh?.code || sh?.name?.substring(0, 2)?.toUpperCase() || 'S';
  }

  function getCategory(empId, day) {
    const dateStr = `${year}-${pad2(month)}-${pad2(day)}`;
    const a = rosterData[`${empId}_${dateStr}`];
    if (!a) return null;
    const sh = shifts.find(s => s.id === a.shiftId);
    return sh?.shiftCategory || 'flexible';
  }

  function getPlannedHours(empId) {
    let total = 0;
    for (const d of days) {
      const dateStr = `${year}-${pad2(month)}-${pad2(d)}`;
      const a = rosterData[`${empId}_${dateStr}`];
      if (a) {
        const sh = shifts.find(s => s.id === a.shiftId);
        total += a.plannedHours ?? sh?.expectedHours ?? 0;
      }
    }
    return parseFloat(total.toFixed(1));
  }

  const rows = [];

  // Title row
  rows.push([`DUTY ROSTER — ${monthLabel.toUpperCase()}`, '', '', ...days.map(() => ''), '', '', '', '', '']);

  // Header
  rows.push(['STAFF NAME', 'DEPT', 'SH', ...days.map(d => String(d)), 'M', 'A', 'N', 'O', 'TOTAL HRS']);

  // Employee rows
  for (const emp of employees) {
    let m = 0, a = 0, n = 0, o = 0;
    const dayCodes = days.map(day => {
      const code = getCode(emp.id, day);
      const cat  = getCategory(emp.id, day);
      if (!cat) { o++; return 'O'; }
      if (cat === 'morning' || cat === 'flexible') m++;
      else if (cat === 'afternoon') a++;
      else if (cat === 'night') n++;
      return code;
    });
    const totalHrs = getPlannedHours(emp.id);
    const shiftCount = m + a + n;
    rows.push([emp.name, emp.department || '', shiftCount, ...dayCodes, m, a, n, o, totalHrs]);
  }

  // Blank separator
  rows.push(Array(days.length + 9).fill(''));

  // Summary footer — count per category per day
  const mRow = ['Total Morning', '', '', ...days.map(day => {
    return employees.filter(emp => getCategory(emp.id, day) === 'morning' || (getCategory(emp.id, day) === 'flexible' && rosterData[`${emp.id}_${year}-${pad2(month)}-${pad2(day)}`])).length;
  }), '', '', '', '', ''];

  const aRow = ['Total Afternoon', '', '', ...days.map(day => {
    return employees.filter(emp => getCategory(emp.id, day) === 'afternoon').length;
  }), '', '', '', '', ''];

  const nRow = ['Total Night', '', '', ...days.map(day => {
    return employees.filter(emp => getCategory(emp.id, day) === 'night').length;
  }), '', '', '', '', ''];

  const oRow = ['Off / Uncovered', '', '', ...days.map(day => {
    return employees.filter(emp => !rosterData[`${emp.id}_${year}-${pad2(month)}-${pad2(day)}`]).length;
  }), '', '', '', '', ''];

  rows.push(mRow, aRow, nRow, oRow);

  const csv = rows.map(r => r.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `Roster_${year}_${pad2(month)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── component ─────────────────────────────────────────────────────────────────

export default function RosterManager() {
  const { activeCompany, activeCompanyId } = useCompany();
  const staffingRulesEnabled = activeCompany?.enableStaffingRules !== false;
  const [tab, setTab]         = useState('templates');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg]         = useState(null);

  // Shift templates
  const [shifts, setShifts]           = useState([]);
  const [shiftForm, setShiftForm]     = useState(null);
  const [shiftSaving, setShiftSaving] = useState(false);

  // Employees & roster
  const [employees, setEmployees]               = useState([]);
  const [rosterMonth, setRosterMonth]           = useState(new Date());
  const [rosterData, setRosterData]             = useState({});
  const [savingCell, setSavingCell]             = useState(null);
  const [publishing, setPublishing]             = useState(false);
  const [rosterDeptFilter, setRosterDeptFilter] = useState('');

  // Swaps
  const [swaps, setSwaps]           = useState([]);
  const [swapSaving, setSwapSaving] = useState(null);

  // Compliance — Feature 7.1 & 7.2
  // licenceMap: { [employeeId]: 'valid'|'expiring'|'expired'|'missing' }
  const [licenceMap, setLicenceMap] = useState({});

  // Staffing rules (Feature 7.2)
  const [staffingRules, setStaffingRules] = useState([]);
  // Publish block modal state
  const [publishGate, setPublishGate] = useState(null); // { violations, leaveConflicts } or null

  // Leave conflicts — map key `${empId}_${dateStr}` → { status, code }
  // Populated per-month load. Statuses considered blocking:
  //   'Approved'         — HR final approval, hardest block
  //   'ManagerApproved'  — awaiting HR, treat as blocking with softer message
  //   'Pending'          — advisory, no block (employee hasn't been told yes yet)
  const [leaveMap, setLeaveMap] = useState({});

  const initialLoadDone = useRef(false);

  const rYear  = rosterMonth.getFullYear();
  const rMonth = rosterMonth.getMonth() + 1;

  // ── data loading ─────────────────────────────────────────────────────────────

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (!initialLoadDone.current) return;
    loadRoster();
  }, [rosterMonth, activeCompanyId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload everything when the admin switches active company.
  useEffect(() => {
    if (!initialLoadDone.current) return;
    loadAll();
  }, [activeCompanyId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadAll() {
    setLoading(true);
    try {
      const [emps, shfts, swapReqs, roster, allDocs, deptRules, leaves] = await Promise.all([
        getEmployees(activeCompanyId),
        getShifts(),
        getShiftSwapRequests({}, activeCompanyId).catch(() => []),
        getRosterForMonth(rYear, rMonth, activeCompanyId).catch(() => []),
        getAllEmployeeDocuments().catch(() => []),
        getDeptStaffingRules().catch(() => []),
        getLeaveRequests().catch(() => []),
      ]);
      setStaffingRules(deptRules);
      const activeEmps = emps.filter(e => e.employmentStatus !== 'Terminated');
      setEmployees(activeEmps);
      setShifts(shfts);
      setSwaps(swapReqs);
      buildRosterMap(roster);
      buildLeaveMap(leaves);

      // Build licence compliance map (Feature 7.1)
      const PRIMARY_LICENCES = new Set(['DHA Licence', 'DOH Licence', 'MOH Licence']);
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const soon  = new Date(today); soon.setDate(soon.getDate() + 30);
      const map = {};
      for (const emp of activeEmps) {
        const empDocs = allDocs.filter(d =>
          d.employeeId === emp.id && PRIMARY_LICENCES.has(d.documentType)
        );
        if (!empDocs.length) { map[emp.id] = 'missing'; continue; }
        const validDocs    = empDocs.filter(d => !d.expiryDate || new Date(d.expiryDate) > today);
        const expiringDocs = validDocs.filter(d => d.expiryDate && new Date(d.expiryDate) <= soon);
        if (!validDocs.length) map[emp.id] = 'expired';
        else if (expiringDocs.length) map[emp.id] = 'expiring';
        else map[emp.id] = 'valid';
      }
      setLicenceMap(map);
    } catch (err) {
      showMsg('danger', 'Load failed: ' + err.message);
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }

  async function loadRoster() {
    try {
      const [roster, leaves] = await Promise.all([
        getRosterForMonth(rYear, rMonth, activeCompanyId),
        // Unfiltered leave fetch, then bucket in-flight statuses. Matches the
        // "call getLeaveRequests unfiltered" pattern (see CLAUDE.md — report
        // builders trap).
        getLeaveRequests().catch(() => []),
      ]);
      buildRosterMap(roster);
      buildLeaveMap(leaves);
    } catch (err) {
      showMsg('danger', 'Failed to load roster: ' + err.message);
    }
  }

  // Expand each blocking leave request into per-date entries covering the
  // currently-viewed month, so cell edits and the publish gate can look up
  // `${empId}_${dateStr}` in O(1).
  function buildLeaveMap(leaves) {
    const monthStart = new Date(rYear, rMonth - 1, 1);
    const monthEnd   = new Date(rYear, rMonth, 0);
    const map = {};
    for (const lr of leaves) {
      if (!['Approved', 'ManagerApproved'].includes(lr.status)) continue;
      if (!lr.startDate || !lr.endDate) continue;
      const start = new Date(lr.startDate);
      const end   = new Date(lr.endDate);
      // Clip to the visible month for cheap iteration.
      const from = start < monthStart ? monthStart : start;
      const to   = end   > monthEnd   ? monthEnd   : end;
      for (let d = new Date(from); d <= to; d.setDate(d.getDate() + 1)) {
        const key = `${lr.employeeId}_${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
        // If multiple overlapping requests, prefer the harder status.
        if (!map[key] || (map[key].status === 'ManagerApproved' && lr.status === 'Approved')) {
          map[key] = { status: lr.status, code: lr.leaveTypeCode || '' };
        }
      }
    }
    setLeaveMap(map);
  }

  function buildRosterMap(assignments) {
    const map = {};
    for (const a of assignments) map[`${a.employeeId}_${a.date}`] = a;
    setRosterData(map);
  }

  function showMsg(type, text) {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  }

  // ── shift template CRUD ──────────────────────────────────────────────────────

  async function handleSaveShift() {
    if (!shiftForm?.name?.trim()) return;
    // Clamp numeric fields into safe ranges. Overnight shifts (start > end)
    // are legitimate — we surface a soft confirm rather than block, matching
    // the existing pattern for non-blocking human review.
    const cleaned = {
      ...shiftForm,
      breakMinutes:               clampNumber(shiftForm.breakMinutes, 0, 480),
      expectedHours:              clampNumber(shiftForm.expectedHours, 0, 24),
      lateGraceMinutes:           clampNumber(shiftForm.lateGraceMinutes, 0, 240),
      earlyDepartureGraceMinutes: clampNumber(shiftForm.earlyDepartureGraceMinutes, 0, 240),
      minStaff:                   clampNumber(shiftForm.minStaff, 0, 999),
    };
    if (cleaned.startTime && cleaned.endTime && cleaned.startTime > cleaned.endTime) {
      const ok = window.confirm(
        `Start time (${cleaned.startTime}) is after end time (${cleaned.endTime}). Save as an overnight shift?`,
      );
      if (!ok) return;
    }
    setShiftSaving(true);
    try {
      const saved = await saveShift(cleaned);
      setShifts(prev =>
        shiftForm.id ? prev.map(s => s.id === saved.id ? saved : s) : [...prev, saved]
      );
      setShiftForm(null);
      showMsg('success', `Shift "${saved.name}" saved.`);
    } catch (err) {
      showMsg('danger', 'Failed to save shift: ' + err.message);
    } finally {
      setShiftSaving(false);
    }
  }

  async function handleDeleteShift(id) {
    if (!window.confirm('Deactivate this shift template?')) return;
    try {
      await deleteShift(id);
      setShifts(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      showMsg('danger', 'Failed: ' + err.message);
    }
  }

  // ── roster cell change ───────────────────────────────────────────────────────

  async function handleCellChange(empId, dateStr, shiftId) {
    const cellKey = `${empId}_${dateStr}`;

    // Leave-conflict guard — only when assigning (not when clearing).
    if (shiftId) {
      const conflict = leaveMap[cellKey];
      if (conflict) {
        const emp   = employees.find(e => e.id === empId);
        const label = conflict.status === 'Approved'
          ? 'APPROVED leave (HR-signed off)'
          : 'manager-approved leave (awaiting HR)';
        const ok = window.confirm(
          `${emp?.name || 'This employee'} has ${label}` +
          (conflict.code ? ` (${conflict.code})` : '') +
          ` on ${formatDateUAE(dateStr)}.\n\nAssign the shift anyway?`,
        );
        if (!ok) return;
      }
    }

    setSavingCell(cellKey);
    try {
      if (!shiftId) {
        await deleteRosterAssignment(empId, dateStr);
        setRosterData(prev => { const n = { ...prev }; delete n[cellKey]; return n; });
      } else {
        const sh = shifts.find(s => s.id === shiftId);
        const existing = rosterData[cellKey];
        const saved = await saveRosterAssignment({
          employeeId:   empId,
          shiftId,
          date:         dateStr,
          plannedHours: sh?.expectedHours ?? null,
          published:    existing?.published ?? false,
          companyId:    activeCompanyId,
        });
        setRosterData(prev => ({ ...prev, [cellKey]: saved }));
      }
    } catch (err) {
      showMsg('danger', 'Roster update failed: ' + err.message);
    } finally {
      setSavingCell(null);
    }
  }

  async function handlePublish() {
    let violations     = [];
    let leaveConflicts = [];
    const daysInMonth  = new Date(rYear, rMonth, 0).getDate();

    // Feature 7.2 — staffing compliance check before publish. Skipped entirely
    // when the company has the Staffing Rules module disabled.
    if (staffingRulesEnabled && staffingRules.length > 0) {
      for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${rYear}-${pad2(rMonth)}-${pad2(d)}`;
        for (const rule of staffingRules) {
          const count = employees.filter(emp => {
            if (emp.department !== rule.department) return false;
            const assignment = rosterData[`${emp.id}_${dateStr}`];
            if (!assignment || !assignment.shiftId) return false;
            const shift = shifts.find(s => s.id === assignment.shiftId);
            return shift?.shiftCategory === rule.shiftCategory;
          }).length;
          if (count < rule.minStaff) {
            violations.push({ date: dateStr, department: rule.department, shiftCategory: rule.shiftCategory, required: rule.minStaff, actual: count });
          }
        }
      }
    }

    // Leave-conflict check — any (employee, day) that has both a shift and an
    // in-flight approved leave request. Surfaces the same override-modal so
    // the admin can either fix the roster or record why the double-book is OK
    // (rare — leave usually wins).
    for (const key of Object.keys(rosterData)) {
      if (leaveMap[key]) {
        const [empId, dateStr] = key.split('_');
        const emp = employees.find(e => e.id === empId);
        if (!emp) continue; // e.g. terminated employee's stale row
        leaveConflicts.push({
          date:       dateStr,
          employee:   emp.name,
          department: emp.department || '',
          status:     leaveMap[key].status,
          code:       leaveMap[key].code || '',
        });
      }
    }

    if (violations.length > 0 || leaveConflicts.length > 0) {
      setPublishGate({ violations, leaveConflicts });
      return;
    }
    await doPublish();
  }

  async function doPublish(overrideReason) {
    setPublishing(true);
    try {
      if (overrideReason) {
        await saveComplianceOverride({
          overrideType: 'roster_publish',
          employeeIds:  null,
          reason:       overrideReason,
        }).catch(() => {});
      }
      await publishRoster(rYear, rMonth, activeCompanyId);
      await loadRoster();
      setPublishGate(null);

      // Notify each employee whose row appears in this month. Dedup key
      // embeds the month so re-publishing is silent — matches the ON CONFLICT
      // DO NOTHING pattern used elsewhere in notificationStorage.js.
      try {
        const monthLabel = rosterMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' });
        const empIdsInMonth = new Set(Object.values(rosterData).map(a => a.employeeId));
        const notifs = employees
          .filter(e => e.authUserId && empIdsInMonth.has(e.id))
          .map(e => ({
            recipientUserId:   e.authUserId,
            type:              'roster_published',
            title:             `Roster published — ${monthLabel}`,
            body:              `Your shifts for ${monthLabel} are now visible in the Schedule tab.`,
            relatedEntityType: 'roster',
            relatedEntityId:   `roster_${rYear}-${pad2(rMonth)}`,
          }));
        if (notifs.length > 0) await createNotifications(notifs);
      } catch (err) {
        // Non-fatal — publish itself already succeeded.
        console.warn('roster publish notifications:', err);
      }

      showMsg('success', 'Roster published — employees can now view their schedule.');
    } catch (err) {
      showMsg('danger', 'Failed to publish roster: ' + err.message);
    } finally {
      setPublishing(false);
    }
  }

  // ── swap actions ─────────────────────────────────────────────────────────────

  async function handleSwapUpdate(id, status) {
    setSwapSaving(id);
    try {
      const updated = await updateShiftSwapRequest(id, status);
      setSwaps(prev => prev.map(s => s.id === id ? updated : s));
      // Approval mutates roster_assignments (sql/052_shift_swap_execution.sql),
      // so pull the roster back in for whichever month(s) are affected.
      if (status === 'approved') {
        await loadRoster();
        showMsg('success', 'Swap approved — roster has been rewritten.');
      } else {
        showMsg('success', `Swap request ${status}.`);
      }
    } catch (err) {
      showMsg('danger', 'Failed: ' + err.message);
    } finally {
      setSwapSaving(null);
    }
  }

  // ── derived values ───────────────────────────────────────────────────────────

  const daysInMonth       = new Date(rYear, rMonth, 0).getDate();
  const departments       = [...new Set(employees.map(e => e.department).filter(Boolean))].sort();
  const filteredEmployees = rosterDeptFilter
    ? employees.filter(e => e.department === rosterDeptFilter)
    : employees;
  const pendingSwaps    = swaps.filter(s => s.status === 'pending');
  const monthIsPublished = Object.values(rosterData).some(a => a.published);
  // Any assignment in the visible month that has never been published, OR
  // that was added/edited after the last publish (still !published on this row).
  const unpublishedCount = Object.values(rosterData).filter(a => !a.published).length;
  const hasUnpublishedChanges = monthIsPublished && unpublishedCount > 0;

  function getEmpPlannedHours(empId) {
    let total = 0;
    for (let d = 1; d <= daysInMonth; d++) {
      const key = `${empId}_${rYear}-${pad2(rMonth)}-${pad2(d)}`;
      const a   = rosterData[key];
      if (a) {
        const sh = shifts.find(s => s.id === a.shiftId);
        total += a.plannedHours ?? sh?.expectedHours ?? 0;
      }
    }
    return parseFloat(total.toFixed(1));
  }

  function getDayStats(day) {
    const dateStr = `${rYear}-${pad2(rMonth)}-${pad2(day)}`;
    let morning = 0, afternoon = 0, night = 0, off = 0;
    for (const emp of filteredEmployees) {
      const a = rosterData[`${emp.id}_${dateStr}`];
      if (!a) { off++; continue; }
      const sh  = shifts.find(s => s.id === a.shiftId);
      const cat = sh?.shiftCategory || 'flexible';
      if (cat === 'morning' || cat === 'flexible') morning++;
      else if (cat === 'afternoon') afternoon++;
      else if (cat === 'night') night++;
    }
    return { morning, afternoon, night, off };
  }

  // Returns true when dateStr is before the employee's first working day this month
  function isBeforeJoin(emp, dateStr) {
    const joinDate = (emp.joiningDate || emp.hireDate || '').substring(0, 10);
    if (!joinDate) return false;
    return dateStr < joinDate;
  }

  // Returns true when dateStr is the employee's exact join date and it's in this month
  function isJoinDay(emp, dateStr) {
    const joinDate = (emp.joiningDate || emp.hireDate || '').substring(0, 10);
    return joinDate === dateStr;
  }

  const TABS = [
    { id: 'templates', label: 'Shift Templates' },
    { id: 'roster',    label: 'Monthly Roster' },
    { id: 'swaps',     label: `Swap Requests${pendingSwaps.length > 0 ? ` (${pendingSwaps.length})` : ''}` },
  ];

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
      Loading Roster…
    </div>
  );

  return (
    <div>
      <div className="page-header">
        <h2>Shift Scheduling &amp; Roster</h2>
      </div>

      <div className="page-body">
        {msg && (
          <div className={`alert alert-${msg.type} mb-4`}>
            <AlertCircle size={14} /> {msg.text}
          </div>
        )}

        {/* Tab bar */}
        <div className="tabs" style={{ marginBottom: 20 }}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── TEMPLATES TAB ── */}
        {tab === 'templates' && (
          <div className="card">
            <div className="card-header">
              <h3>Shift Templates</h3>
              {!shiftForm && (
                <button className="btn btn-primary btn-sm" onClick={() => setShiftForm({ ...EMPTY_FORM })}>
                  <Plus size={14} /> New Shift
                </button>
              )}
            </div>

            <div className="card-body">
              {/* Form */}
              {shiftForm && (
                <div style={{
                  background: 'var(--gray-50)', border: '1px solid var(--gray-200)',
                  borderRadius: 10, padding: 20, marginBottom: 20,
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>
                    {shiftForm.id ? `Edit — ${shiftForm.name}` : 'New Shift Template'}
                  </div>

                  <div className="form-grid form-grid-2" style={{ gap: 12 }}>
                    <div className="form-group">
                      <label>Shift Name</label>
                      <input
                        className="form-control"
                        value={shiftForm.name}
                        onChange={e => setShiftForm(p => ({ ...p, name: e.target.value }))}
                        placeholder="e.g. Morning, Night, Split"
                      />
                    </div>

                    <div className="form-group">
                      <label>
                        Short Code
                        <span style={{ fontWeight: 400, color: 'var(--gray-400)', fontSize: 11, marginLeft: 4 }}>
                          (shown in grid, e.g. D, N, M)
                        </span>
                      </label>
                      <input
                        className="form-control"
                        value={shiftForm.code}
                        onChange={e => setShiftForm(p => ({ ...p, code: e.target.value.toUpperCase().slice(0, 3) }))}
                        placeholder="D"
                        maxLength={3}
                        style={{ fontFamily: 'monospace', fontWeight: 700, letterSpacing: 1 }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Category</label>
                      <select
                        className="form-control"
                        value={shiftForm.shiftCategory}
                        onChange={e => setShiftForm(p => ({ ...p, shiftCategory: e.target.value }))}
                      >
                        {SHIFT_CATEGORIES.map(c => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Color</label>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        {PALETTE.map(c => (
                          <button
                            key={c} type="button"
                            onClick={() => setShiftForm(p => ({ ...p, color: c }))}
                            style={{
                              width: 22, height: 22, borderRadius: '50%', background: c,
                              border: shiftForm.color === c ? '3px solid #1e293b' : '2px solid transparent',
                              cursor: 'pointer', padding: 0, flexShrink: 0,
                            }}
                          />
                        ))}
                        <input
                          type="color" value={shiftForm.color}
                          onChange={e => setShiftForm(p => ({ ...p, color: e.target.value }))}
                          style={{ width: 26, height: 26, borderRadius: 4, border: '1px solid var(--gray-300)', padding: 1, cursor: 'pointer' }}
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Start Time</label>
                      <input
                        className="form-control" type="time"
                        value={shiftForm.startTime || ''}
                        onChange={e => {
                          const v = e.target.value;
                          setShiftForm(p => ({ ...p, startTime: v, expectedHours: autoExpectedHours(v, p.endTime, p.breakMinutes) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>End Time</label>
                      <input
                        className="form-control" type="time"
                        value={shiftForm.endTime || ''}
                        onChange={e => {
                          const v = e.target.value;
                          setShiftForm(p => ({ ...p, endTime: v, expectedHours: autoExpectedHours(p.startTime, v, p.breakMinutes) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Break (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={180}
                        value={shiftForm.breakMinutes}
                        onChange={e => {
                          const v = parseInt(e.target.value) || 0;
                          setShiftForm(p => ({ ...p, breakMinutes: v, expectedHours: autoExpectedHours(p.startTime, p.endTime, v) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Expected Hours <span style={{ fontWeight: 400, color: 'var(--gray-400)', fontSize: 11 }}>(auto-computed)</span></label>
                      <input
                        className="form-control" type="number" min={0} max={24} step={0.5}
                        value={shiftForm.expectedHours}
                        onChange={e => setShiftForm(p => ({ ...p, expectedHours: parseFloat(e.target.value) || 0 }))}
                      />
                    </div>

                    <div className="form-group">
                      <label>Min Staff Required <span style={{ fontWeight: 400, color: 'var(--gray-400)', fontSize: 11 }}>(Feature 7.2)</span></label>
                      <input
                        className="form-control" type="number" min={1} max={50}
                        value={shiftForm.minStaff}
                        onChange={e => setShiftForm(p => ({ ...p, minStaff: parseInt(e.target.value) || 1 }))}
                      />
                    </div>

                    <div className="form-group">
                      <label>Late Grace (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={60}
                        value={shiftForm.lateGraceMinutes}
                        onChange={e => setShiftForm(p => ({ ...p, lateGraceMinutes: parseInt(e.target.value) || 0 }))}
                      />
                    </div>

                    <div className="form-group">
                      <label>Early Departure Grace (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={60}
                        value={shiftForm.earlyDepartureGraceMinutes}
                        onChange={e => setShiftForm(p => ({ ...p, earlyDepartureGraceMinutes: parseInt(e.target.value) || 0 }))}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleSaveShift}
                      disabled={shiftSaving || !shiftForm.name?.trim()}
                    >
                      {shiftSaving ? 'Saving…' : shiftForm.id ? 'Update Shift' : 'Create Shift'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setShiftForm(null)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Shift list */}
              {shifts.length === 0 ? (
                <div className="empty-state">
                  <h3>No shift templates yet</h3>
                  <p>Create at least one shift before building a roster.</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: 30 }}>Color</th>
                        <th>Name</th>
                        <th>Code</th>
                        <th>Category</th>
                        <th>Start</th>
                        <th>End</th>
                        <th>Break</th>
                        <th>Hours</th>
                        <th>Late Grace</th>
                        <th>Early Grace</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {shifts.map(s => (
                        <tr key={s.id}>
                          <td>
                            <div style={{ width: 18, height: 18, borderRadius: 4, background: s.color || '#6366f1' }} />
                          </td>
                          <td style={{ fontWeight: 600 }}>{s.name}</td>
                          <td>
                            {s.code ? (
                              <span style={{
                                fontFamily: 'monospace', fontWeight: 700, fontSize: 12,
                                background: (s.color || '#6366f1') + '22',
                                color: s.color || '#6366f1',
                                padding: '2px 7px', borderRadius: 4,
                                border: `1px solid ${(s.color || '#6366f1')}44`,
                              }}>
                                {s.code}
                              </span>
                            ) : <span style={{ color: 'var(--gray-300)' }}>—</span>}
                          </td>
                          <td style={{ fontSize: 12 }}>
                            {s.shiftCategory ? (
                              <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                fontSize: 11, padding: '2px 7px', borderRadius: 10,
                                background: CATEGORY_COLORS[s.shiftCategory] + '18',
                                color: CATEGORY_COLORS[s.shiftCategory],
                                border: `1px solid ${CATEGORY_COLORS[s.shiftCategory]}33`,
                              }}>
                                {SHIFT_CATEGORIES.find(c => c.value === s.shiftCategory)?.label || s.shiftCategory}
                              </span>
                            ) : '—'}
                          </td>
                          <td>{fmtTime(s.startTime)}</td>
                          <td>{fmtTime(s.endTime)}</td>
                          <td>{s.breakMinutes} min</td>
                          <td>{s.expectedHours}h</td>
                          <td>{s.lateGraceMinutes} min</td>
                          <td>{s.earlyDepartureGraceMinutes} min</td>
                          <td>
                            <div style={{ display: 'flex', gap: 4 }}>
                              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setShiftForm({ ...s })} title="Edit">
                                <Edit2 size={13} />
                              </button>
                              <button className="btn btn-ghost btn-icon btn-sm text-danger" onClick={() => handleDeleteShift(s.id)} title="Deactivate">
                                <Trash2 size={13} />
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

        {/* ── ROSTER TAB ── */}
        {tab === 'roster' && (
          <div className="card">
            {/* Header */}
            <div className="card-header" style={{ flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => setRosterMonth(new Date(rYear, rMonth - 2, 1))}
                >
                  <ChevronLeft size={16} />
                </button>
                {rosterMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' })}
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => setRosterMonth(new Date(rYear, rMonth, 1))}
                >
                  <ChevronRight size={16} />
                </button>
              </h3>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {departments.length > 0 && (
                  <select
                    className="form-control"
                    style={{ width: 160, height: 32, fontSize: 12, padding: '0 8px' }}
                    value={rosterDeptFilter}
                    onChange={e => setRosterDeptFilter(e.target.value)}
                  >
                    <option value="">All Departments</option>
                    {departments.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                )}
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => exportRosterCsv({
                    year: rYear, month: rMonth, daysInMonth,
                    employees: filteredEmployees, shifts, rosterData, rosterMonth,
                  })}
                  disabled={filteredEmployees.length === 0}
                  title="Export duty rota as CSV"
                  style={{ display: 'flex', alignItems: 'center', gap: 5 }}
                >
                  <Download size={13} /> Export CSV
                </button>
                <button
                  className={`btn btn-sm ${hasUnpublishedChanges ? 'btn-warning' : 'btn-primary'}`}
                  onClick={handlePublish}
                  disabled={publishing || Object.keys(rosterData).length === 0}
                  title={
                    hasUnpublishedChanges
                      ? `${unpublishedCount} unpublished change${unpublishedCount === 1 ? '' : 's'} since last publish`
                      : monthIsPublished
                        ? 'Re-publish (update employee view)'
                        : 'Publish roster for employees to see'
                  }
                  style={hasUnpublishedChanges ? { background: '#f59e0b', borderColor: '#f59e0b', color: '#fff' } : undefined}
                >
                  <Send size={13} />
                  {publishing
                    ? 'Publishing…'
                    : hasUnpublishedChanges
                      ? `Re-publish · ${unpublishedCount} pending`
                      : monthIsPublished ? 'Re-publish' : 'Publish'}
                </button>
              </div>
            </div>

            {/* Feature 7.1 licence-compliance banner removed at user request —
                the per-row row-status dot in the roster grid continues to show
                expiring/expired badges for individual employees. */}

            {shifts.length === 0 ? (
              <div className="empty-state">
                <h3>No shift templates</h3>
                <p>Create shifts in the Templates tab first.</p>
                <button className="btn btn-primary btn-sm mt-3" onClick={() => setTab('templates')}>
                  Go to Templates
                </button>
              </div>
            ) : filteredEmployees.length === 0 ? (
              <div className="empty-state"><h3>No active employees</h3></div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', minWidth: '100%', fontSize: 11 }}>
                  <thead>
                    <tr style={{ background: 'var(--gray-50)' }}>
                      {/* Sticky employee name column */}
                      <th style={{
                        padding: '8px 12px', textAlign: 'left',
                        position: 'sticky', left: 0, zIndex: 2,
                        background: 'var(--gray-50)', minWidth: 160,
                        borderRight: '2px solid var(--gray-200)', borderBottom: '1px solid var(--gray-200)',
                      }}>
                        Employee
                      </th>
                      {/* Day columns */}
                      {Array.from({ length: daysInMonth }).map((_, i) => {
                        const day = i + 1;
                        const dow = new Date(`${rYear}-${pad2(rMonth)}-${pad2(day)}`).toLocaleString('en-AE', { weekday: 'short' });
                        const isWeekend = dow === 'Sat' || dow === 'Sun';
                        return (
                          <th key={day} style={{
                            padding: '4px 1px', textAlign: 'center',
                            minWidth: 40, width: 40,
                            borderRight: '1px solid var(--gray-100)',
                            borderBottom: '1px solid var(--gray-200)',
                            background: isWeekend ? '#f1f5f9' : 'var(--gray-50)',
                            color: isWeekend ? 'var(--gray-400)' : 'var(--gray-500)',
                          }}>
                            <div style={{ fontWeight: 700, fontSize: 11 }}>{day}</div>
                            <div style={{ fontSize: 9 }}>{dow}</div>
                          </th>
                        );
                      })}
                      {/* Totals column */}
                      <th style={{
                        padding: '8px 10px', textAlign: 'center',
                        minWidth: 60, borderLeft: '2px solid var(--gray-200)',
                        borderBottom: '1px solid var(--gray-200)',
                        background: 'var(--gray-50)', fontWeight: 700, fontSize: 11,
                        color: 'var(--primary)',
                      }}>
                        Total Hrs
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEmployees.map(emp => {
                      const totalHrs = getEmpPlannedHours(emp.id);
                      return (
                        <tr key={emp.id} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                          {/* Sticky name cell */}
                          <td style={{
                            padding: '6px 12px', fontWeight: 500,
                            position: 'sticky', left: 0, zIndex: 1,
                            background: 'white', borderRight: '2px solid var(--gray-200)',
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                              <div style={{ maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                                {emp.name}
                              </div>
                              {/* Feature 7.1 — Licence compliance badge */}
                              {(() => {
                                const ls = licenceMap[emp.id];
                                if (!ls || ls === 'valid') return null;
                                const cfg = {
                                  expired:  { bg: '#fee2e2', color: '#991b1b', title: 'Clinical licence EXPIRED', dot: '✗' },
                                  expiring: { bg: '#fef3c7', color: '#92400e', title: 'Licence expiring in ≤30d',  dot: '!' },
                                  missing:  { bg: '#fee2e2', color: '#991b1b', title: 'No DHA/DOH/MOH licence on file', dot: '?' },
                                }[ls];
                                return (
                                  <span title={cfg.title} style={{
                                    fontSize: 9, fontWeight: 700, lineHeight: 1,
                                    background: cfg.bg, color: cfg.color,
                                    borderRadius: 3, padding: '1px 4px', flexShrink: 0,
                                  }}>{cfg.dot}</span>
                                );
                              })()}
                            </div>
                            {emp.department && (
                              <div style={{ fontSize: 10, color: 'var(--gray-400)' }}>{emp.department}</div>
                            )}
                          </td>

                          {/* Day cells */}
                          {Array.from({ length: daysInMonth }).map((_, i) => {
                            const day        = i + 1;
                            const dateStr    = `${rYear}-${pad2(rMonth)}-${pad2(day)}`;
                            const cellKey    = `${emp.id}_${dateStr}`;
                            const assignment = rosterData[cellKey];
                            const sh         = assignment ? shifts.find(s => s.id === assignment.shiftId) : null;
                            const dow        = new Date(dateStr).toLocaleString('en-AE', { weekday: 'short' });
                            // UAE government/healthcare weekend is Sat–Sun (matches the
                            // column header shading on line 855). Was Fri/Sat pre-2022.
                            const isWeekend  = dow === 'Sat' || dow === 'Sun';
                            const isSaving   = savingCell === cellKey;
                            const beforeJoin = isBeforeJoin(emp, dateStr);
                            const joinDay    = isJoinDay(emp, dateStr);

                            return (
                              <td key={day} style={{
                                padding: '2px 1px', textAlign: 'center',
                                borderRight: '1px solid var(--gray-100)',
                                background: beforeJoin
                                  ? '#f1f5f9'
                                  : isWeekend ? '#fafbfc' : 'white',
                                opacity: beforeJoin ? 0.4 : 1,
                              }}>
                                {beforeJoin ? (
                                  <span style={{ fontSize: 9, color: 'var(--gray-300)' }}>–</span>
                                ) : (
                                  <>
                                    <select
                                      value={assignment?.shiftId || ''}
                                      disabled={isSaving}
                                      onChange={e => handleCellChange(emp.id, dateStr, e.target.value)}
                                      title={sh
                                        ? `${sh.name} (${sh.code || ''}) ${fmtTime(sh.startTime)}–${fmtTime(sh.endTime)}${assignment?.published ? ' ✓ published' : ''}`
                                        : 'Click to assign a shift'}
                                      style={{
                                        width: 38, height: 26, fontSize: 11,
                                        borderRadius: 5, padding: '0 1px',
                                        border: `2px solid ${sh ? sh.color : 'var(--gray-200)'}`,
                                        background: sh ? sh.color + '22' : 'transparent',
                                        color: sh ? sh.color : 'var(--gray-400)',
                                        fontWeight: sh ? 700 : 400,
                                        fontFamily: 'monospace',
                                        cursor: isSaving ? 'wait' : 'pointer',
                                        opacity: isSaving ? 0.5 : 1,
                                        textAlign: 'center',
                                        textAlignLast: 'center',
                                      }}
                                    >
                                      <option value="">—</option>
                                      {shifts.map(s => (
                                        <option key={s.id} value={s.id}>
                                          {s.code || s.name.substring(0, 3).toUpperCase()}
                                        </option>
                                      ))}
                                    </select>
                                    {joinDay && (
                                      <div style={{ fontSize: 8, color: 'var(--success)', lineHeight: 1, marginTop: 1 }}>
                                        joined
                                      </div>
                                    )}
                                    {assignment?.published && !joinDay && (
                                      <div style={{ fontSize: 8, color: 'var(--success)', lineHeight: 1, marginTop: 1 }}>✓</div>
                                    )}
                                  </>
                                )}
                              </td>
                            );
                          })}

                          {/* Totals cell */}
                          <td style={{
                            textAlign: 'center', fontWeight: 600, fontSize: 12,
                            borderLeft: '2px solid var(--gray-200)',
                            color: totalHrs > 0 ? 'var(--primary)' : 'var(--gray-300)',
                            padding: '0 10px',
                          }}>
                            {totalHrs > 0 ? `${totalHrs}h` : '—'}
                          </td>
                        </tr>
                      );
                    })}

                    {/* ── Summary footer rows ── */}
                    {filteredEmployees.length > 0 && (
                      <>
                        <tr style={{ borderTop: '2px solid var(--gray-200)', background: 'rgba(245,158,11,0.06)' }}>
                          <td style={{
                            padding: '4px 12px', fontSize: 10, fontWeight: 700,
                            color: CATEGORY_COLORS.morning,
                            position: 'sticky', left: 0, zIndex: 1,
                            background: 'rgba(245,158,11,0.06)',
                            borderRight: '2px solid var(--gray-200)',
                          }}>
                            ☀ Morning
                          </td>
                          {(() => {
                            const minMorning = Math.max(0, ...shifts.filter(s => s.shiftCategory === 'morning').map(s => s.minStaff || 1));
                            return Array.from({ length: daysInMonth }).map((_, i) => {
                              const day = i + 1;
                              const { morning } = getDayStats(day);
                              const understaffed = morning > 0 && minMorning > 1 && morning < minMorning;
                              return (
                                <td key={day} style={{
                                  textAlign: 'center', fontSize: 10, fontWeight: 600,
                                  color: understaffed ? '#dc2626' : morning > 0 ? CATEGORY_COLORS.morning : 'var(--gray-300)',
                                  background: understaffed ? '#fee2e2' : undefined,
                                  borderRight: '1px solid var(--gray-100)',
                                }}
                                  title={understaffed ? `Below minimum ${minMorning} staff` : undefined}
                                >
                                  {morning || ''}
                                </td>
                              );
                            });
                          })()}
                          <td style={{ borderLeft: '2px solid var(--gray-200)' }} />
                        </tr>
                        <tr style={{ background: 'rgba(6,182,212,0.05)' }}>
                          <td style={{
                            padding: '4px 12px', fontSize: 10, fontWeight: 700,
                            color: CATEGORY_COLORS.afternoon,
                            position: 'sticky', left: 0, zIndex: 1,
                            background: 'rgba(6,182,212,0.05)',
                            borderRight: '2px solid var(--gray-200)',
                          }}>
                            🌤 Afternoon
                          </td>
                          {Array.from({ length: daysInMonth }).map((_, i) => {
                            const day = i + 1;
                            const { afternoon } = getDayStats(day);
                            const minAft = Math.max(0, ...shifts.filter(s => s.shiftCategory === 'afternoon').map(s => s.minStaff || 1));
                            const underAft = afternoon > 0 && minAft > 1 && afternoon < minAft;
                            return (
                              <td key={day} style={{
                                textAlign: 'center', fontSize: 10, fontWeight: 600,
                                color: underAft ? '#dc2626' : afternoon > 0 ? CATEGORY_COLORS.afternoon : 'var(--gray-300)',
                                background: underAft ? '#fee2e2' : undefined,
                                borderRight: '1px solid var(--gray-100)',
                              }}
                                title={underAft ? `Below minimum ${minAft} staff` : undefined}
                              >
                                {afternoon || ''}
                              </td>
                            );
                          })}
                          <td style={{ borderLeft: '2px solid var(--gray-200)' }} />
                        </tr>
                        <tr style={{ background: 'rgba(99,102,241,0.05)' }}>
                          <td style={{
                            padding: '4px 12px', fontSize: 10, fontWeight: 700,
                            color: CATEGORY_COLORS.night,
                            position: 'sticky', left: 0, zIndex: 1,
                            background: 'rgba(99,102,241,0.05)',
                            borderRight: '2px solid var(--gray-200)',
                          }}>
                            🌙 Night
                          </td>
                          {(() => {
                            const minNight = Math.max(0, ...shifts.filter(s => s.shiftCategory === 'night').map(s => s.minStaff || 1));
                            return Array.from({ length: daysInMonth }).map((_, i) => {
                              const day = i + 1;
                              const { night } = getDayStats(day);
                              const underNight = night > 0 && minNight > 1 && night < minNight;
                              return (
                                <td key={day} style={{
                                  textAlign: 'center', fontSize: 10, fontWeight: 600,
                                  color: underNight ? '#dc2626' : night > 0 ? CATEGORY_COLORS.night : 'var(--gray-300)',
                                  background: underNight ? '#fee2e2' : undefined,
                                  borderRight: '1px solid var(--gray-100)',
                                }}
                                  title={underNight ? `Below minimum ${minNight} staff` : undefined}
                                >
                                  {night || ''}
                                </td>
                              );
                            });
                          })()}
                          <td style={{ borderLeft: '2px solid var(--gray-200)' }} />
                        </tr>
                        <tr style={{ background: 'var(--gray-50)' }}>
                          <td style={{
                            padding: '4px 12px', fontSize: 10, fontWeight: 700,
                            color: 'var(--gray-400)',
                            position: 'sticky', left: 0, zIndex: 1,
                            background: 'var(--gray-50)',
                            borderRight: '2px solid var(--gray-200)',
                          }}>
                            ○ Unassigned
                          </td>
                          {Array.from({ length: daysInMonth }).map((_, i) => {
                            const day = i + 1;
                            const { off } = getDayStats(day);
                            return (
                              <td key={day} style={{
                                textAlign: 'center', fontSize: 10, fontWeight: 600,
                                color: off > 0 ? 'var(--danger)' : 'var(--gray-300)',
                                borderRight: '1px solid var(--gray-100)',
                              }}>
                                {off || ''}
                              </td>
                            );
                          })}
                          <td style={{ borderLeft: '2px solid var(--gray-200)' }} />
                        </tr>
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Legend */}
            {shifts.length > 0 && (
              <div style={{
                padding: '10px 16px', borderTop: '1px solid var(--gray-100)',
                display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center',
              }}>
                {shifts.map(s => (
                  <span key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--gray-600)' }}>
                    <span style={{
                      fontFamily: 'monospace', fontWeight: 700, fontSize: 11,
                      background: (s.color || '#6366f1') + '22', color: s.color || '#6366f1',
                      padding: '1px 5px', borderRadius: 3,
                      border: `1px solid ${(s.color || '#6366f1')}44`,
                    }}>
                      {s.code || s.name.substring(0, 2).toUpperCase()}
                    </span>
                    {s.name} {s.startTime ? `(${fmtTime(s.startTime)}–${fmtTime(s.endTime)})` : ''}
                  </span>
                ))}
                <span style={{ fontSize: 11, color: 'var(--gray-400)' }}>
                  "—" = unassigned · ✓ = published · grey = before hire date
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── SWAPS TAB ── */}
        {tab === 'swaps' && (
          <div className="card">
            <div className="card-header">
              <h3>Shift Swap Requests</h3>
              <span style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 400 }}>
                {pendingSwaps.length} pending · {swaps.length} total
              </span>
            </div>

            {swaps.length === 0 ? (
              <div className="empty-state">
                <h3>No swap requests</h3>
                <p>Employees can submit shift swap requests from their Schedule tab in the portal.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Requested By</th>
                      <th>Their Date</th>
                      <th>Swap With</th>
                      <th>Their Date</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Submitted</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {swaps.map(sw => {
                      const requester = employees.find(e => e.id === sw.requesterEmployeeId);
                      const target    = employees.find(e => e.id === sw.targetEmployeeId);
                      return (
                        <tr key={sw.id}>
                          <td style={{ fontWeight: 500 }}>{requester?.name || '—'}</td>
                          <td>{formatDateUAE(sw.requesterDate)}</td>
                          <td>{target?.name || '—'}</td>
                          <td>{sw.targetDate ? formatDateUAE(sw.targetDate) : '—'}</td>
                          <td className="text-muted text-sm">{sw.reason || '—'}</td>
                          <td>
                            <span className={`badge ${
                              sw.status === 'approved'  ? 'badge-green' :
                              sw.status === 'rejected'  ? 'badge-red'   :
                              sw.status === 'cancelled' ? 'badge-gray'  : 'badge-amber'
                            }`}>
                              {sw.status}
                            </span>
                          </td>
                          <td className="text-muted text-sm">{sw.createdAt?.split('T')[0] || '—'}</td>
                          <td>
                            {sw.status === 'pending' && (
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  className="btn btn-primary btn-sm"
                                  onClick={() => handleSwapUpdate(sw.id, 'approved')}
                                  disabled={swapSaving === sw.id}
                                >
                                  <Check size={12} />
                                </button>
                                <button
                                  className="btn btn-ghost btn-sm text-danger"
                                  onClick={() => handleSwapUpdate(sw.id, 'rejected')}
                                  disabled={swapSaving === sw.id}
                                >
                                  <X size={12} />
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
            )}
          </div>
        )}
      </div>

      {/* Feature 7.2 — Publish staffing compliance + leave-conflict gate */}
      {publishGate && (
        <div className="modal-overlay" style={{ zIndex: 2000 }}>
          <div className="modal" style={{ maxWidth: 640 }}>
            <div className="modal-header" style={{ background: '#fff5f5', borderBottom: '1px solid #fecaca' }}>
              <h3 style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertCircle size={18} />
                {publishGate.violations.length > 0 && publishGate.leaveConflicts?.length > 0
                  ? 'Staffing + Leave Conflicts'
                  : publishGate.violations.length > 0
                    ? 'Staffing Below Minimum'
                    : 'Leave Conflicts'}
              </h3>
            </div>
            <div className="modal-body">
              {publishGate.violations.length > 0 && (
                <>
                  <p style={{ color: 'var(--gray-700)', marginBottom: 12 }}>
                    The roster has <strong>{publishGate.violations.length} date/shift combinations</strong> below the required minimum staff.
                    Publishing will make this visible to employees.
                  </p>
                  <div style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 16 }}>
                    <table className="table">
                      <thead><tr><th>Date</th><th>Department</th><th>Shift</th><th>Required</th><th>Assigned</th></tr></thead>
                      <tbody>
                        {publishGate.violations.slice(0, 30).map((v, i) => (
                          <tr key={i} style={{ background: '#fff5f5' }}>
                            <td style={{ fontSize: 13 }}>{formatDateUAE(v.date)}</td>
                            <td style={{ fontWeight: 500 }}>{v.department}</td>
                            <td>{CATEGORY_LABELS[v.shiftCategory] || v.shiftCategory}</td>
                            <td><span className="badge badge-blue">{v.required}</span></td>
                            <td><span className="badge badge-red">{v.actual}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {publishGate.violations.length > 30 && (
                      <p style={{ fontSize: 12, color: 'var(--gray-400)', textAlign: 'center', margin: '8px 0 0' }}>
                        …and {publishGate.violations.length - 30} more violations
                      </p>
                    )}
                  </div>
                </>
              )}

              {publishGate.leaveConflicts?.length > 0 && (
                <>
                  <p style={{ color: 'var(--gray-700)', marginBottom: 12 }}>
                    <strong>{publishGate.leaveConflicts.length} shift assignment{publishGate.leaveConflicts.length !== 1 ? 's' : ''}</strong> collide with approved leave.
                    Employees on leave will still see these shifts once published.
                  </p>
                  <div style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 16 }}>
                    <table className="table">
                      <thead><tr><th>Date</th><th>Employee</th><th>Department</th><th>Leave Status</th></tr></thead>
                      <tbody>
                        {publishGate.leaveConflicts.slice(0, 30).map((c, i) => (
                          <tr key={i} style={{ background: '#fffbeb' }}>
                            <td style={{ fontSize: 13 }}>{formatDateUAE(c.date)}</td>
                            <td style={{ fontWeight: 500 }}>{c.employee}</td>
                            <td style={{ fontSize: 12, color: 'var(--gray-500)' }}>{c.department || '—'}</td>
                            <td>
                              <span className={`badge ${c.status === 'Approved' ? 'badge-red' : 'badge-amber'}`}>
                                {c.status}{c.code ? ` · ${c.code}` : ''}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {publishGate.leaveConflicts.length > 30 && (
                      <p style={{ fontSize: 12, color: 'var(--gray-400)', textAlign: 'center', margin: '8px 0 0' }}>
                        …and {publishGate.leaveConflicts.length - 30} more conflicts
                      </p>
                    )}
                  </div>
                </>
              )}
                <div className="form-group">
                  <label style={{ color: 'var(--danger)', fontWeight: 600 }}>
                    Override Reason (required to publish despite violations)
                  </label>
                  <textarea
                    className="form-control"
                    rows={3}
                    value={publishGate.overrideReason || ''}
                    onChange={e => setPublishGate(prev => ({ ...prev, overrideReason: e.target.value }))}
                    placeholder="State the operational reason for publishing below minimum staffing (min 10 characters)…"
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-outline" onClick={() => setPublishGate(null)}>
                  Cancel — Fix Staffing
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => doPublish(publishGate.overrideReason)}
                  disabled={publishing || !publishGate.overrideReason || publishGate.overrideReason.trim().length < 10}
                >
                  <Send size={14} /> {publishing ? 'Publishing…' : 'Override & Publish'}
                </button>
              </div>
            </div>
          </div>
      )}
    </div>
  );
}

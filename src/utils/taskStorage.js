/**
 * taskStorage.js — Aggregates pending/actionable items across all modules.
 *
 * Three entry points: getAdminTasks(), getManagerTasks(), getEmployeeTasks().
 * Each returns { categories: [...] } where each category has a label, items[], and count.
 * Uses count-only queries where possible for performance.
 */

import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

function daysUntil(dateStr) {
  if (!dateStr) return Infinity;
  const d = new Date(dateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return Math.ceil((d - now) / 86400000);
}

function expiryUrgency(days) {
  if (days <= 0) return 'expired';
  if (days <= 14) return 'urgent';
  if (days <= 30) return 'warning';
  if (days <= 60) return 'info';
  return null;
}

function expiryLabel(days) {
  if (days <= 0) return 'Expired';
  return `${days}d left`;
}

// ─── ADMIN TASKS ────────────────────────────────────────────────────────────

export async function getAdminTasks(employees = []) {
  const user = await getSessionUser();
  if (!user) return { categories: [] };

  const results = await Promise.allSettled([
    fetchAdminApprovalTasks(),
    fetchAdminExpiryTasks(employees),
  ]);

  const approvals = results[0].status === 'fulfilled' ? results[0].value : [];
  const expiries = results[1].status === 'fulfilled' ? results[1].value : [];

  return {
    categories: [
      ...approvals.filter(c => c.items.length > 0),
      ...expiries.filter(c => c.items.length > 0),
    ],
  };
}

async function fetchAdminApprovalTasks() {
  const categories = [];

  // Leave requests pending
  const [leaves, expenses, advances, letters, docs, certs, regs, swaps, payrolls] =
    await Promise.allSettled([
      supabase.from('leave_requests').select('id, employee_id, status, leave_type_code, days_requested, created_at, employees!left(name)')
        .in('status', ['Pending', 'ManagerApproved']).order('created_at'),
      supabase.from('expense_claims').select('id, employee_id, status, amount, description, created_at, employees!left(name)')
        .in('status', ['pending', 'manager_approved']).order('created_at'),
      supabase.from('salary_advances').select('id, employee_id, status, amount, created_at, employees!left(name)')
        .eq('status', 'pending').order('created_at'),
      supabase.from('letter_requests').select('id, employee_id, status, letter_type, created_at, employees!left(name)')
        .eq('status', 'pending').order('created_at'),
      supabase.from('employee_documents').select('id, employee_id, doc_type, status, created_at, employees!left(name)')
        .eq('status', 'pending_verification').order('created_at'),
      supabase.from('certifications').select('id, employee_id, certification_name, status, created_at, employees!left(name)')
        .eq('status', 'pending_review').order('created_at'),
      supabase.from('regularisation_requests').select('id, employee_id, attendance_date, status, created_at, employees!left(name)')
        .eq('status', 'Pending').order('created_at'),
      supabase.from('shift_swap_requests').select('id, requester_employee_id, status, created_at').eq('status', 'pending'),
      supabase.from('payroll_runs').select('id, month, year, approval_status')
        .eq('approval_status', 'pending_approval'),
    ]);

  const leaveItems = extractData(leaves).map(r => ({
    id: `leave-${r.id}`, entity: 'leave', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — ${r.leave_type_code || 'Leave'} (${r.days_requested || '?'}d)`,
    subtitle: r.status === 'ManagerApproved' ? 'Manager approved, needs HR approval' : 'Pending approval',
    urgency: 'action', createdAt: r.created_at,
  }));
  if (leaveItems.length) categories.push({ label: 'Leave Requests', icon: 'calendar', items: leaveItems });

  const expenseItems = extractData(expenses).map(r => ({
    id: `expense-${r.id}`, entity: 'expenses', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — AED ${r.amount || 0}`,
    subtitle: r.description || (r.status === 'manager_approved' ? 'Manager approved' : 'Pending'),
    urgency: 'action', createdAt: r.created_at,
  }));
  if (expenseItems.length) categories.push({ label: 'Expense Claims', icon: 'receipt', items: expenseItems });

  const advanceItems = extractData(advances).map(r => ({
    id: `advance-${r.id}`, entity: 'advances', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — AED ${r.amount || 0}`,
    subtitle: 'Pending approval', urgency: 'action', createdAt: r.created_at,
  }));
  if (advanceItems.length) categories.push({ label: 'Salary Advances', icon: 'dollar', items: advanceItems });

  const letterItems = extractData(letters).map(r => ({
    id: `letter-${r.id}`, entity: 'letters', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — ${(r.letter_type || '').replace(/_/g, ' ')}`,
    subtitle: 'Pending', urgency: 'action', createdAt: r.created_at,
  }));
  if (letterItems.length) categories.push({ label: 'Letter Requests', icon: 'mail', items: letterItems });

  const docItems = extractData(docs).map(r => ({
    id: `doc-${r.id}`, entity: 'employees', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — ${(r.doc_type || '').replace(/_/g, ' ')}`,
    subtitle: 'Pending verification', urgency: 'action', createdAt: r.created_at,
  }));
  if (docItems.length) categories.push({ label: 'Document Verification', icon: 'folder', items: docItems });

  const certItems = extractData(certs).map(r => ({
    id: `cert-${r.id}`, entity: 'training', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — ${r.certification_name || 'Certification'}`,
    subtitle: 'Pending review', urgency: 'action', createdAt: r.created_at,
  }));
  if (certItems.length) categories.push({ label: 'Certification Review', icon: 'graduation', items: certItems });

  const regItems = extractData(regs).map(r => ({
    id: `reg-${r.id}`, entity: 'attendance', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — ${r.attendance_date || ''}`,
    subtitle: 'Regularisation pending', urgency: 'action', createdAt: r.created_at,
  }));
  if (regItems.length) categories.push({ label: 'Regularisation Requests', icon: 'clock', items: regItems });

  const swapItems = extractData(swaps).map(r => ({
    id: `swap-${r.id}`, entity: 'roster', entityId: r.id,
    title: 'Shift swap request',
    subtitle: 'Pending approval', urgency: 'action', createdAt: r.created_at,
  }));
  if (swapItems.length) categories.push({ label: 'Shift Swap Requests', icon: 'calendar', items: swapItems });

  const payrollItems = extractData(payrolls).map(r => ({
    id: `payroll-${r.id}`, entity: 'payroll', entityId: r.id,
    title: `Payroll ${r.month}/${r.year}`,
    subtitle: 'Awaiting approval', urgency: 'action',
  }));
  if (payrollItems.length) categories.push({ label: 'Payroll Approval', icon: 'file', items: payrollItems });

  return categories;
}

async function fetchAdminExpiryTasks(employees) {
  const categories = [];
  const today = new Date().toISOString().slice(0, 10);
  const horizon = new Date();
  horizon.setDate(horizon.getDate() + 60);
  const horizonStr = horizon.toISOString().slice(0, 10);

  // Employee document expiry (visa, passport, EID, labour card)
  const docExpiryItems = [];
  const fields = [
    { field: 'visa_expiry', label: 'Visa' },
    { field: 'passport_expiry', label: 'Passport' },
    { field: 'eid_expiry', label: 'Emirates ID' },
    { field: 'labour_card_expiry', label: 'Labour Card' },
    { field: 'licence_expiry', label: 'Professional Licence' },
  ];
  for (const emp of (employees || [])) {
    if (!emp.active && emp.active !== undefined) continue;
    for (const f of fields) {
      const val = emp[f.field] || emp[camelCase(f.field)];
      if (!val) continue;
      const days = daysUntil(val);
      const urg = expiryUrgency(days);
      if (urg) {
        docExpiryItems.push({
          id: `expiry-${emp.id}-${f.field}`,
          entity: 'employees', entityId: emp.id,
          title: `${emp.name || emp.emp_no || 'Employee'} — ${f.label}`,
          subtitle: expiryLabel(days),
          urgency: urg,
        });
      }
    }
  }
  if (docExpiryItems.length) categories.push({ label: 'Document Expiry', icon: 'alert', items: docExpiryItems });

  // Certification expiry
  const { data: certRows } = await supabase
    .from('certifications')
    .select('id, employee_id, certification_name, expiry_date, employees!left(name)')
    .lte('expiry_date', horizonStr)
    .gte('expiry_date', '1900-01-01')
    .order('expiry_date');
  const certExpiryItems = (certRows || []).map(r => {
    const days = daysUntil(r.expiry_date);
    return {
      id: `certexp-${r.id}`, entity: 'training', entityId: r.id,
      title: `${r.employees?.name || 'Employee'} — ${r.certification_name}`,
      subtitle: expiryLabel(days), urgency: expiryUrgency(days) || 'info',
    };
  }).filter(i => i.urgency);
  if (certExpiryItems.length) categories.push({ label: 'Certification Expiry', icon: 'graduation', items: certExpiryItems });

  // Probation ending
  const probItems = (employees || []).filter(e => {
    if (!e.active && e.active !== undefined) return false;
    const status = e.employment_status || e.employmentStatus;
    if (status !== 'Probation') return false;
    const end = e.probation_end_date || e.probationEndDate;
    if (!end) return false;
    const days = daysUntil(end);
    return days >= 0 && days <= 30;
  }).map(e => {
    const end = e.probation_end_date || e.probationEndDate;
    const days = daysUntil(end);
    return {
      id: `prob-${e.id}`, entity: 'employees', entityId: e.id,
      title: `${e.name || e.emp_no} — Probation ending`,
      subtitle: expiryLabel(days), urgency: days <= 7 ? 'urgent' : 'warning',
    };
  });
  if (probItems.length) categories.push({ label: 'Probation Ending', icon: 'user', items: probItems });

  // Contract expiry
  const { data: contractRows } = await supabase
    .from('employee_contracts')
    .select('id, employee_id, contract_type, end_date, employees!left(name)')
    .eq('contract_type', 'Limited')
    .lte('end_date', horizonStr)
    .gte('end_date', today)
    .order('end_date');
  const contractItems = (contractRows || []).map(r => {
    const days = daysUntil(r.end_date);
    return {
      id: `contract-${r.id}`, entity: 'employees', entityId: r.id,
      title: `${r.employees?.name || 'Employee'} — Contract ending`,
      subtitle: expiryLabel(days), urgency: days <= 14 ? 'urgent' : 'warning',
    };
  });
  if (contractItems.length) categories.push({ label: 'Contract Expiry', icon: 'file', items: contractItems });

  // Offboarding incomplete
  const { data: obRows } = await supabase
    .from('offboarding_checklists')
    .select('id, employee_id, employees!left(name), offboarding_tasks(id, completed)')
    .eq('status', 'in_progress');
  const obItems = (obRows || []).filter(r => {
    const tasks = r.offboarding_tasks || [];
    return tasks.some(t => !t.completed);
  }).map(r => {
    const tasks = r.offboarding_tasks || [];
    const done = tasks.filter(t => t.completed).length;
    return {
      id: `ob-${r.id}`, entity: 'employees', entityId: r.employee_id,
      title: `${r.employees?.name || 'Employee'} — Offboarding`,
      subtitle: `${done}/${tasks.length} tasks done`, urgency: 'warning',
    };
  });
  if (obItems.length) categories.push({ label: 'Offboarding In Progress', icon: 'user', items: obItems });

  // Appraisals needing calibration
  const { data: appraisalRows } = await supabase
    .from('appraisals')
    .select('id, employee_id, status, employees!left(name)')
    .eq('status', 'reviewed');
  const appraisalItems = (appraisalRows || []).map(r => ({
    id: `appr-${r.id}`, entity: 'appraisals', entityId: r.id,
    title: `${r.employees?.name || 'Employee'} — Needs calibration`,
    subtitle: 'Manager reviewed, pending HR calibration', urgency: 'action',
  }));
  if (appraisalItems.length) categories.push({ label: 'Appraisals', icon: 'star', items: appraisalItems });

  return categories;
}

// ─── MANAGER TASKS ──────────────────────────────────────────────────────────

export async function getManagerTasks() {
  const user = await getSessionUser();
  if (!user) return { categories: [] };

  const categories = [];

  const [leaves, expenses, appraisals, teamCerts] = await Promise.allSettled([
    supabase.rpc('manager_get_leave_queue'),
    supabase.rpc('manager_get_expense_queue'),
    supabase.from('appraisals').select('id, employee_id, status, employees!left(name)')
      .eq('status', 'pending'),
    supabase.from('certifications')
      .select('id, employee_id, certification_name, expiry_date, status, employees!left(name)'),
  ]);

  // Leave queue
  const leaveData = extractData(leaves);
  const pendingLeaves = leaveData.filter(r => r.status === 'Pending');
  if (pendingLeaves.length) {
    categories.push({
      label: 'Leave Approvals',
      icon: 'calendar',
      items: pendingLeaves.map(r => ({
        id: `mleave-${r.id}`, entity: 'queue', entityId: r.id,
        title: `${r.employee_name || r.employees?.name || 'Employee'} — ${r.leave_type_code || 'Leave'}`,
        subtitle: `${r.days_requested || '?'}d requested`, urgency: 'action',
      })),
    });
  }

  // Expense queue
  const expenseData = extractData(expenses);
  const pendingExpenses = expenseData.filter(r => r.status === 'pending');
  if (pendingExpenses.length) {
    categories.push({
      label: 'Expense Approvals',
      icon: 'receipt',
      items: pendingExpenses.map(r => ({
        id: `mexp-${r.id}`, entity: 'expenses', entityId: r.id,
        title: `${r.employee_name || r.employees?.name || 'Employee'} — AED ${r.amount || 0}`,
        subtitle: r.description || 'Pending pre-approval', urgency: 'action',
      })),
    });
  }

  // Team appraisals needing review
  const appraisalData = extractData(appraisals);
  if (appraisalData.length) {
    categories.push({
      label: 'Team Appraisals',
      icon: 'star',
      items: appraisalData.map(r => ({
        id: `mappr-${r.id}`, entity: 'appraisals', entityId: r.id,
        title: `${r.employees?.name || 'Employee'} — Needs review`,
        subtitle: 'Rate sections and submit', urgency: 'action',
      })),
    });
  }

  // Team certification expiry
  const certData = extractData(teamCerts);
  const today = new Date().toISOString().slice(0, 10);
  const certExpiryItems = certData
    .filter(r => r.expiry_date && r.status !== 'pending_review')
    .map(r => {
      const days = daysUntil(r.expiry_date);
      const urg = expiryUrgency(days);
      if (!urg) return null;
      return {
        id: `mcert-${r.id}`, entity: 'training', entityId: r.id,
        title: `${r.employees?.name || 'Employee'} — ${r.certification_name}`,
        subtitle: expiryLabel(days), urgency: urg,
      };
    }).filter(Boolean);
  if (certExpiryItems.length) {
    categories.push({ label: 'Team Cert Expiry', icon: 'graduation', items: certExpiryItems });
  }

  return { categories: categories.filter(c => c.items.length > 0) };
}

// ─── EMPLOYEE TASKS ─────────────────────────────────────────────────────────

export async function getEmployeeTasks() {
  const user = await getSessionUser();
  if (!user) return { categories: [] };

  // Get own employee record
  const { data: emp } = await supabase
    .from('employees')
    .select('*')
    .eq('auth_user_id', user.id)
    .maybeSingle();

  if (!emp) return { categories: [] };

  const categories = [];

  const [myCerts, myDocs, myLeaves, myAdvances, myExpenses, myLetters, myAttendance] =
    await Promise.allSettled([
      supabase.from('certifications').select('id, certification_name, expiry_date, status')
        .eq('employee_id', emp.id),
      supabase.from('employee_documents').select('id, doc_type, status')
        .eq('employee_id', emp.id),
      supabase.from('leave_requests').select('id, leave_type_code, status, days_requested')
        .eq('employee_id', emp.id).in('status', ['Pending', 'ManagerApproved']),
      supabase.from('salary_advances').select('id, amount, status')
        .eq('employee_id', emp.id).eq('status', 'pending'),
      supabase.from('expense_claims').select('id, amount, status, description')
        .eq('employee_id', emp.id).in('status', ['pending', 'manager_approved']),
      supabase.from('letter_requests').select('id, letter_type, status')
        .eq('employee_id', emp.id).eq('status', 'pending'),
      supabase.from('attendance_records').select('id, date, clock_in_time, clock_out_time')
        .eq('employee_id', emp.id).not('clock_in_time', 'is', null).is('clock_out_time', null),
    ]);

  // Document expiry (from employee record)
  const docExpiryItems = [];
  const fields = [
    { field: 'visa_expiry', label: 'Visa' },
    { field: 'passport_expiry', label: 'Passport' },
    { field: 'eid_expiry', label: 'Emirates ID' },
    { field: 'labour_card_expiry', label: 'Labour Card' },
  ];
  for (const f of fields) {
    const val = emp[f.field];
    if (!val) continue;
    const days = daysUntil(val);
    const urg = expiryUrgency(days);
    if (urg) {
      docExpiryItems.push({
        id: `edoc-${f.field}`, entity: 'documents', entityId: emp.id,
        title: `${f.label} ${days <= 0 ? 'expired' : 'expiring'}`,
        subtitle: expiryLabel(days), urgency: urg,
      });
    }
  }
  if (docExpiryItems.length) categories.push({ label: 'Document Expiry', icon: 'alert', items: docExpiryItems });

  // Certification expiry + rejected/pending
  const certData = extractData(myCerts);
  const certExpiryItems = certData.filter(r => r.expiry_date && r.status !== 'pending_review').map(r => {
    const days = daysUntil(r.expiry_date);
    const urg = expiryUrgency(days);
    if (!urg) return null;
    return {
      id: `ecert-${r.id}`, entity: 'training', entityId: r.id,
      title: `${r.certification_name} ${days <= 0 ? 'expired' : 'expiring'}`,
      subtitle: expiryLabel(days), urgency: urg,
    };
  }).filter(Boolean);
  if (certExpiryItems.length) categories.push({ label: 'Certification Expiry', icon: 'graduation', items: certExpiryItems });

  const rejectedCerts = certData.filter(r => r.status === 'rejected');
  if (rejectedCerts.length) {
    categories.push({
      label: 'Rejected Certifications',
      icon: 'alert',
      items: rejectedCerts.map(r => ({
        id: `ecertrej-${r.id}`, entity: 'training', entityId: r.id,
        title: `${r.certification_name} — Rejected`,
        subtitle: 'Resubmit required', urgency: 'urgent',
      })),
    });
  }

  // Rejected documents
  const docData = extractData(myDocs);
  const rejectedDocs = docData.filter(r => r.status === 'rejected');
  if (rejectedDocs.length) {
    categories.push({
      label: 'Rejected Documents',
      icon: 'folder',
      items: rejectedDocs.map(r => ({
        id: `edocrej-${r.id}`, entity: 'documents', entityId: r.id,
        title: `${(r.doc_type || '').replace(/_/g, ' ')} — Rejected`,
        subtitle: 'Resubmit required', urgency: 'urgent',
      })),
    });
  }

  // Missing clock-outs
  const attendanceData = extractData(myAttendance);
  const todayStr = new Date().toISOString().slice(0, 10);
  const missingClockOuts = attendanceData.filter(r => r.date < todayStr);
  if (missingClockOuts.length) {
    categories.push({
      label: 'Missing Clock-Out',
      icon: 'clock',
      items: missingClockOuts.map(r => ({
        id: `emco-${r.id}`, entity: 'attendance', entityId: r.id,
        title: `Missing clock-out — ${r.date}`,
        subtitle: 'Submit regularisation', urgency: 'urgent',
      })),
    });
  }

  // Pending leave requests (informational)
  const leaveData = extractData(myLeaves);
  if (leaveData.length) {
    categories.push({
      label: 'Pending Leave',
      icon: 'calendar',
      items: leaveData.map(r => ({
        id: `eleave-${r.id}`, entity: 'leave', entityId: r.id,
        title: `${r.leave_type_code || 'Leave'} — ${r.days_requested || '?'}d`,
        subtitle: r.status === 'ManagerApproved' ? 'Awaiting HR approval' : 'Awaiting approval',
        urgency: 'info',
      })),
    });
  }

  // Pending advances (informational)
  const advData = extractData(myAdvances);
  if (advData.length) {
    categories.push({
      label: 'Pending Advances',
      icon: 'dollar',
      items: advData.map(r => ({
        id: `eadv-${r.id}`, entity: 'advances', entityId: r.id,
        title: `Advance — AED ${r.amount || 0}`,
        subtitle: 'Awaiting approval', urgency: 'info',
      })),
    });
  }

  // Pending expenses (informational)
  const expData = extractData(myExpenses);
  if (expData.length) {
    categories.push({
      label: 'Pending Expenses',
      icon: 'receipt',
      items: expData.map(r => ({
        id: `eexp-${r.id}`, entity: 'expenses', entityId: r.id,
        title: `Expense — AED ${r.amount || 0}`,
        subtitle: r.status === 'manager_approved' ? 'Awaiting HR' : 'Awaiting approval',
        urgency: 'info',
      })),
    });
  }

  // Pending letters (informational)
  const letterData = extractData(myLetters);
  if (letterData.length) {
    categories.push({
      label: 'Pending Letters',
      icon: 'mail',
      items: letterData.map(r => ({
        id: `elet-${r.id}`, entity: 'requests', entityId: r.id,
        title: `${(r.letter_type || '').replace(/_/g, ' ')}`,
        subtitle: 'Awaiting HR', urgency: 'info',
      })),
    });
  }

  return { categories: categories.filter(c => c.items.length > 0) };
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function extractData(settled) {
  if (settled.status !== 'fulfilled') return [];
  const result = settled.value;
  if (result?.data) return result.data || [];
  return [];
}

function camelCase(str) {
  return str.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

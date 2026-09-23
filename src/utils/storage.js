/**
 * storage.js  –  Supabase-backed data layer for Workloop
 *
 * All functions are async and scoped to the currently logged-in user via RLS.
 * The shape of objects returned matches what the components already expect,
 * so component changes are minimal (just await the calls).
 */

import { supabase } from '../lib/supabase';

// ─── helpers ────────────────────────────────────────────────────────────────

/**
 * Returns the current user from the local session without a server round-trip.
 * Using getSession() instead of getUser() prevents the server-side JWT validation
 * from triggering refresh-token rotation, which causes SIGNED_OUT in tests.
 */
async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ─── COMPANY ────────────────────────────────────────────────────────────────

/**
 * Returns all company/branch rows for the current admin.
 * Multi-company (Feature 21): one admin can own multiple company rows.
 */
export async function getCompanies() {
  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .order('created_at', { ascending: true });

  if (error) { console.error('getCompanies:', error); return []; }
  return (data || []).map(dbToCompany);
}

/**
 * Returns a single company row.
 * If `id` is provided, returns that specific branch.
 * Without `id`, returns the first company (backward-compatible for single-company usage).
 */
export async function getCompany(id) {
  let query = supabase.from('companies').select('*');
  if (id) {
    query = query.eq('id', id);
  }
  const { data, error } = await query.limit(1).maybeSingle();
  if (error) { console.error('getCompany:', error); return null; }
  if (!data) return null;
  return dbToCompany(data);
}

/** Legacy organization writes are disabled after the Phase 7C authority switch. */
export async function saveCompany(company) {
  void company;
  throw new Error('Organization writes have moved to the migration settings screen.');
}

/** Legacy logo writes are disabled after the Phase 7C authority switch. */
export async function saveCompanyLogo(companyId, logoDataUrl) {
  void companyId;
  void logoDataUrl;
  throw new Error('Organization writes have moved to the migration settings screen.');
}

/**
 * Cascade a new SCR bank routing code from Company Settings down onto every
 * still-editable payroll run for the same branch.
 *
 * Scope is intentionally narrow — we only touch runs where BOTH:
 *   - status = 'draft'                 (not yet generated / locked)
 *   - approval_status = 'draft'        (not submitted for HR sign-off)
 * so a run mid-approval or already generated is never rewritten. Future runs
 * pick up the new code automatically because PayrollList pre-fills each new
 * run from `company.defaultBankRoutingCode`.
 *
 * Returns { count } — number of draft payrolls updated, for the UI to show
 * a "X drafts synced" confirmation. Does not throw when 0 rows match.
 */
export async function cascadeBankRoutingCodeToDrafts(companyId, newCode) {
  void companyId;
  void newCode;
  throw new Error('Payroll drafts have moved to the migration payroll workspace.');
}

/** Legacy branch creation is disabled after the Phase 7C authority switch. */
export async function createBranch(name, templateCompany) {
  void name;
  void templateCompany;
  throw new Error('Organization writes have moved to the migration settings screen.');
}

/** Legacy branch deletion is disabled after the Phase 7C authority switch. */
export async function deleteBranch(id) {
  void id;
  throw new Error('Organization writes have moved to the migration settings screen.');
}

// ─── EMPLOYEES ──────────────────────────────────────────────────────────────

/**
 * Returns employees for the current user, optionally filtered by branch.
 * `companyId` — when provided, returns only employees for that branch (Feature 21).
 *               When omitted, returns all employees (backward-compatible).
 */
export async function getEmployees(companyId) {
  let query = supabase
    .from('employees')
    .select('*')
    .order('created_at', { ascending: true });

  if (companyId) {
    // Include employees with matching company_id OR null company_id (pre-migration / CSV-imported employees).
    query = query.or(`company_id.eq.${companyId},company_id.is.null`);
  }

  const { data, error } = await query;
  if (error) { console.error('getEmployees:', error); return []; }

  return (data || []).map(dbToEmployee);
}

/**
 * Saves (upserts) a single employee. Pass the full employee object.
 * Returns the saved employee with its DB id.
 */
export async function saveEmployee(employee) {
  void employee;
  throw new Error('Employee administration has moved to the migration employee directory.');
}

/**
 * Saves the full employees array (used by CSV import which replaces/merges many at once).
 */
export async function saveEmployees(employees) {
  void employees;
  throw new Error('Employee administration has moved to the migration employee directory.');
}

/** Employee hard deletion is unavailable under the approved Phase 7 contract. */
export async function deleteEmployee(id) {
  void id;
  throw new Error('Employee hard deletion is not supported.');
}

/**
 * Retained as a hard-fail guard after lifecycle writes moved to the migration app.
 */
export async function archiveEmployee(id) {
  void id;
  throw new Error('Employee lifecycle changes have moved to the migration employee directory.');
}

// ─── EMPLOYEE JOB HISTORY ───────────────────────────────────────────────────

/**
 * Returns job history log for a specific employee.
 */
export async function getJobHistory(employeeId) {
  const { data, error } = await supabase
    .from('employee_job_history')
    .select('*')
    .eq('employee_id', employeeId)
    .order('changed_at', { ascending: false });

  if (error) { console.error('getJobHistory:', error); return []; }
  return (data || []).map(row => ({
    id:          row.id,
    employeeId:  row.employee_id,
    changedAt:   row.changed_at,
    changedBy:   row.changed_by,
    changeType:  row.change_type,
    oldValue:    row.old_value,
    newValue:    row.new_value,
    reason:      row.reason,
  }));
}

/**
 * Retained as a hard-fail guard after job-history writes moved to the migration app.
 */
export async function addJobHistoryEntry(employeeId, changeType, oldValue, newValue, reason = '') {
  void employeeId;
  void changeType;
  void oldValue;
  void newValue;
  void reason;
  throw new Error('Employee job history is written only by migration employee workflows.');
}

// ─── PAYROLL RUNS ───────────────────────────────────────────────────────────

/**
 * Returns payroll runs (with their entries) for the current user.
 * `companyId` — when provided, returns only runs for that branch (Feature 21).
 *               When omitted, returns all runs (backward-compatible).
 */
export async function getPayrolls(companyId) {
  void companyId;
  throw new Error('Payroll drafts have moved to the migration payroll workspace.');
}

/**
 * Saves (upserts) a full payroll run including all its entries.
 * Automatically records audit trail fields (runBy, totalDisbursed, employeeCount).
 */
export async function savePayroll(payroll) {
  void payroll;
  throw new Error('Payroll drafts have moved to the migration payroll workspace.');
}

/**
 * Saves an array of payroll runs.
 */
export async function savePayrolls(payrolls) {
  void payrolls;
  throw new Error('Payroll drafts have moved to the migration payroll workspace.');
}

/**
 * Deletes a payroll run and all its entries (cascade handles entries).
 */
export async function deletePayroll(id) {
  void id;
  throw new Error('Payroll drafts have moved to the migration payroll workspace.');
}

// ─── PAYSLIPS ────────────────────────────────────────────────────────────────

/**
 * Upserts one payslip snapshot row per active employee when a payroll is finalised.
 * Called by PayrollEditor when the admin clicks "Download SIF".
 */
export async function createPayslipRecords(payroll) {
  void payroll;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

// ─── EMPLOYEE DOCUMENTS ─────────────────────────────────────────────────────

/**
 * Returns all documents for a specific employee, each with a 1-hour signed URL.
 */
export async function getEmployeeDocuments(employeeId) {
  void employeeId;
  throw new Error('Employee documents have moved to the migration records and benefits workspace.');
}

/**
 * Returns ALL employee documents across all employees — no signed URLs generated
 * (used by the Document Expiry report where links aren't needed).
 */
export async function getAllEmployeeDocuments() {
  const { data, error } = await supabase
    .from('employee_documents')
    .select('*')
    .order('expiry_date', { ascending: true });
  if (error) { console.error('getAllEmployeeDocuments:', error); return []; }
  return (data || []).map(dbToDocument);
}

/**
 * Returns job history entries for ALL employees (used by the Salary Movement report).
 */
export async function getAllJobHistory() {
  const { data, error } = await supabase
    .from('employee_job_history')
    .select('*')
    .order('changed_at', { ascending: false });
  if (error) { console.error('getAllJobHistory:', error); return []; }
  return (data || []).map(row => ({
    id:         row.id,
    employeeId: row.employee_id,
    changedAt:  row.changed_at,
    changedBy:  row.changed_by,
    changeType: row.change_type,
    oldValue:   row.old_value,
    newValue:   row.new_value,
    reason:     row.reason,
  }));
}

/**
 * Uploads a file to Supabase Storage and saves its metadata to employee_documents.
 * Returns the saved document record (with signedUrl populated).
 */
export async function uploadEmployeeDocument(employeeId, file, documentType, expiryDate, notes, documentNumber) {
  void employeeId; void file; void documentType; void expiryDate; void notes; void documentNumber;
  throw new Error('Employee documents have moved to the migration records and benefits workspace.');
}

/**
 * Deletes a document from both Supabase Storage and the employee_documents table.
 */
export async function deleteEmployeeDocument(id, storagePath) {
  void id; void storagePath;
  throw new Error('Employee documents have moved to the migration records and benefits workspace.');
}

function dbToDocument(row) {
  return {
    id:              row.id,
    employeeId:      row.employee_id,
    documentType:    row.document_type,
    documentNumber:  row.document_number  || '',
    fileName:        row.file_name,
    fileSize:        row.file_size        || 0,
    storagePath:     row.storage_path     || '',
    expiryDate:      row.expiry_date      || '',
    notes:           row.notes            || '',
    uploadedAt:      row.uploaded_at,
    status:          row.status           || 'verified',
    submittedBy:     row.submitted_by     || 'hr',
    rejectionReason: row.rejection_reason || '',
    signedUrl:       '',
  };
}

/** HR verifies a pending employee-submitted document. */
export async function verifyEmployeeDocument(docId) {
  void docId;
  throw new Error('Employee documents have moved to the migration records and benefits workspace.');
}

/** HR rejects a pending employee-submitted document with a reason. */
export async function rejectEmployeeDocument(docId, reason) {
  void docId; void reason;
  throw new Error('Employee documents have moved to the migration records and benefits workspace.');
}

// ─── INSURANCE POLICIES ─────────────────────────────────────────────────────

/**
 * Returns all insurance policies for the current user.
 */
export async function getInsurancePolicies() {
  const { data, error } = await supabase
    .from('insurance_policies')
    .select('*')
    .order('created_at', { ascending: true });
  if (error) { console.error('getInsurancePolicies:', error); return []; }
  return (data || []).map(dbToInsurancePolicy);
}

/**
 * Saves (upserts) an insurance policy. Returns the saved record.
 */
export async function saveInsurancePolicy(policy) {
  void policy;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

/**
 * Deletes an insurance policy by id.
 */
export async function deleteInsurancePolicy(id) {
  void id;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

// ─── EMPLOYEE INSURANCE ──────────────────────────────────────────────────────

/**
 * Returns ALL employee_insurance records for the current admin (for dashboard alerts).
 */
export async function getAllEmployeeInsurance() {
  const { data, error } = await supabase
    .from('employee_insurance')
    .select('*')
    .order('expiry_date', { ascending: true });
  if (error) { console.error('getAllEmployeeInsurance:', error); return []; }
  return (data || []).map(dbToEmployeeInsurance);
}

/**
 * Returns the insurance record for a specific employee (or null if not assigned).
 */
export async function getEmployeeInsurance(employeeId) {
  void employeeId;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

/**
 * Saves (upserts) an employee's insurance assignment.
 * Uses UNIQUE (user_id, employee_id) — one record per employee.
 */
export async function saveEmployeeInsurance(insurance) {
  void insurance;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

// ─── INSURANCE DEPENDANTS ────────────────────────────────────────────────────

/**
 * Returns all dependants for a specific employee.
 */
export async function getInsuranceDependants(employeeId) {
  void employeeId;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

/**
 * Saves (inserts or updates) an insurance dependant.
 */
export async function saveInsuranceDependant(dependant) {
  void dependant;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

/**
 * Deletes an insurance dependant by id.
 */
export async function deleteInsuranceDependant(id) {
  void id;
  throw new Error('Insurance administration has moved to the migration records and benefits workspace.');
}

function dbToInsurancePolicy(row) {
  return {
    id:            row.id,
    insurerName:   row.insurer_name,
    policyNumber:  row.policy_number,
    tierName:      row.tier_name,
    annualPremium: parseFloat(row.annual_premium) || 0,
    renewalDate:   row.renewal_date || '',
    brokerName:    row.broker_name,
    brokerContact: row.broker_contact,
    notes:         row.notes,
    createdAt:     row.created_at,
  };
}

function dbToEmployeeInsurance(row) {
  return {
    id:            row.id,
    employeeId:    row.employee_id,
    policyId:      row.policy_id || '',
    memberId:      row.member_id,
    cardNumber:    row.card_number,
    effectiveDate: row.effective_date || '',
    expiryDate:    row.expiry_date || '',
    tierName:      row.tier_name,
    createdAt:     row.created_at,
  };
}

function dbToInsuranceDependant(row) {
  return {
    id:           row.id,
    employeeId:   row.employee_id,
    name:         row.name,
    relationship: row.relationship,
    dateOfBirth:  row.date_of_birth || '',
    cardNumber:   row.card_number,
    createdAt:    row.created_at,
  };
}

// ─── SALARY ADVANCES ─────────────────────────────────────────────────────────

function advanceWritesMoved() {
  throw new Error('Salary advance changes have moved to the migration advance workspace.');
}

/**
 * Returns advances for the current user's company.
 * Pass employeeId to filter to a single employee; omit to get all.
 */
export async function getAdvances(employeeId) {
  let q = supabase
    .from('salary_advances')
    .select('*')
    .order('created_at', { ascending: false });

  if (employeeId) q = q.eq('employee_id', employeeId);

  const { data, error } = await q;
  if (error) { console.error('getAdvances:', error); return []; }
  return (data || []).map(dbToAdvance);
}

/** Withdraw the signed-in employee's own pending advance request. */
export async function withdrawEmployeeAdvance(advanceId) {
  void advanceId;
  advanceWritesMoved();
}

/**
 * Saves (inserts or updates) a salary advance.
 * Pass the full camelCase advance object; auto-computes monthly_deduction if not set.
 * Returns the saved advance.
 */
export async function saveAdvance(advance) {
  void advance;
  advanceWritesMoved();
}

/**
 * Updates the outstanding balance on an advance after a repayment.
 * Automatically transitions status to 'settled' when balance reaches 0.
 */
export async function updateAdvanceBalance(id, newBalance) {
  void id;
  void newBalance;
  advanceWritesMoved();
}

/**
 * Returns all repayment records for a given advance.
 */
export async function getAdvanceRepayments(advanceId) {
  void advanceId;
  advanceWritesMoved();
}

/**
 * Records a repayment for an advance and updates the outstanding balance.
 */
export async function saveAdvanceRepayment(repayment) {
  void repayment;
  advanceWritesMoved();
}

function dbToAdvance(row) {
  return {
    id:                 row.id,
    employeeId:         row.employee_id,
    amount:             parseFloat(row.amount) || 0,
    disbursedDate:      row.disbursed_date || '',
    repaymentStartMonth: row.repayment_start_month ? row.repayment_start_month.slice(0, 7) : '',
    reason:             row.reason || '',
    repaymentMonths:    parseInt(row.repayment_months) || 1,
    monthlyDeduction:   parseFloat(row.monthly_deduction) || 0,
    outstandingBalance: parseFloat(row.outstanding_balance) || 0,
    status:             row.status || 'active',
    rejectionReason:    row.rejection_reason || '',
    createdAt:          row.created_at,
  };
}

// ─── NAFIS / EMIRATIZATION REPORTS ──────────────────────────────────────────

/**
 * Returns all saved Nafis compliance reports for the current user.
 */
export async function getNafisReports() {
  throw new Error('Phase 9G cutover: WPS and Nafis writes are served by FastAPI.');
}

/**
 * Saves (upserts) a Nafis compliance report snapshot for a given period.
 */
export async function saveNafisReport(report) {
  void report;
  throw new Error('Phase 9G cutover: WPS and Nafis writes are served by FastAPI.');
}

// ─── OFFBOARDING ─────────────────────────────────────────────────────────────

/** Default clearance tasks used when no custom templates exist. */
const DEFAULT_OFFBOARDING_TASKS = [
  'Return access card and office keys',
  'Revoke system access (email, apps, VPN)',
  'Return company assets (laptop, phone, ID badge)',
  'Final salary payment processed via WPS',
  'Gratuity / EOSB calculated and transferred',
  'Visa cancellation initiated with immigration authority',
  'NOC / Reference letter issued to employee',
  'Exit interview completed',
  'Knowledge transfer to replacement completed',
];

/**
 * Returns the offboarding checklist for an employee, or null if none exists yet.
 */
export async function getOffboardingChecklist(employeeId) {
  const { data, error } = await supabase
    .from('offboarding_checklists')
    .select('*')
    .eq('employee_id', employeeId)
    .maybeSingle();
  if (error) { console.error('getOffboardingChecklist:', error); return null; }
  return data ? dbToChecklist(data) : null;
}

/**
 * Creates a new offboarding checklist for an employee and seeds it with default tasks.
 * Safe to call if one already exists (upsert on user_id,employee_id).
 */
export async function createOffboardingChecklist(employeeId) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  // Upsert the checklist header
  const { data: checklist, error: clErr } = await supabase
    .from('offboarding_checklists')
    .upsert(
      { user_id: user.id, employee_id: employeeId, status: 'in_progress', visa_cancellation_status: 'not_started' },
      { onConflict: 'user_id,employee_id' }
    )
    .select()
    .single();
  if (clErr) throw clErr;

  // Seed default tasks only on first creation (no tasks yet)
  const { data: existing } = await supabase
    .from('offboarding_tasks')
    .select('id')
    .eq('checklist_id', checklist.id)
    .limit(1);

  if (!existing?.length) {
    // Use the admin's custom templates if any, otherwise fall back to hardcoded defaults
    const { data: templates } = await supabase
      .from('offboarding_task_templates')
      .select('*')
      .eq('user_id', user.id)
      .order('default_order', { ascending: true });

    const taskNames = templates?.length ? templates.map(t => t.task_name) : DEFAULT_OFFBOARDING_TASKS;
    const taskRows  = taskNames.map((name, i) => ({
      checklist_id: checklist.id,
      user_id:      user.id,
      task_name:    name,
      sort_order:   i,
    }));
    await supabase.from('offboarding_tasks').insert(taskRows);
  }

  return dbToChecklist(checklist);
}

/**
 * Returns all tasks for a checklist, ordered by sort_order.
 */
export async function getOffboardingTasks(checklistId) {
  const { data, error } = await supabase
    .from('offboarding_tasks')
    .select('*')
    .eq('checklist_id', checklistId)
    .order('sort_order', { ascending: true });
  if (error) { console.error('getOffboardingTasks:', error); return []; }
  return (data || []).map(dbToOffboardingTask);
}

/**
 * Toggles a task's completed state.
 */
export async function updateOffboardingTask(taskId, { completed, completedBy, notes }) {
  const { data, error } = await supabase
    .from('offboarding_tasks')
    .update({
      completed,
      completed_at: completed ? new Date().toISOString() : null,
      completed_by: completed ? (completedBy || '') : '',
      notes:        notes ?? '',
    })
    .eq('id', taskId)
    .select()
    .single();
  if (error) throw error;
  return dbToOffboardingTask(data);
}

/**
 * Adds a custom task to a checklist.
 */
export async function addOffboardingTask(checklistId, taskName) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  const { data: existing } = await supabase
    .from('offboarding_tasks')
    .select('sort_order')
    .eq('checklist_id', checklistId)
    .order('sort_order', { ascending: false })
    .limit(1);
  const maxOrder = existing?.[0]?.sort_order ?? -1;

  const { data, error } = await supabase
    .from('offboarding_tasks')
    .insert({ checklist_id: checklistId, user_id: user.id, task_name: taskName, sort_order: maxOrder + 1 })
    .select()
    .single();
  if (error) throw error;
  return dbToOffboardingTask(data);
}

/**
 * Deletes a task from a checklist.
 */
export async function deleteOffboardingTask(taskId) {
  const { error } = await supabase.from('offboarding_tasks').delete().eq('id', taskId);
  if (error) throw error;
}

/**
 * Saves visa cancellation status and date on the checklist header.
 */
export async function saveOffboardingVisaStatus(checklistId, { visaCancellationStatus, visaCancellationDate }) {
  const { data, error } = await supabase
    .from('offboarding_checklists')
    .update({
      visa_cancellation_status: visaCancellationStatus,
      visa_cancellation_date:   visaCancellationDate || null,
    })
    .eq('id', checklistId)
    .select()
    .single();
  if (error) throw error;
  return dbToChecklist(data);
}

/**
 * Marks the entire offboarding checklist as completed.
 */
export async function completeOffboardingChecklist(checklistId) {
  const { data, error } = await supabase
    .from('offboarding_checklists')
    .update({ status: 'completed', completed_at: new Date().toISOString() })
    .eq('id', checklistId)
    .select()
    .single();
  if (error) throw error;
  return dbToChecklist(data);
}

function dbToChecklist(row) {
  return {
    id:                     row.id,
    employeeId:             row.employee_id,
    status:                 row.status || 'in_progress',
    visaCancellationStatus: row.visa_cancellation_status || 'not_started',
    visaCancellationDate:   row.visa_cancellation_date || '',
    createdAt:              row.created_at,
    completedAt:            row.completed_at || '',
  };
}

function dbToOffboardingTask(row) {
  return {
    id:          row.id,
    checklistId: row.checklist_id,
    taskName:    row.task_name,
    completed:   row.completed || false,
    completedAt: row.completed_at || '',
    completedBy: row.completed_by || '',
    notes:       row.notes || '',
    sortOrder:   row.sort_order || 0,
    createdAt:   row.created_at,
  };
}

// ─── EMPLOYEE CONTRACTS ──────────────────────────────────────────────────────

/**
 * Returns the contract history for a specific employee, newest first.
 */
export async function getEmployeeContracts(employeeId) {
  void employeeId;
  throw new Error('Employment contracts have moved to the migration records and benefits workspace.');
}

/**
 * Saves a new contract lifecycle record (always inserts — each action is a new row).
 * action: 'new' | 'renewed' | 'converted' | 'not_renewed'
 */
export async function saveEmployeeContract(contract) {
  void contract;
  throw new Error('Employment contracts have moved to the migration records and benefits workspace.');
}

function dbToContract(row) {
  return {
    id:           row.id,
    employeeId:   row.employee_id,
    contractType: row.contract_type,
    startDate:    row.start_date || '',
    endDate:      row.end_date || '',
    renewedAt:    row.renewed_at || '',
    renewedBy:    row.renewed_by || '',
    action:       row.action || 'new',
    notes:        row.notes || '',
    createdAt:    row.created_at,
  };
}

// ─── shape converters ───────────────────────────────────────────────────────

function dbToCompany(data) {
  return {
    id:                     data.id,
    name:                   data.name,
    branchName:             data.branch_name ?? '',   // Feature 21: branch label
    molEmployerId:          data.mol_employer_id,
    defaultBankRoutingCode: data.default_bank_routing_code,
    address:                data.address,
    contactEmail:           data.contact_email,
    defaultSalaryDay:       data.default_salary_day ?? 25,
    workLocationType:       data.work_location_type ?? 'Mainland',
    freeZoneName:           data.free_zone_name ?? '',
    logoUrl:                data.logo_url ?? '',
    sector:                 data.sector ?? '',
    nafisQuotaPercent:      parseFloat(data.nafis_quota_percent) || 2,
    // Feature toggles (migration 049). Default true so pre-migration data and
    // rows without the columns still behave exactly as before.
    enableNafis:            data.enable_nafis            ?? true,
    enableStaffingRules:    data.enable_staffing_rules   ?? true,
    enableBiometricImport:  data.enable_biometric_import ?? true,
  };
}

function dbToEmployee(row) {
  return {
    // Core WPS fields
    id:               row.id,
    empNo:            row.emp_no,
    name:             row.name,
    molId:            row.mol_id,
    bankName:         row.bank_name,
    bankRoutingCode:  row.bank_routing_code,
    iban:             row.iban,
    basicSalary:      parseFloat(row.basic_salary) || 0,
    allowance:        parseFloat(row.allowance) || 0,
    active:           row.active,

    // Personal info
    personalEmail:    row.personal_email ?? '',
    workEmail:        row.work_email ?? '',
    phone:            row.phone ?? '',
    dateOfBirth:      row.date_of_birth ?? '',
    gender:           row.gender ?? '',
    maritalStatus:    row.marital_status ?? '',
    homeCountryAddress: row.home_country_address ?? '',
    photoUrl:         row.photo_url ?? '',

    // Emergency contact
    emergencyContactName:         row.emergency_contact_name ?? '',
    emergencyContactRelationship: row.emergency_contact_relationship ?? '',
    emergencyContactPhone:        row.emergency_contact_phone ?? '',

    // Job info
    jobTitle:         row.job_title ?? '',
    department:       row.department ?? '',
    reportingManagerId: row.reporting_manager_id ?? '',

    // Employment
    startDate:              row.employment_start_date ?? '',
    employmentStartDate:    row.employment_start_date ?? '',
    probationEndDate:       row.probation_end_date ?? '',
    probationExtended:      row.probation_extended ?? false,
    contractType:           row.contract_type ?? 'Unlimited',
    contractEndDate:        row.contract_end_date ?? '',
    employmentStatus:       row.employment_status ?? 'Active',
    terminationDate:        row.termination_date ?? '',
    terminationReason:      row.termination_reason ?? '',

    // Salary breakdown
    housingAllowance:       parseFloat(row.housing_allowance) || 0,
    transportAllowance:     parseFloat(row.transport_allowance) || 0,
    otherAllowances:        parseFloat(row.other_allowances) || 0,
    otherAllowancesLabel:   row.other_allowances_label ?? '',
    bankAccountHolder:      row.bank_account_holder ?? '',

    // Auth link (set when employee registers on the employee portal)
    authUserId:             row.auth_user_id || null,
    // Multi-company (Feature 21)
    companyId:              row.company_id ?? null,

    // UAE compliance
    nationality:            row.nationality ?? '',
    visaType:               row.visa_type ?? '',
    visaNumber:             row.visa_number ?? '',
    visaExpiry:             row.visa_expiry ?? '',
    passportNumber:         row.passport_number ?? '',
    passportExpiry:         row.passport_expiry ?? '',
    emiratesId:             row.emirates_id ?? '',
    emiratesIdExpiry:       row.emirates_id_expiry ?? '',
    labourCardNumber:       row.labour_card_number ?? '',
    labourCardExpiry:       row.labour_card_expiry ?? '',
    sponsoringEntity:       row.sponsoring_entity ?? '',
    workLocationType:       row.work_location_type ?? 'Mainland',
    freeZoneName:           row.free_zone_name ?? '',
    nafisRegistrationNo:    row.nafis_registration_no ?? '',
    // Professional licence (Feature 7.1)
    licenceAuthority:       row.licence_authority ?? 'None',
    licenceNumber:          row.licence_number ?? '',
    licenceExpiry:          row.licence_expiry ?? '',
  };
}

// ─── WPS TRACKING ────────────────────────────────────────────────────────────

/**
 * Updates only the WPS tracking fields on a payroll run — avoids re-saving all
 * entries (safe to call while PayrollEditor is open).
 */
export async function saveWpsTracking(payrollId, { wpsStatus, wpsSubmittedAt, wpsConfirmedAt, wpsReferenceNo }) {
  void payrollId;
  void wpsStatus;
  void wpsSubmittedAt;
  void wpsConfirmedAt;
  void wpsReferenceNo;
  throw new Error('Phase 9G cutover: WPS and Nafis writes are served by FastAPI.');
}

// ── COMPLIANCE OVERRIDES (Feature 7.1) ───────────────────────────────────────

export async function saveComplianceOverride({ overrideType, employeeIds, reason }) {
  void overrideType;
  void employeeIds;
  void reason;
  throw new Error('Phase 9G cutover: WPS and Nafis writes are served by FastAPI.');
}

// ── PAYROLL APPROVAL (Feature 17) ────────────────────────────────────────────

/** Submit a draft payroll run for approval. Locks editing until approved/rejected. */
export async function submitPayrollForApproval(payrollRunId) {
  void payrollRunId;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

/** Approve a pending-approval payroll. Enables the Generate SIF button. */
export async function approvePayroll(payrollRunId, notes = '') {
  void payrollRunId;
  void notes;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

/** Reject a pending payroll, returning it to draft with a mandatory reason. */
export async function rejectPayroll(payrollRunId, reason) {
  void payrollRunId;
  void reason;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

/** Recall a submitted payroll before it is approved (back to draft). */
export async function recallPayrollApproval(payrollRunId) {
  void payrollRunId;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

/** Return the full approval event log for a payroll run (newest first). */
export async function getPayrollApprovalLog(payrollRunId) {
  void payrollRunId;
  throw new Error('Payroll approval and payslips have moved to the migration payroll workspace.');
}

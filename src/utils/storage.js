/**
 * storage.js  –  Supabase-backed data layer for Workloop
 *
 * All functions are async and scoped to the currently logged-in user via RLS.
 * The shape of objects returned matches what the components already expect,
 * so component changes are minimal (just await the calls).
 */

import { supabase } from '../lib/supabase';

// ─── helpers ────────────────────────────────────────────────────────────────

function getUserId() {
  return supabase.auth.getUser().then(({ data }) => data?.user?.id);
}

// ─── COMPANY ────────────────────────────────────────────────────────────────

/**
 * Returns the company row for the current user, or null if not set up yet.
 */
export async function getCompany() {
  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .limit(1)
    .maybeSingle();

  if (error) { console.error('getCompany:', error); return null; }
  if (!data) return null;

  return dbToCompany(data);
}

/**
 * Upserts the company for the current user.
 */
export async function saveCompany(company) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated — please sign out and sign in again');

  const row = companyToDb(company, user.id);

  if (company.id) {
    const { error } = await supabase
      .from('companies')
      .update(row)
      .eq('id', company.id);
    if (error) { console.error('saveCompany update:', error); throw error; }
  } else {
    const { data, error } = await supabase
      .from('companies')
      .upsert({ ...row }, { onConflict: 'user_id' })
      .select()
      .single();
    if (error) { console.error('saveCompany insert:', error); throw error; }
    return data ? { ...dbToCompany(data) } : company;
  }
}

// ─── EMPLOYEES ──────────────────────────────────────────────────────────────

/**
 * Returns all employees for the current user.
 */
export async function getEmployees() {
  const { data, error } = await supabase
    .from('employees')
    .select('*')
    .order('created_at', { ascending: true });

  if (error) { console.error('getEmployees:', error); return []; }

  return (data || []).map(dbToEmployee);
}

/**
 * Saves (upserts) a single employee. Pass the full employee object.
 * Returns the saved employee with its DB id.
 */
export async function saveEmployee(employee) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const row = employeeToDb(employee, user.id);

  if (employee.id && employee.id.includes('-')) {
    // UUID — update existing
    const { data, error } = await supabase
      .from('employees')
      .update(row)
      .eq('id', employee.id)
      .select()
      .single();
    if (error) throw error;
    return dbToEmployee(data);
  } else {
    // New employee — insert
    const { id: _drop, ...insertRow } = row;
    const { data, error } = await supabase
      .from('employees')
      .insert({ ...insertRow, user_id: user.id })
      .select()
      .single();
    if (error) throw error;
    return dbToEmployee(data);
  }
}

/**
 * Saves the full employees array (used by CSV import which replaces/merges many at once).
 */
export async function saveEmployees(employees) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const existing = employees.filter(e => e.id && e.id.includes('-'));
  const newEmps  = employees.filter(e => !e.id || !e.id.includes('-'));

  if (existing.length) {
    const rows = existing.map(e => employeeToDb(e, user.id));
    const { error } = await supabase
      .from('employees')
      .upsert(rows, { onConflict: 'id' });
    if (error) throw error;
  }

  if (newEmps.length) {
    const rows = newEmps.map(e => {
      const { id: _drop, ...row } = employeeToDb(e, user.id);
      return row;
    });
    const { error } = await supabase
      .from('employees')
      .insert(rows);
    if (error) throw error;
  }
}

/**
 * Deletes a single employee by id.
 */
export async function deleteEmployee(id) {
  const { error } = await supabase
    .from('employees')
    .delete()
    .eq('id', id);
  if (error) throw error;
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
 * Appends a job history entry for an employee.
 */
export async function addJobHistoryEntry(employeeId, changeType, oldValue, newValue, reason = '') {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const { error } = await supabase
    .from('employee_job_history')
    .insert({
      user_id:     user.id,
      employee_id: employeeId,
      changed_by:  user.email || user.id,
      change_type: changeType,
      old_value:   String(oldValue ?? ''),
      new_value:   String(newValue ?? ''),
      reason:      reason || '',
    });
  if (error) throw error;
}

// ─── PAYROLL RUNS ───────────────────────────────────────────────────────────

/**
 * Returns all payroll runs (with their entries) for the current user.
 */
export async function getPayrolls() {
  const { data: runs, error: runsErr } = await supabase
    .from('payroll_runs')
    .select('*')
    .order('period', { ascending: false });

  if (runsErr) { console.error('getPayrolls runs:', runsErr); return []; }
  if (!runs?.length) return [];

  const runIds = runs.map(r => r.id);

  const { data: entries, error: entriesErr } = await supabase
    .from('payroll_entries')
    .select('*')
    .in('payroll_run_id', runIds);

  if (entriesErr) { console.error('getPayrolls entries:', entriesErr); return []; }

  return runs.map(run => ({
    id:                 run.id,
    period:             run.period,
    paymentDate:        run.payment_date,
    sequenceNo:         run.sequence_no,
    scrBankRoutingCode: run.scr_bank_routing_code,
    description:        run.description,
    status:             run.status,
    runBy:              run.run_by,
    totalDisbursed:     parseFloat(run.total_disbursed) || 0,
    employeeCount:      run.employee_count || 0,
    createdAt:          run.created_at,
    entries: (entries || [])
      .filter(e => e.payroll_run_id === run.id)
      .map(dbToEntry),
  }));
}

/**
 * Saves (upserts) a full payroll run including all its entries.
 * Automatically records audit trail fields (runBy, totalDisbursed, employeeCount).
 */
export async function savePayroll(payroll) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  // Calculate totals for audit trail
  const activeEntries = (payroll.entries || []).filter(e => !e.excluded);
  const totalDisbursed = activeEntries.reduce((s, e) => {
    return s + (parseFloat(e.basicSalary) || 0) + (parseFloat(e.variableAllowance) || 0);
  }, 0);

  const runRow = {
    id:                   payroll.id,
    user_id:              user.id,
    period:               payroll.period,
    payment_date:         payroll.paymentDate ?? '',
    sequence_no:          payroll.sequenceNo ?? '',
    scr_bank_routing_code: payroll.scrBankRoutingCode ?? '',
    description:          payroll.description ?? '',
    status:               payroll.status ?? 'draft',
    run_by:               payroll.runBy || user.email || user.id,
    total_disbursed:      totalDisbursed,
    employee_count:       activeEntries.length,
  };

  const { error: runErr } = await supabase
    .from('payroll_runs')
    .upsert(runRow, { onConflict: 'id' });
  if (runErr) throw runErr;

  // Replace all entries for this run
  if (payroll.entries?.length) {
    await supabase.from('payroll_entries').delete().eq('payroll_run_id', payroll.id);

    const entryRows = payroll.entries.map(e => entryToDb(e, payroll.id, user.id));
    const { error: entErr } = await supabase
      .from('payroll_entries')
      .insert(entryRows);
    if (entErr) throw entErr;
  }
}

/**
 * Saves an array of payroll runs.
 */
export async function savePayrolls(payrolls) {
  for (const p of payrolls) {
    await savePayroll(p);
  }
}

/**
 * Deletes a payroll run and all its entries (cascade handles entries).
 */
export async function deletePayroll(id) {
  const { error } = await supabase
    .from('payroll_runs')
    .delete()
    .eq('id', id);
  if (error) throw error;
}

// ─── PAYSLIPS ────────────────────────────────────────────────────────────────

/**
 * Upserts one payslip snapshot row per active employee when a payroll is finalised.
 * Called by PayrollEditor when the admin clicks "Download SIF".
 */
export async function createPayslipRecords(payroll) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return;

  const activeEntries = (payroll.entries || []).filter(e => !e.excluded);
  if (!activeEntries.length) return;

  const rows = activeEntries.map(entry => {
    const gross =
      (parseFloat(entry.basicSalary)       || 0) +
      (parseFloat(entry.variableAllowance) || 0) +
      (parseFloat(entry.housingAllowance)  || 0) +
      (parseFloat(entry.transportAllowance)|| 0) +
      (parseFloat(entry.bonus)             || 0) +
      (parseFloat(entry.otherPay)          || 0) +
      (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);

    const totalDeductions =
      (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0) +
      (parseFloat(entry.leaveDeduction) || 0);

    return {
      user_id:        user.id,
      payroll_run_id: payroll.id,
      employee_id:    entry.employeeId,
      period:         payroll.period,
      payment_date:   payroll.paymentDate || null,
      gross_pay:      gross,
      net_pay:        gross - totalDeductions,
      data_snapshot:  entry,
    };
  });

  const { error } = await supabase
    .from('payslips')
    .upsert(rows, { onConflict: 'payroll_run_id,employee_id' });

  if (error) console.error('createPayslipRecords:', error);
}

// ─── shape converters ───────────────────────────────────────────────────────

function dbToCompany(data) {
  return {
    id:                     data.id,
    name:                   data.name,
    molEmployerId:          data.mol_employer_id,
    defaultBankRoutingCode: data.default_bank_routing_code,
    address:                data.address,
    contactEmail:           data.contact_email,
    defaultSalaryDay:       data.default_salary_day ?? 25,
    workLocationType:       data.work_location_type ?? 'Mainland',
    freeZoneName:           data.free_zone_name ?? '',
    logoUrl:                data.logo_url ?? '',
  };
}

function companyToDb(company, userId) {
  return {
    user_id:                    userId,
    name:                       company.name ?? '',
    mol_employer_id:            company.molEmployerId ?? '',
    default_bank_routing_code:  company.defaultBankRoutingCode ?? '',
    address:                    company.address ?? '',
    contact_email:              company.contactEmail ?? '',
    default_salary_day:         company.defaultSalaryDay ?? 25,
    work_location_type:         company.workLocationType ?? 'Mainland',
    free_zone_name:             company.freeZoneName ?? '',
    logo_url:                   company.logoUrl ?? '',
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
  };
}

function employeeToDb(emp, userId) {
  return {
    id:                 emp.id,
    user_id:            userId,
    emp_no:             emp.empNo ?? '',
    name:               emp.name ?? '',
    mol_id:             emp.molId ?? '',
    bank_name:          emp.bankName ?? '',
    bank_routing_code:  emp.bankRoutingCode ?? '',
    iban:               emp.iban ?? '',
    basic_salary:       parseFloat(emp.basicSalary) || 0,
    allowance:          parseFloat(emp.allowance) || 0,
    active:             emp.active ?? true,

    // Personal info
    personal_email:     emp.personalEmail ?? '',
    work_email:         emp.workEmail ?? '',
    phone:              emp.phone ?? '',
    date_of_birth:      emp.dateOfBirth || null,
    gender:             emp.gender ?? '',
    marital_status:     emp.maritalStatus ?? '',
    home_country_address: emp.homeCountryAddress ?? '',
    photo_url:          emp.photoUrl ?? '',

    // Emergency contact
    emergency_contact_name:         emp.emergencyContactName ?? '',
    emergency_contact_relationship: emp.emergencyContactRelationship ?? '',
    emergency_contact_phone:        emp.emergencyContactPhone ?? '',

    // Job info
    job_title:          emp.jobTitle ?? '',
    department:         emp.department ?? '',
    reporting_manager_id: emp.reportingManagerId || null,

    // Employment
    employment_start_date: emp.startDate || emp.employmentStartDate || null,
    probation_end_date:    emp.probationEndDate || null,
    contract_type:         emp.contractType ?? 'Unlimited',
    contract_end_date:     emp.contractEndDate || null,
    employment_status:     emp.employmentStatus ?? 'Active',
    termination_date:      emp.terminationDate || null,
    termination_reason:    emp.terminationReason ?? '',

    // Salary breakdown
    housing_allowance:     parseFloat(emp.housingAllowance) || 0,
    transport_allowance:   parseFloat(emp.transportAllowance) || 0,
    other_allowances:      parseFloat(emp.otherAllowances) || 0,
    other_allowances_label: emp.otherAllowancesLabel ?? '',
    bank_account_holder:   emp.bankAccountHolder ?? '',

    // UAE compliance
    nationality:           emp.nationality ?? '',
    visa_type:             emp.visaType ?? '',
    visa_number:           emp.visaNumber ?? '',
    visa_expiry:           emp.visaExpiry || null,
    passport_number:       emp.passportNumber ?? '',
    passport_expiry:       emp.passportExpiry || null,
    emirates_id:           emp.emiratesId ?? '',
    emirates_id_expiry:    emp.emiratesIdExpiry || null,
    labour_card_number:    emp.labourCardNumber ?? '',
    labour_card_expiry:    emp.labourCardExpiry || null,
    sponsoring_entity:     emp.sponsoringEntity ?? '',
    work_location_type:    emp.workLocationType ?? 'Mainland',
    free_zone_name:        emp.freeZoneName ?? '',
  };
}

function dbToEntry(row) {
  return {
    id:                   row.id,
    employeeId:           row.employee_id,
    basicSalary:          parseFloat(row.basic_salary) || 0,
    housingAllowance:     parseFloat(row.housing_allowance) || 0,
    transportAllowance:   parseFloat(row.transport_allowance) || 0,
    allowance:            parseFloat(row.allowance) || 0,
    increment:            parseFloat(row.increment) || 0,
    bonus:                parseFloat(row.bonus) || 0,
    otherPay:             parseFloat(row.other_pay) || 0,
    // du_cost column repurposed to store leaveDeduction (editable leave deduction per payroll entry)
    leaveDeduction:       parseFloat(row.du_cost) || 0,
    duCost:               0,
    variableAllowance:    parseFloat(row.variable_allowance) || 0,
    additionalAllowances: row.additional_allowances ?? [],
    deductions:           row.deductions ?? [],
    excluded:             row.excluded ?? false,
  };
}

function entryToDb(entry, runId, userId) {
  return {
    payroll_run_id:        runId,
    user_id:               userId,
    employee_id:           entry.employeeId,
    basic_salary:          parseFloat(entry.basicSalary) || 0,
    housing_allowance:     parseFloat(entry.housingAllowance) || 0,
    transport_allowance:   parseFloat(entry.transportAllowance) || 0,
    allowance:             parseFloat(entry.allowance) || 0,
    increment:             parseFloat(entry.increment) || 0,
    bonus:                 parseFloat(entry.bonus) || 0,
    other_pay:             parseFloat(entry.otherPay) || 0,
    // Store leaveDeduction in du_cost column (repurposed — no schema change needed)
    du_cost:               parseFloat(entry.leaveDeduction) || 0,
    variable_allowance:    parseFloat(entry.variableAllowance) || 0,
    additional_allowances: entry.additionalAllowances ?? [],
    deductions:            entry.deductions ?? [],
    excluded:              entry.excluded ?? false,
  };
}

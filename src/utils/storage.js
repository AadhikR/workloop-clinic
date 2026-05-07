/**
 * storage.js  –  Supabase-backed data layer
 *
 * All functions are async and scoped to the currently logged-in user via RLS.
 * The shape of objects returned matches what the components already expect,
 * so component changes are minimal (just await the calls).
 */

import { supabase } from '../lib/supabase';

// ─── helpers ────────────────────────────────────────────────────────────────

function getUserId() {
  const session = supabase.auth.getSession();
  // We rely on RLS so we don't need to pass user_id manually —
  // Supabase injects auth.uid() server-side. But we still need it for inserts.
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

  // Map DB columns → app shape
  return {
    id:                     data.id,
    name:                   data.name,
    molEmployerId:          data.mol_employer_id,
    defaultBankRoutingCode: data.default_bank_routing_code,
    address:                data.address,
    contactEmail:           data.contact_email,
  };
}

/**
 * Upserts the company for the current user.
 */
export async function saveCompany(company) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:                    user.id,
    name:                       company.name ?? '',
    mol_employer_id:            company.molEmployerId ?? '',
    default_bank_routing_code:  company.defaultBankRoutingCode ?? '',
    address:                    company.address ?? '',
    contact_email:              company.contactEmail ?? '',
  };

  if (company.id) {
    // Update existing
    const { error } = await supabase
      .from('companies')
      .update(row)
      .eq('id', company.id);
    if (error) throw error;
  } else {
    // Insert new
    const { error } = await supabase
      .from('companies')
      .insert(row);
    if (error) throw error;
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

  if (employee.id && !employee.id.includes('-') === false) {
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
    const { id: _drop, ...insertRow } = row; // remove id if present
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

  // Upsert all rows — Supabase upsert on id
  const rows = employees.map(e => employeeToDb(e, user.id));

  const { error } = await supabase
    .from('employees')
    .upsert(rows, { onConflict: 'id' });

  if (error) throw error;
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
    createdAt:          run.created_at,
    entries: (entries || [])
      .filter(e => e.payroll_run_id === run.id)
      .map(dbToEntry),
  }));
}

/**
 * Saves (upserts) a full payroll run including all its entries.
 */
export async function savePayroll(payroll) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const runRow = {
    id:                   payroll.id,
    user_id:              user.id,
    period:               payroll.period,
    payment_date:         payroll.paymentDate ?? '',
    sequence_no:          payroll.sequenceNo ?? '',
    scr_bank_routing_code: payroll.scrBankRoutingCode ?? '',
    description:          payroll.description ?? '',
    status:               payroll.status ?? 'draft',
  };

  const { error: runErr } = await supabase
    .from('payroll_runs')
    .upsert(runRow, { onConflict: 'id' });
  if (runErr) throw runErr;

  // Replace all entries for this run
  if (payroll.entries?.length) {
    // Delete old entries first
    await supabase.from('payroll_entries').delete().eq('payroll_run_id', payroll.id);

    const entryRows = payroll.entries.map(e => entryToDb(e, payroll.id, user.id));
    const { error: entErr } = await supabase
      .from('payroll_entries')
      .insert(entryRows);
    if (entErr) throw entErr;
  }
}

/**
 * Saves an array of payroll runs (used when updating status on multiple runs).
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

// ─── shape converters ───────────────────────────────────────────────────────

function dbToEmployee(row) {
  return {
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
  };
}

function employeeToDb(emp, userId) {
  return {
    id:                 emp.id,          // uuid or undefined for new
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
  };
}

function dbToEntry(row) {
  return {
    id:                   row.id,
    employeeId:           row.employee_id,
    basicSalary:          parseFloat(row.basic_salary) || 0,
    allowance:            parseFloat(row.allowance) || 0,
    increment:            parseFloat(row.increment) || 0,
    bonus:                parseFloat(row.bonus) || 0,
    otherPay:             parseFloat(row.other_pay) || 0,
    variableAllowance:    parseFloat(row.variable_allowance) || 0,
    additionalAllowances: row.additional_allowances ?? [],
    deductions:           row.deductions ?? [],
    excluded:             row.excluded ?? false,
  };
}

function entryToDb(entry, runId, userId) {
  return {
    payroll_run_id:       runId,
    user_id:              userId,
    employee_id:          entry.employeeId,
    basic_salary:         parseFloat(entry.basicSalary) || 0,
    allowance:            parseFloat(entry.allowance) || 0,
    increment:            parseFloat(entry.increment) || 0,
    bonus:                parseFloat(entry.bonus) || 0,
    other_pay:            parseFloat(entry.otherPay) || 0,
    variable_allowance:   parseFloat(entry.variableAllowance) || 0,
    additional_allowances: entry.additionalAllowances ?? [],
    deductions:           entry.deductions ?? [],
    excluded:             entry.excluded ?? false,
  };
}

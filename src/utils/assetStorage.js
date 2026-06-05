/**
 * assetStorage.js — Feature 16: Asset Management
 *
 * Admin functions:
 *   getAssets()                              — all assets + current assignee
 *   saveAsset(asset)                         — create or update
 *   deleteAsset(id)                          — only if not currently assigned
 *   getAssetAssignments(filters?)            — full history, optionally filtered
 *   assignAsset(assetId, employeeId, opts)   — creates assignment + marks asset 'assigned'
 *   returnAsset(assignmentId, assetId, opts) — closes assignment + marks asset 'available'
 *
 * Employee functions (direct Supabase — uses employee self-read RLS policy):
 *   getEmployeeCurrentAssets(employeeId)     — assets assigned to this employee right now
 */
import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user ?? null;
  if (!user) throw new Error('Not authenticated');
  return user;
}

// ── Shape converters ──────────────────────────────────────────────────────────

function dbToAsset(row, activeAssignment = null) {
  return {
    id:           row.id,
    userId:       row.user_id,
    name:         row.name,
    assetCode:    row.asset_code,
    category:     row.category,
    brand:        row.brand,
    model:        row.model,
    serialNumber: row.serial_number,
    purchaseDate: row.purchase_date,
    purchaseCost: row.purchase_cost != null ? parseFloat(row.purchase_cost) : null,
    status:       row.status,
    notes:        row.notes,
    createdAt:    row.created_at,
    // Denormalised current assignment (populated by getAssets)
    currentAssignment: activeAssignment,
  };
}

function dbToAssignment(row) {
  return {
    id:                 row.id,
    userId:             row.user_id,
    assetId:            row.asset_id,
    employeeId:         row.employee_id,
    employeeName:       row.employees?.name ?? null,
    assetName:          row.assets?.name    ?? null,
    assetCode:          row.assets?.asset_code ?? null,
    assignedDate:       row.assigned_date,
    returnDate:         row.return_date,
    conditionAtHandover: row.condition_at_handover,
    conditionAtReturn:  row.condition_at_return,
    notes:              row.notes,
    assignedBy:         row.assigned_by,
    createdAt:          row.created_at,
  };
}

// ── Admin functions ───────────────────────────────────────────────────────────

/**
 * Return all assets for the admin's company, with the current assignee merged in.
 * Two queries are run in parallel: assets + all open assignments (return_date IS NULL).
 */
export async function getAssets() {
  const user = await getSessionUser();

  const [assetsRes, assignRes] = await Promise.all([
    supabase
      .from('assets')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false }),
    supabase
      .from('asset_assignments')
      .select('id, asset_id, employee_id, assigned_date, condition_at_handover, employees(name)')
      .eq('user_id', user.id)
      .is('return_date', null),
  ]);

  if (assetsRes.error) throw assetsRes.error;

  const openMap = {};
  for (const a of (assignRes.data || [])) {
    openMap[a.asset_id] = {
      assignmentId: a.id,
      employeeId:   a.employee_id,
      employeeName: a.employees?.name ?? null,
      assignedDate: a.assigned_date,
      condition:    a.condition_at_handover,
    };
  }

  return (assetsRes.data || []).map(row => dbToAsset(row, openMap[row.id] ?? null));
}

/**
 * Create or update an asset.
 * Pass `id` to update; omit (or set null) to create.
 */
export async function saveAsset(asset) {
  const user = await getSessionUser();
  const row = {
    user_id:       user.id,
    name:          asset.name,
    asset_code:    asset.assetCode    ?? '',
    category:      asset.category     ?? 'other',
    brand:         asset.brand        ?? '',
    model:         asset.model        ?? '',
    serial_number: asset.serialNumber ?? '',
    purchase_date: asset.purchaseDate || null,
    purchase_cost: asset.purchaseCost != null ? parseFloat(asset.purchaseCost) : null,
    status:        asset.status       ?? 'available',
    notes:         asset.notes        ?? '',
  };

  if (asset.id) {
    const { data, error } = await supabase
      .from('assets').update(row).eq('id', asset.id).eq('user_id', user.id)
      .select().single();
    if (error) throw error;
    return dbToAsset(data);
  } else {
    const { data, error } = await supabase
      .from('assets').insert(row).select().single();
    if (error) throw error;
    return dbToAsset(data);
  }
}

/**
 * Delete an asset. Throws if the asset currently has an open assignment.
 */
export async function deleteAsset(assetId) {
  const user = await getSessionUser();
  // Guard: check for active assignment first
  const { count } = await supabase
    .from('asset_assignments')
    .select('id', { count: 'exact', head: true })
    .eq('asset_id', assetId)
    .eq('user_id', user.id)
    .is('return_date', null);
  if (count > 0) throw new Error('Cannot delete an asset that is currently assigned. Return it first.');

  const { error } = await supabase
    .from('assets').delete().eq('id', assetId).eq('user_id', user.id);
  if (error) throw error;
}

/**
 * Return all assignment records, newest first. Joins employee and asset names.
 * Optional filters: { assetId, employeeId }
 */
export async function getAssetAssignments({ assetId, employeeId } = {}) {
  const user = await getSessionUser();
  let q = supabase
    .from('asset_assignments')
    .select('*, employees(name), assets(name, asset_code)')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false });
  if (assetId)    q = q.eq('asset_id', assetId);
  if (employeeId) q = q.eq('employee_id', employeeId);
  const { data, error } = await q;
  if (error) throw error;
  return (data || []).map(dbToAssignment);
}

/**
 * Assign an asset to an employee.
 * Creates an asset_assignments row and sets the asset status to 'assigned'.
 */
export async function assignAsset(assetId, employeeId, {
  assignedDate         = new Date().toISOString().split('T')[0],
  conditionAtHandover  = 'good',
  notes                = '',
  assignedBy           = '',
} = {}) {
  const user = await getSessionUser();

  // Insert assignment record
  const { data, error } = await supabase
    .from('asset_assignments')
    .insert({
      user_id:               user.id,
      asset_id:              assetId,
      employee_id:           employeeId,
      assigned_date:         assignedDate,
      condition_at_handover: conditionAtHandover,
      notes,
      assigned_by:           assignedBy,
    })
    .select()
    .single();
  if (error) throw error;

  // Mark asset as assigned
  await supabase.from('assets').update({ status: 'assigned' }).eq('id', assetId).eq('user_id', user.id);

  return dbToAssignment(data);
}

/**
 * Return an asset from an employee.
 * Sets return_date + condition on the assignment row; marks asset back to 'available'.
 */
export async function returnAsset(assignmentId, assetId, {
  returnDate          = new Date().toISOString().split('T')[0],
  conditionAtReturn   = 'good',
  notes               = '',
} = {}) {
  const user = await getSessionUser();

  const { error } = await supabase
    .from('asset_assignments')
    .update({
      return_date:         returnDate,
      condition_at_return: conditionAtReturn,
      notes,
    })
    .eq('id', assignmentId)
    .eq('user_id', user.id);
  if (error) throw error;

  // Mark asset as available again
  await supabase.from('assets').update({ status: 'available' }).eq('id', assetId).eq('user_id', user.id);
}

// ── Employee self-service ─────────────────────────────────────────────────────

/**
 * Return assets currently assigned to this employee (no return_date).
 * Uses the employee self-read RLS policy — no admin scope needed.
 * Safe to call from the employee portal without a session user check.
 */
export async function getEmployeeCurrentAssets(employeeId) {
  if (!employeeId) return [];
  const { data, error } = await supabase
    .from('asset_assignments')
    .select('id, asset_id, assigned_date, condition_at_handover, notes, assets(name, asset_code, category, brand, model)')
    .eq('employee_id', employeeId)
    .is('return_date', null)
    .order('assigned_date', { ascending: false });
  if (error) return [];
  return (data || []).map(row => ({
    assignmentId: row.id,
    assetId:      row.asset_id,
    assignedDate: row.assigned_date,
    condition:    row.condition_at_handover,
    notes:        row.notes,
    name:         row.assets?.name       ?? '—',
    assetCode:    row.assets?.asset_code ?? '',
    category:     row.assets?.category  ?? 'other',
    brand:        row.assets?.brand      ?? '',
    model:        row.assets?.model      ?? '',
  }));
}

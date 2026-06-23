/**
 * departmentStorage.js — Feature 3.1: Department Hierarchy
 * CRUD for the departments table. All operations scoped to auth.uid() via RLS.
 */
import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

function dbToDept(row) {
  return {
    id:             row.id,
    name:           row.name,
    parentId:       row.parent_id ?? null,
    headEmployeeId: row.head_employee_id ?? null,
    color:          row.color || '#6366f1',
    description:    row.description || '',
    sortOrder:      row.sort_order ?? 0,
    createdAt:      row.created_at,
  };
}

export async function getDepartments() {
  const { data, error } = await supabase
    .from('departments')
    .select('*')
    .order('sort_order', { ascending: true })
    .order('name', { ascending: true });
  if (error) { console.error('getDepartments:', error); return []; }
  return (data || []).map(dbToDept);
}

export async function saveDepartment(dept) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:          user.id,
    name:             dept.name.trim(),
    parent_id:        dept.parentId || null,
    head_employee_id: dept.headEmployeeId || null,
    color:            dept.color || '#6366f1',
    description:      dept.description || '',
    sort_order:       dept.sortOrder ?? 0,
  };

  if (dept.id) {
    const { data, error } = await supabase
      .from('departments')
      .update(row)
      .eq('id', dept.id)
      .eq('user_id', user.id)
      .select()
      .single();
    if (error) throw error;
    return dbToDept(data);
  } else {
    const { data, error } = await supabase
      .from('departments')
      .insert(row)
      .select()
      .single();
    if (error) throw error;
    return dbToDept(data);
  }
}

export async function deleteDepartment(id) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const { error } = await supabase
    .from('departments')
    .delete()
    .eq('id', id)
    .eq('user_id', user.id);
  if (error) throw error;
}

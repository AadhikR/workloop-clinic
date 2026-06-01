/**
 * db.js — Supabase admin client for test setup/teardown.
 * Uses the service role key so it bypasses RLS.
 * Only used in Node.js test scripts — never in the browser.
 */
import { createClient } from '@supabase/supabase-js';

export function adminClient() {
  const url  = process.env.VITE_SUPABASE_URL;
  const key  = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Missing VITE_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.test');
  return createClient(url, key, { auth: { autoRefreshToken: false, persistSession: false } });
}

/** Delete all rows in a table matching a filter — used in teardown. */
export async function deleteWhere(db, table, column, value) {
  const { error } = await db.from(table).delete().eq(column, value);
  if (error) console.warn(`cleanup ${table}:`, error.message);
}

/** Upsert a single row and return it. */
export async function upsertRow(db, table, row, conflict) {
  const { data, error } = await db.from(table).upsert(row, { onConflict: conflict }).select().single();
  if (error) throw new Error(`upsertRow ${table}: ${error.message}`);
  return data;
}

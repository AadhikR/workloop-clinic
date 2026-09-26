-- 043_employee_portal_fixes.sql
-- Consolidated fix for three employee portal issues:
--   1. Document upload fails ("new row violates row-level security policy")
--   2. Cannot download/view verified documents
--   3. Cannot edit profile contact info
--
-- Run in: Supabase Dashboard → SQL Editor → New Query
-- This is idempotent — safe to run multiple times.

-- ═══════════════════════════════════════════════════════════════
-- FIX 1 & 2: Storage policies for employee document upload/download
-- ═══════════════════════════════════════════════════════════════

-- Allow employees to UPLOAD files into their folder: {admin_user_id}/{employee_id}/...
DROP POLICY IF EXISTS "employee_documents_employee_upload" ON storage.objects;
CREATE POLICY "employee_documents_employee_upload"
  ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'employee-documents'
    AND EXISTS (
      SELECT 1 FROM public.employees e
       WHERE e.auth_user_id = auth.uid()
         AND e.user_id::text  = (storage.foldername(name))[1]
         AND e.id::text       = (storage.foldername(name))[2]
    )
  );

-- Allow employees to READ (download / generate signed URLs) their own files
DROP POLICY IF EXISTS "employee_documents_employee_read_own" ON storage.objects;
CREATE POLICY "employee_documents_employee_read_own"
  ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'employee-documents'
    AND EXISTS (
      SELECT 1 FROM public.employees e
       WHERE e.auth_user_id = auth.uid()
         AND e.user_id::text  = (storage.foldername(name))[1]
         AND e.id::text       = (storage.foldername(name))[2]
    )
  );

-- ═══════════════════════════════════════════════════════════════
-- FIX 3: Employee can update own contact fields via Profile tab
-- ═══════════════════════════════════════════════════════════════

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'employees_self_update_contact' AND tablename = 'employees') THEN
    CREATE POLICY "employees_self_update_contact"
      ON employees
      FOR UPDATE
      TO authenticated
      USING (auth_user_id = auth.uid())
      WITH CHECK (auth_user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- After running, also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- ═══════════════════════════════════════════════════════════════

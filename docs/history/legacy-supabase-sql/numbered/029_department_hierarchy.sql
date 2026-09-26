-- Feature 3.1: Department Hierarchy & Org Tree
-- Formal department registry with optional parent-child nesting and dept head.

CREATE TABLE IF NOT EXISTS departments (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  parent_id        UUID REFERENCES departments(id) ON DELETE SET NULL,
  head_employee_id UUID REFERENCES employees(id) ON DELETE SET NULL,
  color            TEXT NOT NULL DEFAULT '#6366f1',
  description      TEXT NOT NULL DEFAULT '',
  sort_order       INT  NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, name)
);

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE departments TO authenticated;

DROP POLICY IF EXISTS "departments_admin" ON departments;
CREATE POLICY "departments_admin" ON departments
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

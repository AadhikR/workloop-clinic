-- 038_appraisal_manager_update.sql
-- Allows managers to UPDATE their direct reports' appraisals (overall_rating, status, reviewed_at).
-- Required for managerRateSection() to transition appraisal status from 'pending' to 'reviewed'
-- after the manager has rated all sections.

CREATE POLICY appraisals_manager_update ON appraisals
  FOR UPDATE USING (
    employee_id IN (
      SELECT id FROM employees
      WHERE reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  ) WITH CHECK (
    employee_id IN (
      SELECT id FROM employees
      WHERE reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

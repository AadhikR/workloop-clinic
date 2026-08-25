-- 050_advance_repayment_scheduling.sql
-- Month-specific salary-advance scheduling and idempotent payroll repayments.

ALTER TABLE salary_advances
  ADD COLUMN IF NOT EXISTS repayment_start_month DATE;

UPDATE salary_advances
SET repayment_start_month = date_trunc('month', COALESCE(disbursed_date, created_at::date))::date
WHERE repayment_start_month IS NULL;

ALTER TABLE salary_advances
  ALTER COLUMN repayment_start_month SET DEFAULT date_trunc('month', CURRENT_DATE)::date;

CREATE UNIQUE INDEX IF NOT EXISTS uq_advance_repayment_payroll
  ON advance_repayments (advance_id, payroll_run_id)
  WHERE payroll_run_id IS NOT NULL;

CREATE OR REPLACE FUNCTION record_advance_repayment(
  p_advance_id UUID,
  p_payroll_run_id UUID,
  p_amount NUMERIC,
  p_paid_date DATE DEFAULT CURRENT_DATE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_advance salary_advances%ROWTYPE;
  v_payroll payroll_runs%ROWTYPE;
  v_amount NUMERIC;
  v_new_balance NUMERIC;
  v_new_status TEXT;
  v_repayment_id UUID;
BEGIN
  SELECT * INTO v_advance FROM salary_advances WHERE id = p_advance_id FOR UPDATE;
  IF v_advance.id IS NULL OR v_advance.user_id <> auth.uid() THEN
    RAISE EXCEPTION 'Advance not found or access denied';
  END IF;
  IF v_advance.status <> 'active' OR v_advance.outstanding_balance <= 0 THEN
    RAISE EXCEPTION 'Advance is not active';
  END IF;

  IF p_payroll_run_id IS NOT NULL THEN
    SELECT * INTO v_payroll FROM payroll_runs WHERE id = p_payroll_run_id;
    IF v_payroll.id IS NULL OR v_payroll.user_id <> auth.uid() THEN
      RAISE EXCEPTION 'Payroll run not found or access denied';
    END IF;
    SELECT id INTO v_repayment_id
    FROM advance_repayments
    WHERE advance_id = p_advance_id AND payroll_run_id = p_payroll_run_id;
    IF v_repayment_id IS NOT NULL THEN
      RETURN jsonb_build_object(
        'repaymentId', v_repayment_id,
        'newBalance', v_advance.outstanding_balance,
        'newStatus', v_advance.status,
        'alreadyRecorded', true
      );
    END IF;
  END IF;

  v_amount := LEAST(GREATEST(COALESCE(p_amount, 0), 0), v_advance.outstanding_balance);
  IF v_amount <= 0 THEN RAISE EXCEPTION 'Repayment amount must be greater than zero'; END IF;

  INSERT INTO advance_repayments (advance_id, payroll_run_id, amount, paid_date)
  VALUES (p_advance_id, p_payroll_run_id, v_amount, p_paid_date)
  RETURNING id INTO v_repayment_id;

  UPDATE salary_advances
  SET outstanding_balance = GREATEST(0, outstanding_balance - v_amount),
      status = CASE WHEN GREATEST(0, outstanding_balance - v_amount) <= 0 THEN 'settled' ELSE 'active' END
  WHERE id = p_advance_id
  RETURNING outstanding_balance, status INTO v_new_balance, v_new_status;

  RETURN jsonb_build_object(
    'repaymentId', v_repayment_id,
    'newBalance', v_new_balance,
    'newStatus', v_new_status,
    'alreadyRecorded', false
  );
END;
$$;

REVOKE ALL ON FUNCTION record_advance_repayment(UUID, UUID, NUMERIC, DATE) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION record_advance_repayment(UUID, UUID, NUMERIC, DATE) TO authenticated;

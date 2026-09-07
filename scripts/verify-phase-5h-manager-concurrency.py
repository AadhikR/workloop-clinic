from __future__ import annotations

import os
import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from sqlalchemy import create_engine, text

BASE = runpy.run_path(str(Path(__file__).with_name("verify-phase-5e-rls.py")))
c = BASE["c"]
build_rows = BASE["build_rows"]
apply_rows = BASE["apply_rows"]
clean = BASE["clean"]
validate = BASE["validate"]
connect_as = BASE["connect_as"]
human_context = BASE["human_context"]
principal_for = BASE["principal_for"]
scalar = BASE["scalar"]


def reassign_report(report_id: object, new_manager_id: object) -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE employees SET reporting_manager_id=:manager WHERE id=:report"
                ),
                {"manager": new_manager_id, "report": report_id},
            )
    finally:
        engine.dispose()


def execute_shift_swap(swap_id: object) -> str:
    runtime = connect_as("workloop_runtime")
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT public.admin_execute_shift_swap(%s,%s)",
                (swap_id, principal_for("hr.admin@horizon.test").app_user_id),
            )
        return "accepted"
    except psycopg.Error as error:
        return str(error)
    finally:
        runtime.close()


def revoke_delegation(delegation_id: object) -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE leave_approval_delegates SET to_date=DATE '2026-08-14' WHERE id=:id"),
                {"id": delegation_id},
            )
    finally:
        engine.dispose()


def execute_repayment(advance_id: object, payroll_run_id: object, key: uuid.UUID) -> str:
    runtime = connect_as("workloop_runtime")
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT public.record_advance_repayment(%s,%s,%s,1.00,DATE '2026-09-06')",
                (advance_id, payroll_run_id, key),
            )
        return "accepted"
    except psycopg.Error as error:
        return str(error)
    finally:
        runtime.close()


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    repayment_key = uuid.uuid4()
    aisha = principal_for("aisha.manager@horizon.test")
    ravi = principal_for("ravi.employee@horizon.test")
    maria = principal_for("maria.employee@horizon.test")
    runtime = connect_as("workloop_runtime")
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            connection.execute(
                text("UPDATE user_profiles SET role='manager' WHERE app_user_id=:user"),
                {"user": ravi.app_user_id},
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            with human_context(runtime, "aisha.manager@horizon.test") as cursor:
                cursor.execute(
                    "SELECT public.lock_authorized_employee_relationships(%s::uuid[])",
                    ([maria.employee_id],),
                )
                future = executor.submit(
                    reassign_report, maria.employee_id, ravi.employee_id
                )
                try:
                    future.result(timeout=0.5)
                except TimeoutError:
                    pass
                else:
                    raise AssertionError(
                        "manager reassignment bypassed the authorization relationship lock"
                    )
            future.result(timeout=5)

        with human_context(runtime, "aisha.manager@horizon.test") as cursor:
            assert scalar(
                cursor,
                "SELECT count(*) FROM employees WHERE id=%s "
                "AND reporting_manager_id=%s",
                (maria.employee_id, aisha.employee_id),
            ) == 0
        with human_context(
            runtime,
            "ravi.employee@horizon.test",
            overrides={"workloop.role": "manager"},
        ) as cursor:
            assert scalar(
                cursor,
                "SELECT count(*) FROM employees WHERE id=%s "
                "AND reporting_manager_id=%s",
                (maria.employee_id, ravi.employee_id),
            ) == 1

        delegation_id = c.derive(
            "leave_approval_delegates", c.HORIZON, "dubai", "H-DXB-001", "active"
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            with human_context(
                runtime,
                "fatima.employee@horizon.test",
                overrides={"workloop.business_date": "2026-08-15"},
            ) as cursor:
                cursor.execute(
                    "SELECT public.lock_authorized_employee_relationships(%s::uuid[])",
                    ([ravi.employee_id],),
                )
                future = executor.submit(revoke_delegation, delegation_id)
                try:
                    future.result(timeout=0.5)
                except TimeoutError:
                    pass
                else:
                    raise AssertionError("delegation revocation bypassed the relationship lock")
            future.result(timeout=5)
        try:
            with human_context(
                runtime,
                "fatima.employee@horizon.test",
                overrides={"workloop.business_date": "2026-08-15"},
            ) as cursor:
                cursor.execute(
                    "SELECT public.lock_authorized_employee_relationships(%s::uuid[])",
                    ([ravi.employee_id],),
                )
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("revoked delegate retained relationship-lock authority")

        with engine.connect() as connection:
            swap = connection.execute(
                text(
                    "SELECT id,target_employee_id FROM shift_swap_requests "
                    "WHERE company_id=:company AND branch_id=:branch "
                    "AND status='pending' AND requester_employee_id<>target_employee_id LIMIT 1"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
            ).one()
            before_swap = connection.execute(
                text(
                    "SELECT status,admin_approved_at,admin_approved_by_app_user_id "
                    "FROM shift_swap_requests WHERE id=:id"
                ),
                {"id": swap.id},
            ).one()
            before_rosters = connection.execute(
                text(
                    "SELECT md5(string_agg(id::text||':'||employee_id::text,',' ORDER BY id)) "
                    "FROM roster_assignments WHERE company_id=:company AND branch_id=:branch"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
            ).scalar_one()
            connection.execute(
                text("SELECT id FROM employees WHERE id=:id FOR UPDATE"),
                {"id": swap.target_employee_id},
            )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(execute_shift_swap, swap.id)
                try:
                    future.result(timeout=0.5)
                except TimeoutError:
                    pass
                else:
                    raise AssertionError(
                        "shift swap did not wait for the employee eligibility lock"
                    )
                connection.execute(
                    text(
                        "UPDATE employees SET active=false,employment_status='Terminated' "
                        "WHERE id=:id"
                    ),
                    {"id": swap.target_employee_id},
                )
                connection.commit()
                assert "shift_swap_employee_ineligible" in future.result(timeout=5)
        with engine.connect() as connection:
            after_swap = connection.execute(
                text(
                    "SELECT status,admin_approved_at,admin_approved_by_app_user_id "
                    "FROM shift_swap_requests WHERE id=:id"
                ),
                {"id": swap.id},
            ).one()
            after_rosters = connection.execute(
                text(
                    "SELECT md5(string_agg(id::text||':'||employee_id::text,',' ORDER BY id)) "
                    "FROM roster_assignments WHERE company_id=:company AND branch_id=:branch"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
            ).scalar_one()
        assert after_swap == before_swap
        assert after_rosters == before_rosters

        with engine.connect() as connection:
            advance_id, payroll_run_id = connection.execute(
                text(
                    "SELECT advance.id,run.id FROM salary_advances AS advance "
                    "JOIN payroll_runs AS run ON run.company_id=advance.company_id "
                    "AND run.branch_id=advance.branch_id "
                    "WHERE advance.company_id=:company AND advance.branch_id=:branch "
                    "AND advance.status='active' AND advance.outstanding_balance>=1 "
                    "AND NOT EXISTS (SELECT 1 FROM advance_repayments AS repayment "
                    "WHERE repayment.advance_id=advance.id AND repayment.payroll_run_id=run.id) "
                    "ORDER BY advance.id,run.id LIMIT 1"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
            ).one()
            connection.execute(
                text("SELECT id FROM payroll_runs WHERE id=:id FOR UPDATE"),
                {"id": payroll_run_id},
            )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    execute_repayment, advance_id, payroll_run_id, repayment_key
                )
                try:
                    future.result(timeout=0.5)
                except TimeoutError:
                    pass
                else:
                    raise AssertionError("advance repayment bypassed the payroll-run lock")
                connection.commit()
                assert future.result(timeout=5) == "accepted"
    finally:
        runtime.close()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE employees SET reporting_manager_id=:manager WHERE id=:report"
                ),
                {"manager": aisha.employee_id, "report": maria.employee_id},
            )
            connection.execute(
                text("UPDATE user_profiles SET role='employee' WHERE app_user_id=:user"),
                {"user": ravi.app_user_id},
            )
            connection.execute(
                text("DELETE FROM advance_repayments WHERE idempotency_key=:key"),
                {"key": repayment_key},
            )
            connection.execute(
                text(
                    "UPDATE employees SET active=true,employment_status='Active' "
                    "WHERE id IN (SELECT target_employee_id FROM shift_swap_requests "
                    "WHERE company_id=:company AND branch_id=:branch)"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
            )
            clean(connection, rows)
        engine.dispose()
    print("Phase 5H relationship, shift-swap, and repayment races passed.")


if __name__ == "__main__":
    main()

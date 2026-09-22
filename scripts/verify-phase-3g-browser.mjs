import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const docker = process.env.DOCKER
  || (process.platform === 'win32'
    && existsSync('C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe')
    ? 'C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe'
    : 'docker')
const compose = [
  'compose',
  ...(process.env.WORKLOOP_COMPOSE_PROJECT_NAME
    ? ['--project-name', process.env.WORKLOOP_COMPOSE_PROJECT_NAME]
    : []),
  ...(process.env.WORKLOOP_COMPOSE_FILES
    ? process.env.WORKLOOP_COMPOSE_FILES.split(';').flatMap((file) => ['--file', file])
    : []),
]
const kcadmConfig = '/tmp/workloop-phase-3g-kcadm.config'
const keycloakBaseUrl = (process.env.WORKLOOP_KEYCLOAK_BASE_URL
  || 'http://127.0.0.1:8080').replace(/\/$/, '')
const apiBaseUrl = (process.env.WORKLOOP_API_BASE_URL
  || 'http://127.0.0.1:8000').replace(/\/$/, '')
const issuer = `${keycloakBaseUrl}/realms/workloop-dev`
const keycloakOrigin = new URL(keycloakBaseUrl).origin
const apiOrigin = new URL(apiBaseUrl).origin
const personas = [
  {
    appUserId: '00000000-0000-0000-0000-000000000071',
    employeeId: null,
    role: 'admin',
    userName: 'phase-3g-admin-test',
  },
  {
    appUserId: '00000000-0000-4000-8000-000000000072',
    employeeId: '00000000-0000-4000-8000-000000000072',
    role: 'manager',
    userName: 'phase-3g-manager-test',
  },
  {
    appUserId: '00000000-0000-4000-8000-000000000073',
    employeeId: '00000000-0000-4000-8000-000000000073',
    role: 'employee',
    userName: 'phase-3g-employee-test',
  },
]
const companyId = '00000000-0000-0000-0000-000000000070'
const branchId = '00000000-0000-4000-8000-000000000071'
const alternateBranchId = '00000000-0000-4000-8000-000000000074'
const createdRows = {
  appUsers: [],
  branches: [],
  company: false,
  departments: [],
  employees: [],
  jobHistory: [],
  profiles: [],
  staffingRules: [],
}
const browserHistoryId = '00000000-0000-4000-8000-000000000075'
const browserDepartmentId = '00000000-0000-4000-8000-000000000076'
const browserLeaveSettingsId = '00000000-0000-4000-8000-000000000077'
const browserLeaveTypeId = '00000000-0000-4000-8000-000000000078'
const browserLeaveRequestId = '00000000-0000-4000-8000-000000000079'
const browserAutoLeaveTypeId = '00000000-0000-4000-8000-000000000080'
const browserApprovalLeaveTypeId = '00000000-0000-4000-8000-000000000081'
const browserAdminApprovalRequestId = '00000000-0000-4000-8000-000000000082'
const browserManagerApprovalRequestId = '00000000-0000-4000-8000-000000000083'
const browserPayrollRunId = '00000000-0000-4000-8000-000000000090'
const browserPayrollEntryId = '00000000-0000-4000-8000-000000000091'
const browserPayslipId = '00000000-0000-4000-8000-000000000092'
const browserShiftId = '00000000-0000-4000-8000-000000000093'
const browserManagerRosterId = '00000000-0000-4000-8000-000000000094'
const browserEmployeeRosterId = '00000000-0000-4000-8000-000000000095'
const browserRosterMonthId = '00000000-0000-4000-8000-000000000096'
const browserRosterVersionId = '00000000-0000-4000-8000-000000000097'
const browserRosterSourceVersion = `sha256:${'b'.repeat(64)}`
const createdIdentityIds = []
const financialJourney = {
  advanceId: null,
  expenseId: null,
}
const phase10Journey = {
  swapId: null,
}
let activeStage = 'startup'

function stage(name) {
  activeStage = name
}

function run(args, { input = undefined, output = false } = {}) {
  const result = spawnSync(docker, [...compose, ...args], {
    cwd: root,
    encoding: 'utf8',
    input,
    maxBuffer: 10 * 1024 * 1024,
    windowsHide: true,
  })
  if (result.status !== 0) {
    const detail = result.stderr.trim() || result.stdout.trim() || `exit ${result.status}`
    throw new Error(`local synthetic fixture operation failed: ${detail}`)
  }
  return output ? result.stdout.trim() : ''
}

function kcadm(args, options = {}) {
  return run([
    'exec', '-T', 'keycloak', '/opt/keycloak/bin/kcadm.sh',
    ...args, '--config', kcadmConfig,
  ], options)
}

function psql(sql, variables = {}) {
  const variableArguments = Object.entries(variables)
    .flatMap(([name, value]) => ['--set', `${name}=${value}`])
  return run([
    'exec', '-T', 'postgres', 'psql', '--username', 'postgres', '--dbname', 'workloop',
    '--tuples-only', '--no-align', '--set', 'ON_ERROR_STOP=1', ...variableArguments,
  ], { input: sql, output: true })
}

function authenticateAdministrator() {
  run([
    'exec', '-T', 'keycloak', 'sh', '-c',
    `/opt/keycloak/bin/kcadm.sh config credentials --config ${kcadmConfig} `
      + '--server http://127.0.0.1:8080 --realm master '
      + '--user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" '
      + '>/dev/null 2>&1',
  ])
}

function findUsers(userName) {
  const result = kcadm(
    ['get', 'users', '-r', 'workloop-dev', '-q', `username=${userName}`],
    { output: true },
  )
  return JSON.parse(result)
}

function setPassword(userId, password) {
  run([
    'exec', '-T', 'keycloak', 'sh', '-c',
    `IFS= read -r password; /opt/keycloak/bin/kcadm.sh set-password --config ${kcadmConfig} `
      + `-r workloop-dev --userid ${userId} --new-password "$password" --temporary=false`,
  ], { input: password })
}

function createFixtures() {
  stage('synthetic Keycloak administrator authentication')
  authenticateAdministrator()
  stage('synthetic Keycloak identity preflight')
  for (const persona of personas) {
    assert.deepEqual(findUsers(persona.userName), [])
  }
  stage('synthetic PostgreSQL identity preflight')
  assert.equal(
    psql(
      "SELECT count(*) FROM companies WHERE id = :'company_id' "
        + "OR id IN (:'app_1', :'app_2', :'app_3')",
      {
        app_1: personas[0].appUserId,
        app_2: personas[1].appUserId,
        app_3: personas[2].appUserId,
        company_id: companyId,
      },
    ),
    '0',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM app_users WHERE id IN (:'app_1', :'app_2', :'app_3')",
      {
        app_1: personas[0].appUserId,
        app_2: personas[1].appUserId,
        app_3: personas[2].appUserId,
      },
    ),
    '0',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM employees WHERE id IN (:'employee_1', :'employee_2')",
      {
        employee_1: personas[1].employeeId,
        employee_2: personas[2].employeeId,
      },
    ),
    '0',
  )
  assert.equal(
    psql("SELECT count(*) FROM departments WHERE id = :'department_id'", {
      department_id: browserDepartmentId,
    }),
    '0',
  )

  for (const persona of personas) {
    stage(`synthetic ${persona.role} identity creation`)
    persona.password = randomBytes(32).toString('base64url')
    persona.identityId = kcadm([
      'create', 'users', '-r', 'workloop-dev',
      '-s', `username=${persona.userName}`,
      '-s', 'firstName=Phase',
      '-s', `lastName=${persona.role}`,
      '-s', `email=${persona.userName}@example.test`,
      '-s', 'enabled=true',
      '-i',
    ], { output: true })
    if (!persona.identityId) {
      const matches = findUsers(persona.userName)
      createdIdentityIds.push(...matches.map(({ id }) => id))
    }
    assert.ok(persona.identityId)
    createdIdentityIds.push(persona.identityId)
    setPassword(persona.identityId, persona.password)
  }

  stage('synthetic organization row creation')
  psql(
    "INSERT INTO companies (id,name,sector,enable_nafis,nafis_quota_percent) "
      + "VALUES (:'company_id','Phase 9H synthetic clinic','Healthcare',true,2.00)",
    { company_id: companyId },
  )
  createdRows.company = true
  for (const [createdBranchId, name] of [
    [branchId, 'Phase 3G main'],
    [alternateBranchId, 'Phase 3G alternate'],
  ]) {
    psql(
      "INSERT INTO branches (id,company_id,name,mol_employer_id,default_bank_routing_code) "
        + "VALUES (:'branch_id',:'company_id',:'name','999000001','999000001')",
      { branch_id: createdBranchId, company_id: companyId, name },
    )
    createdRows.branches.push(createdBranchId)
  }
  psql(
    "INSERT INTO departments (id, company_id, branch_id, name) "
      + "VALUES (:'department_id', :'company_id', :'branch_id', 'Clinical')",
    { department_id: browserDepartmentId, company_id: companyId, branch_id: branchId },
  )
  createdRows.departments.push(browserDepartmentId)
  for (const persona of personas.filter(({ employeeId }) => employeeId)) {
    stage(`synthetic ${persona.role} employee creation`)
    psql(
      "INSERT INTO employees (id,company_id,branch_id,emp_no,name,mol_id,work_email, "
        + "job_title,department,reporting_manager_id,basic_salary,housing_allowance, "
        + "transport_allowance,allowance,bank_routing_code,iban,nationality, "
        + "nafis_registration_no,employment_start_date) "
        + "VALUES (:'employee_id', :'company_id', :'branch_id', :'emp_no', :'name', "
        + ":'mol_id', :'work_email', :'job_title', 'Clinical', "
        + "NULLIF(:'manager_id', '')::uuid, 10000.00,2000.00,500.00,250.00, "
        + "'999000001',:'iban','United Arab Emirates',:'nafis_number','2025-01-01')",
      {
        branch_id: branchId,
        company_id: companyId,
        employee_id: persona.employeeId,
        emp_no: `E-${persona.role}`,
        job_title: persona.role === 'manager' ? 'Clinical manager' : 'Registered nurse',
        manager_id: persona.role === 'employee' ? personas[1].employeeId : '',
        mol_id: `MOL-${persona.role}`,
        name: `Phase ${persona.role}`,
        iban: `AE07033123456789012345${persona.role === 'manager' ? '1' : '2'}`,
        nafis_number: `NAFIS-${persona.role}`,
        work_email: `${persona.role}@example.test`,
      },
    )
    createdRows.employees.push(persona.employeeId)
  }
  for (const persona of personas) {
    stage(`synthetic ${persona.role} application profile creation`)
    psql(
      "INSERT INTO app_users (id, identity_issuer, identity_subject, status) "
        + "VALUES (:'app_user_id', :'issuer', :'subject', 'active')",
      { app_user_id: persona.appUserId, issuer, subject: persona.identityId },
    )
    createdRows.appUsers.push(persona.appUserId)
    psql(
      "INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) "
        + "VALUES (:'app_user_id', :'company_id', NULLIF(:'employee_id', '')::uuid, :'role')",
      {
        app_user_id: persona.appUserId,
        company_id: companyId,
        employee_id: persona.employeeId ?? '',
        role: persona.role,
      },
    )
    createdRows.profiles.push(persona.appUserId)
  }
  stage('synthetic Phase 10 attendance and roster fixture creation')
  psql(
    "INSERT INTO attendance_settings (company_id,branch_id) "
      + "VALUES (:'company_id',:'branch_id')",
    { company_id: companyId, branch_id: branchId },
  )
  psql(
    "INSERT INTO shifts (id,company_id,branch_id,name,shift_type,start_time,end_time,"
      + "break_minutes,expected_hours,color,code,shift_category,min_staff) VALUES "
      + "(:'id',:'company_id',:'branch_id','Phase 10J day','fixed','08:00','17:00',"
      + "60,8.00,'#3366AA','P10J-DAY','morning',1)",
    { id: browserShiftId, company_id: companyId, branch_id: branchId },
  )
  for (const [id, employeeId] of [
    ['00000000-0000-4000-8000-000000000098', personas[1].employeeId],
    ['00000000-0000-4000-8000-000000000099', personas[2].employeeId],
  ]) {
    psql(
      "INSERT INTO shift_assignments (id,company_id,branch_id,employee_id,shift_id,effective_from) "
        + "VALUES (:'id',:'company_id',:'branch_id',:'employee_id',:'shift_id','2026-01-01')",
      { id, company_id: companyId, branch_id: branchId, employee_id: employeeId, shift_id: browserShiftId },
    )
  }
  for (const [id, employeeId, date, note] of [
    [browserManagerRosterId, personas[1].employeeId, '2026-11-04', 'Phase 10J manager'],
    [browserEmployeeRosterId, personas[2].employeeId, '2026-11-03', 'Phase 10J employee'],
  ]) {
    psql(
      "INSERT INTO roster_assignments "
        + "(id,company_id,branch_id,employee_id,shift_id,date,published,notes,planned_hours,version) "
        + "VALUES (:'id',:'company_id',:'branch_id',:'employee_id',:'shift_id',:'date',true,:'note',8.00,2)",
      { id, company_id: companyId, branch_id: branchId, employee_id: employeeId, shift_id: browserShiftId, date, note },
    )
  }
  psql(
    "INSERT INTO roster_months (id,company_id,branch_id,period) "
      + "VALUES (:'id',:'company_id',:'branch_id','2026-11')",
    { id: browserRosterMonthId, company_id: companyId, branch_id: branchId },
  )
  psql(
    "INSERT INTO roster_publication_versions "
      + "(id,company_id,branch_id,roster_month_id,period,version,kind,source_version,"
      + "source_canonical,source_payload,affected_row_digest,record_count,actor_app_user_id,reason) "
      + "VALUES (:'id',:'company_id',:'branch_id',:'month_id','2026-11',1,'publication',"
      + ":'source_version','{}','{}'::jsonb,:'affected_digest',2,:'actor','')",
    {
      id: browserRosterVersionId,
      company_id: companyId,
      branch_id: branchId,
      month_id: browserRosterMonthId,
      source_version: browserRosterSourceVersion,
      affected_digest: `sha256:${'c'.repeat(64)}`,
      actor: personas[0].appUserId,
    },
  )
  for (const [assignmentId, employeeId, employeeName, date, note] of [
    [browserManagerRosterId, personas[1].employeeId, 'Phase manager', '2026-11-04', 'Phase 10J manager'],
    [browserEmployeeRosterId, personas[2].employeeId, 'Phase employee', '2026-11-03', 'Phase 10J employee'],
  ]) {
    psql(
      "INSERT INTO roster_publication_memberships "
        + "(company_id,branch_id,publication_version_id,source_assignment_id,"
        + "source_assignment_version,employee_id,employee_name,department,shift_id,shift_name,"
        + "shift_code,shift_category,date,planned_hours,notes,source_payload) VALUES "
        + "(:'company_id',:'branch_id',:'version_id',:'assignment_id',2,:'employee_id',"
        + ":'employee_name','Clinical',:'shift_id','Phase 10J day','P10J-DAY','morning',"
        + ":'date',8.00,:'note',jsonb_build_object('date',:'date','employeeId',:'employee_id',"
        + "'rosterAssignmentId',:'assignment_id','shiftId',:'shift_id','plannedHours','8.00'))",
      {
        company_id: companyId,
        branch_id: branchId,
        version_id: browserRosterVersionId,
        assignment_id: assignmentId,
        employee_id: employeeId,
        employee_name: employeeName,
        shift_id: browserShiftId,
        date,
        note,
      },
    )
  }
  psql(
    "UPDATE roster_months SET status='published',version=1,current_version_id=:'version_id',"
      + "source_version=:'source_version',published_at=statement_timestamp(),"
      + "published_by_app_user_id=:'actor' WHERE id=:'id'",
    {
      version_id: browserRosterVersionId,
      source_version: browserRosterSourceVersion,
      actor: personas[0].appUserId,
      id: browserRosterMonthId,
    },
  )
  psql(
    "INSERT INTO employee_job_history "
      + "(id, company_id, branch_id, employee_id, changed_at, change_type, old_value, "
      + "new_value, reason) VALUES (:'id', :'company_id', :'branch_id', :'employee_id', "
      + "'2026-09-10T08:00:00Z', 'title_change', 'Assistant nurse', "
      + "'Registered nurse', 'Synthetic browser proof')",
    {
      id: browserHistoryId,
      company_id: companyId,
      branch_id: branchId,
      employee_id: personas[2].employeeId,
    },
  )
  createdRows.jobHistory.push(browserHistoryId)
  stage('synthetic leave attachment fixture creation')
  psql(
    "INSERT INTO leave_settings (id, company_id, branch_id) "
      + "VALUES (:'id', :'company_id', :'branch_id')",
    { id: browserLeaveSettingsId, company_id: companyId, branch_id: branchId },
  )
  psql(
    "INSERT INTO leave_types (id, company_id, branch_id, code, name) "
      + "VALUES (:'id', :'company_id', :'branch_id', 'BROWSER', 'Browser proof')",
    { id: browserLeaveTypeId, company_id: companyId, branch_id: branchId },
  )
  psql(
    "INSERT INTO leave_types (id, company_id, branch_id, code, name, auto_approve) "
      + "VALUES (:'id', :'company_id', :'branch_id', "
      + "'AUTO_BROWSER', 'Browser auto approval', true)",
    { id: browserAutoLeaveTypeId, company_id: companyId, branch_id: branchId },
  )
  psql(
    "INSERT INTO leave_types (id, company_id, branch_id, code, name) "
      + "VALUES (:'id', :'company_id', :'branch_id', 'APPROVAL_BROWSER', 'Browser approval')",
    { id: browserApprovalLeaveTypeId, company_id: companyId, branch_id: branchId },
  )
  for (const leaveTypeId of [browserLeaveTypeId, browserAutoLeaveTypeId]) {
    const isPendingFixture = leaveTypeId === browserLeaveTypeId
    psql(
      "INSERT INTO leave_balances "
        + "(company_id, branch_id, employee_id, leave_type_id, leave_year, "
        + "entitled_days, accrued_days, pending_days, remaining_days) VALUES "
        + "(:'company_id', :'branch_id', :'employee_id', :'leave_type_id', "
        + "2026, 10.00, 10.00, :'pending_days', :'remaining_days')",
      {
        branch_id: branchId,
        company_id: companyId,
        employee_id: personas[2].employeeId,
        leave_type_id: leaveTypeId,
        pending_days: isPendingFixture ? '1.00' : '0.00',
        remaining_days: isPendingFixture ? '9.00' : '10.00',
      },
    )
  }
  psql(
    "INSERT INTO leave_requests "
      + "(id, company_id, branch_id, employee_id, leave_type_id, start_date, end_date, "
      + "days_requested, status, reason) VALUES (:'id', :'company_id', :'branch_id', "
      + ":'employee_id', :'leave_type_id', '2026-09-21', '2026-09-21', 1.00, "
      + "'Pending', 'Phase 8D browser attachment proof')",
    {
      id: browserLeaveRequestId,
      company_id: companyId,
      branch_id: branchId,
      employee_id: personas[2].employeeId,
      leave_type_id: browserLeaveTypeId,
    },
  )
  psql(
    "INSERT INTO leave_balances "
      + "(company_id, branch_id, employee_id, leave_type_id, leave_year, "
      + "entitled_days, accrued_days, pending_days, remaining_days) VALUES "
      + "(:'company_id', :'branch_id', :'employee_id', :'leave_type_id', "
      + "2026, 10.00, 10.00, 2.00, 8.00)",
    {
      branch_id: branchId,
      company_id: companyId,
      employee_id: personas[2].employeeId,
      leave_type_id: browserApprovalLeaveTypeId,
    },
  )
  for (const [id, date, level] of [
    [browserAdminApprovalRequestId, '2026-10-11', 1],
    [browserManagerApprovalRequestId, '2026-10-12', 2],
  ]) {
    psql(
      "INSERT INTO leave_requests "
        + "(id, company_id, branch_id, employee_id, leave_type_id, start_date, end_date, "
        + "days_requested, status, reason, approval_level_required) VALUES "
        + "(:'id', :'company_id', :'branch_id', :'employee_id', :'leave_type_id', "
        + ":'date', :'date', 1.00, 'Pending', 'Phase 8F browser approval proof', :'level')",
      {
        id,
        company_id: companyId,
        branch_id: branchId,
        employee_id: personas[2].employeeId,
        leave_type_id: browserApprovalLeaveTypeId,
        date,
        level,
      },
    )
  }
  stage('synthetic Phase 9 payroll fixture creation')
  psql(
    "INSERT INTO payroll_runs (id,company_id,branch_id,period,payment_date,sequence_no, "
      + "scr_bank_routing_code,description,status,run_by_app_user_id,total_disbursed, "
      + "employee_count,wps_status,approval_status,submitted_for_approval_at, "
      + "submitted_by_app_user_id,approved_by_app_user_id,approved_at,source_snapshot_digest) "
      + "VALUES (:'id',:'company_id',:'branch_id','2026-08','2026-08-25','0001', "
      + "'999000001','Phase 9H browser payroll','generated',:'actor',12750.00,1,'draft', "
      + "'approved',statement_timestamp(),:'actor',:'actor',statement_timestamp(),:'digest')",
    {
      actor: personas[0].appUserId,
      branch_id: branchId,
      company_id: companyId,
      digest: 'a'.repeat(64),
      id: browserPayrollRunId,
    },
  )
  psql(
    "INSERT INTO payroll_entries (id,payroll_run_id,company_id,branch_id,employee_id, "
      + "basic_salary,housing_allowance,transport_allowance,allowance,additional_allowances, "
      + "deductions,source_snapshot,excluded,wps_payment_status) VALUES "
      + "(:'id',:'run_id',:'company_id',:'branch_id',:'employee_id',10000.00,2000.00, "
      + "500.00,250.00,'[]','[]','{\"eligibleDays\":31}',false,'pending')",
    {
      branch_id: branchId,
      company_id: companyId,
      employee_id: personas[2].employeeId,
      id: browserPayrollEntryId,
      run_id: browserPayrollRunId,
    },
  )
  psql(
    "INSERT INTO payslips (id,company_id,branch_id,payroll_run_id,employee_id,period, "
      + "payment_date,gross_pay,net_pay,data_snapshot) VALUES "
      + "(:'id',:'company_id',:'branch_id',:'run_id',:'employee_id','2026-08', "
      + "'2026-08-25',12750.00,12750.00,CAST(:'snapshot' AS jsonb))",
    {
      branch_id: branchId,
      company_id: companyId,
      employee_id: personas[2].employeeId,
      id: browserPayslipId,
      run_id: browserPayrollRunId,
      snapshot: JSON.stringify({
        deductions: [],
        earnings: [
          { amount: '10000.00', label: 'Basic salary' },
          { amount: '2000.00', label: 'Housing allowance' },
          { amount: '500.00', label: 'Transport allowance' },
          { amount: '250.00', label: 'Fixed allowance' },
        ],
        employeeName: 'Phase employee',
        totalDeductions: '0.00',
        wpsBasicPay: '10000.00',
        wpsVariablePay: '2750.00',
      }),
    },
  )
}

function cleanupFixtures() {
  let cleanupFailed = false
  const cleanup = (operation) => {
    try {
      operation()
    } catch {}
  }
  const verifyCleanup = (operation) => {
    try {
      operation()
    } catch {
      cleanupFailed = true
    }
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (createdRows.company) {
      cleanup(() => psql(
        "DELETE FROM idempotency_records WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM audit_events WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "SET SESSION AUTHORIZATION workloop_migration; "
          + "DELETE FROM shift_swap_history WHERE company_id = :'company_id'; "
          + "DELETE FROM shift_swap_requests WHERE company_id = :'company_id'; "
          + "UPDATE roster_months SET status='draft',version=0,current_version_id=NULL,"
          + "source_version=NULL,published_at=NULL,published_by_app_user_id=NULL "
          + "WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_publication_memberships WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_overtime_approvals WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_actual_hours_evidence WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_publication_versions WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_months WHERE company_id = :'company_id'; "
          + "DELETE FROM roster_assignments WHERE company_id = :'company_id'; "
          + "DELETE FROM attendance_import_row_outcomes WHERE company_id = :'company_id'; "
          + "DELETE FROM clock_events WHERE company_id = :'company_id'; "
          + "DELETE FROM attendance_import_batches WHERE company_id = :'company_id'; "
          + "DELETE FROM biometric_mappings WHERE company_id = :'company_id'; "
          + "DELETE FROM shift_assignments WHERE company_id = :'company_id'; "
          + "DELETE FROM shifts WHERE company_id = :'company_id'; "
          + "DELETE FROM attendance_periods WHERE company_id = :'company_id'; "
          + "DELETE FROM attendance_settings WHERE company_id = :'company_id'; "
          + "RESET SESSION AUTHORIZATION",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "SET SESSION AUTHORIZATION workloop_migration; "
          + "DELETE FROM compliance_overrides WHERE company_id = :'company_id'; "
          + "DELETE FROM payslips WHERE company_id = :'company_id'; "
          + "DELETE FROM payroll_approval_log WHERE company_id = :'company_id'; "
          + "DELETE FROM advance_repayments WHERE company_id = :'company_id'; "
          + "DELETE FROM payroll_entries WHERE company_id = :'company_id'; "
          + "DELETE FROM expense_receipts WHERE company_id = :'company_id'; "
          + "DELETE FROM expense_claims WHERE company_id = :'company_id'; "
          + "DELETE FROM salary_advances WHERE company_id = :'company_id'; "
          + "DELETE FROM payroll_runs WHERE company_id = :'company_id'; "
          + "DELETE FROM nafis_reports WHERE company_id = :'company_id'; "
          + "RESET SESSION AUTHORIZATION",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_approval_delegates WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM storage_operations WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_attachments WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_audit_log WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_requests WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_balances WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_types WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM leave_settings WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM employee_job_history WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
    }
    for (const staffingRuleId of createdRows.staffingRules) {
      cleanup(() => psql(
        "DELETE FROM department_staffing_rules WHERE id = :'staffing_rule_id'",
        { staffing_rule_id: staffingRuleId },
      ))
    }
    for (const departmentId of createdRows.departments) {
      cleanup(() => psql(
        "DELETE FROM departments WHERE id = :'department_id'",
        { department_id: departmentId },
      ))
    }
    for (const historyId of createdRows.jobHistory) {
      cleanup(() => psql(
        "DELETE FROM employee_job_history WHERE id = :'history_id'",
        { history_id: historyId },
      ))
    }
    for (const appUserId of createdRows.profiles) {
      cleanup(() => psql(
        "DELETE FROM user_profiles WHERE app_user_id = :'app_user_id'",
        { app_user_id: appUserId },
      ))
    }
    for (const appUserId of createdRows.appUsers) {
      cleanup(() => psql("DELETE FROM app_users WHERE id = :'app_user_id'", { app_user_id: appUserId }))
    }
    for (const employeeId of createdRows.employees) {
      cleanup(() => psql("DELETE FROM employees WHERE id = :'employee_id'", { employee_id: employeeId }))
    }
    if (createdRows.company) {
      for (const createdBranchId of createdRows.branches) {
        cleanup(() => psql(
          "DELETE FROM branches WHERE id = :'branch_id'",
          { branch_id: createdBranchId },
        ))
      }
      cleanup(() => psql("DELETE FROM companies WHERE id = :'company_id'", { company_id: companyId }))
    }

    for (const persona of personas) {
      cleanup(() => {
        for (const { id } of findUsers(persona.userName)) createdIdentityIds.push(id)
      })
    }
    for (const identityId of new Set(createdIdentityIds)) {
      cleanup(() => kcadm(['delete', `users/${identityId}`, '-r', 'workloop-dev']))
    }
  }

  verifyCleanup(() => assert.deepEqual(
    JSON.parse(kcadm(['get', 'users', '-r', 'workloop-dev'], { output: true })),
    [],
  ))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM app_users'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM user_profiles'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM employees'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM employee_job_history'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM leave_attachments'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM storage_operations'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM leave_requests'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM leave_approval_delegates'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM leave_types'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM leave_settings'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM expense_claims'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM salary_advances'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM payroll_runs'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM payroll_entries'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM payslips'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM nafis_reports'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM shift_swap_requests'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM roster_publication_versions'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM roster_assignments'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM clock_events'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM biometric_mappings'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM shifts'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM attendance_periods'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM attendance_settings'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM companies'), '0'))
  verifyCleanup(() => run(['exec', '-T', 'keycloak', 'rm', '-f', kcadmConfig]))
  verifyCleanup(() => run(['exec', '-T', 'keycloak', 'test', '!', '-e', kcadmConfig]))
  if (cleanupFailed) throw new Error('local synthetic fixture cleanup failed')
}

async function waitForStatus(page, status) {
  await page.locator(`main[data-session-status="${status}"]`).waitFor({ timeout: 20_000 })
}

async function waitForSettledStatus(page, expected, label) {
  await page.waitForFunction(
    () => {
      const status = document.querySelector('main')?.dataset.sessionStatus
      return status && status !== 'loading'
    },
    undefined,
    { timeout: 20_000 },
  )
  const status = await page.locator('main').getAttribute('data-session-status')
  stage(`${label} ${status}`)
  assert.equal(status, expected)
}

async function interactiveLogin(page, persona) {
  stage(`${persona.role} login redirect`)
  await page.getByRole('button', { name: 'Sign in' }).click()
  stage(`${persona.role} credential form`)
  await page.locator('#username').fill(persona.userName)
  await page.locator('#password').fill(persona.password)
  stage(`${persona.role} login callback`)
  await page.locator('#kc-login').click()
  await page.waitForFunction(
    () => {
      const status = document.querySelector('main')?.dataset.sessionStatus
      return status && status !== 'loading'
    },
    undefined,
    { timeout: 20_000 },
  )
  const status = await page.locator('main').getAttribute('data-session-status')
  stage(`${persona.role} login callback ${status}`)
  assert.equal(status, 'signed-in')
}

async function assertNoPersistedTokens(page) {
  const storage = await page.evaluate(async () => {
    const { authenticationSession } = await import('/src/authSession.js')
    const user = await authenticationSession().manager.getUser()
    const tokens = [user?.access_token, user?.id_token, user?.refresh_token].filter(Boolean)
    const persisted = JSON.stringify({
      cookie: document.cookie,
      local: Object.entries(localStorage),
      session: Object.entries(sessionStorage),
    })
    return {
      cacheCount: (await caches.keys()).length,
      indexedDatabaseCount: (await indexedDB.databases()).length,
      local: Object.entries(localStorage),
      session: Object.entries(sessionStorage),
      tokenPersisted: tokens.some((token) => persisted.includes(token)),
    }
  })
  stage(`storage local ${storage.local.length}`)
  assert.deepEqual(storage.local, [])
  stage(`storage session ${storage.session.length}`)
  assert.deepEqual(storage.session, [])
  stage(`storage cache ${storage.cacheCount}`)
  assert.equal(storage.cacheCount, 0)
  stage(`storage indexeddb ${storage.indexedDatabaseCount}`)
  assert.equal(storage.indexedDatabaseCount, 0)
  stage(`storage token match ${storage.tokenPersisted}`)
  assert.equal(storage.tokenPersisted, false)
}

async function assertSampleApi(page, persona) {
  await page.waitForFunction(
    () => document.querySelector('[data-public-api-status]')?.dataset.publicApiStatus === 'ready'
      && document.querySelector('[data-account-api-status]')?.dataset.accountApiStatus === 'ready',
    undefined,
    { timeout: 20_000 },
  )
  assert.equal(await page.locator('[data-public-api-status]').textContent(), 'ok')
  assert.equal(await page.locator('[data-account-api-status]').textContent(), persona.role)
  const sampleText = await page.locator('.sample-status').textContent()
  assert.ok(sampleText.includes(persona.appUserId))
  assert.ok(sampleText.includes(companyId))
  if (persona.employeeId) {
    assert.ok(sampleText.includes(persona.employeeId))
    assert.ok(sampleText.includes(branchId))
  } else {
    assert.ok(sampleText.includes('Not linked'))
    assert.ok(sampleText.includes('Not selected'))
  }
}

async function assertLeaveAttachmentJourney(page) {
  const body = Buffer.from('%PDF-1.7\n% Phase 8D browser proof\n%%EOF\n')
  stage('employee leave attachment upload')
  await page.getByRole('heading', { name: 'My leave' }).waitFor({ timeout: 20_000 })
  const input = page.getByLabel(`Upload attachment for request ${browserLeaveRequestId}`)
  await input.waitFor({ timeout: 20_000 })
  const intentResponsePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/leave/attachment-submissions'
  })
  const uploadResponsePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname.endsWith('/file')
  })
  await input.setInputFiles({
    name: 'phase-8d-browser.pdf',
    mimeType: 'application/pdf',
    buffer: body,
  })
  stage('employee leave attachment intent response')
  const intentResponse = await intentResponsePromise
  assert.equal(intentResponse.status(), 201, await intentResponse.text())
  stage('employee leave attachment file response')
  const uploadResponse = await uploadResponsePromise
  assert.equal(uploadResponse.status(), 201, await uploadResponse.text())
  await page.getByText('Upload complete.', { exact: true }).waitFor({ timeout: 20_000 })
  const downloadButton = page.getByRole('button', { name: 'Download phase-8d-browser.pdf' })
  await downloadButton.waitFor({ timeout: 20_000 })
  assert.equal(
    psql(
      "SELECT concat(status, '|', file_name) FROM leave_attachments "
        + "WHERE leave_request_id = :'request_id'",
      { request_id: browserLeaveRequestId },
    ),
    'attached|phase-8d-browser.pdf',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM storage_operations AS operation "
        + "JOIN leave_attachments AS attachment ON attachment.id = operation.entity_id "
        + "WHERE attachment.leave_request_id = :'request_id' AND operation.status = 'succeeded'",
      { request_id: browserLeaveRequestId },
    ),
    '1',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM audit_events WHERE company_id = :'company_id' "
        + "AND action = 'leave_attachment_uploaded'",
      { company_id: companyId },
    ),
    '1',
  )

  stage('employee signed leave attachment download')
  const signedResponsePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname.endsWith('/download')
  })
  await downloadButton.evaluate((button) => button.click())
  const signedResponse = await signedResponsePromise
  assert.equal(signedResponse.status(), 200)
  const signedBody = await signedResponse.json()
  assert.deepEqual(Object.keys(signedBody), ['data'])
  const downloaded = await page.request.get(signedBody.data.url)
  assert.equal(downloaded.status(), 200)
  assert.equal(downloaded.headers()['content-type'], 'application/pdf')
  assert.ok(
    downloaded.headers()['content-disposition'].includes('filename="phase-8d-browser.pdf"'),
  )
  assert.deepEqual(await downloaded.body(), body)

  stage('employee attached leave request cancellation')
  await cancelLeaveThroughTable(page, {
    admin: false,
    requestId: browserLeaveRequestId,
    date: '2026-09-21',
  })
  assert.equal(
    psql(
      "SELECT concat(attachment.status, '|', operation.status) "
        + "FROM leave_attachments AS attachment "
        + "JOIN storage_operations AS operation ON operation.entity_id = attachment.id "
        + "WHERE attachment.leave_request_id = :'request_id' "
        + "AND operation.operation = 'delete'",
      { request_id: browserLeaveRequestId },
    ),
    'removed|succeeded',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM audit_events WHERE company_id = :'company_id' "
        + "AND action = 'leave_attachment_cleanup_requested'",
      { company_id: companyId },
    ),
    '1',
  )
  assert.equal((await page.request.get(signedBody.data.url)).status(), 404)
}

async function submitLeaveThroughForm(page, { admin, date, leaveType, employeeId = null }) {
  await page.getByRole('heading', {
    name: admin ? 'Branch leave overview' : 'My leave',
  }).waitFor({ timeout: 20_000 })
  const form = page.locator('.leave-request-form')
  try {
    await form.waitFor({ timeout: 20_000 })
  } catch {
    const overview = await page.locator('.leave-overview').textContent()
    throw new Error(`leave request form unavailable: ${overview}`)
  }
  if (admin) {
    await form.locator('label').filter({ hasText: /^Employee/ }).locator('select')
      .selectOption(employeeId)
  }
  await form.locator('label').filter({ hasText: /^Leave type/ }).locator('select')
    .selectOption({ label: leaveType })
  await form.getByLabel('Start date', { exact: true }).fill(date)
  await form.getByLabel('End date', { exact: true }).fill(date)
  const responsePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname === (admin
        ? '/api/v1/leave/requests/branch'
        : '/api/v1/leave/requests/self')
  })
  await form.getByRole('button', { name: 'Submit request' }).click()
  const response = await responsePromise
  assert.equal(response.status(), 201, await response.text())
  return (await response.json()).data
}

async function cancelLeaveThroughTable(page, { admin, requestId, date }) {
  const row = page.locator('tr', { hasText: `${date} to ${date}` })
  await row.waitFor({ timeout: 20_000 })
  const responsePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/leave/requests/${requestId}/cancel/${
        admin ? 'branch' : 'self'
      }`
  })
  await row.getByRole('button', { name: 'Cancel' }).click()
  const response = await responsePromise
  assert.equal(response.status(), 200, await response.text())
  assert.equal((await response.json()).data.status, 'Cancelled')
  await row.getByText('Cancelled', { exact: true }).waitFor({ timeout: 20_000 })
}

async function assertLeaveSubmissionJourney(page, persona) {
  const admin = persona.role === 'admin'
  if (admin && await page.locator('.branch-chooser').count()) {
    await page.getByRole('button', { name: 'Phase 3G main', exact: true }).click()
  }
  const readiness = await page.evaluate(async ({ admin, branchId, year }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const {
      readAllAdminLeaveBalances,
      readAllAdminLeaveRequests,
      readAllEmployeeLeaveBalances,
      readAllEmployeeLeaveRequests,
    } = await import('/src/leaveBalanceApi.js')
    const { readAllEmployees } = await import('/src/employeeApi.js')
    const { readSubmissionLeaveTypes } = await import('/src/leaveRequestApi.js')
    const authentication = authenticationSession()
    const capture = async (name, operation) => {
      try {
        const result = await operation()
        return { name, count: result.length, ok: true }
      } catch (error) {
        return { name, code: error.code ?? null, message: error.message, ok: false }
      }
    }
    const options = { year }
    return Promise.all(admin ? [
      capture('balances', () => readAllAdminLeaveBalances(authentication, branchId, options)),
      capture('requests', () => readAllAdminLeaveRequests(authentication, branchId, options)),
      capture('types', () => readSubmissionLeaveTypes(authentication, branchId)),
      capture('employees', () => readAllEmployees(authentication, branchId)),
    ] : [
      capture('balances', () => readAllEmployeeLeaveBalances(authentication, options)),
      capture('requests', () => readAllEmployeeLeaveRequests(authentication, options)),
      capture('types', () => readSubmissionLeaveTypes(authentication, null)),
    ])
  }, { admin, branchId, year: 2026 })
  stage(`${persona.role} leave readiness ${JSON.stringify(readiness)}`)
  if (readiness.some(({ ok }) => !ok)) {
    throw new Error(`${persona.role} leave readiness failed: ${JSON.stringify(readiness)}`)
  }
  const date = admin ? '2026-10-05' : '2026-10-04'
  const leaveType = admin ? 'Browser auto approval' : 'Browser proof'
  stage(`${persona.role} leave request submission`)
  const submitted = await submitLeaveThroughForm(page, {
    admin,
    date,
    leaveType,
    employeeId: personas[2].employeeId,
  })
  assert.equal(submitted.employeeId, personas[2].employeeId)
  assert.equal(submitted.daysRequested, '1.00')
  assert.equal(submitted.status, admin ? 'Approved' : 'Pending')

  stage(`${persona.role} leave request cancellation`)
  await cancelLeaveThroughTable(page, { admin, requestId: submitted.id, date })
  const expectedAuditCount = admin ? '3' : '2'
  assert.equal(
    psql(
      "SELECT count(*) FROM leave_audit_log WHERE leave_request_id = :'request_id'",
      { request_id: submitted.id },
    ),
    expectedAuditCount,
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM audit_events WHERE entity_id = :'request_id' "
        + "AND action IN ('leave_request_submitted', "
        + "'leave_request_auto_approved', 'leave_request_cancelled')",
      { request_id: submitted.id },
    ),
    expectedAuditCount,
  )
  assert.equal(
    psql(
      "SELECT concat(pending_days, '|', used_days, '|', remaining_days) "
        + "FROM leave_balances WHERE employee_id = :'employee_id' "
        + "AND leave_type_id = :'leave_type_id' AND leave_year = 2026",
      {
        employee_id: personas[2].employeeId,
        leave_type_id: admin ? browserAutoLeaveTypeId : browserLeaveTypeId,
      },
    ),
    '0.00|0.00|10.00',
  )
}

async function decideApprovalThroughTable(page, { admin, requestId, date, reason }) {
  const row = page.locator('.leave-approvals tr', { hasText: `${date} to ${date}` })
  await row.waitFor({ timeout: 20_000 })
  await row.getByRole('button', { name: 'Approve' }).waitFor()
  await row.getByRole('button', { name: 'Reject' }).waitFor()
  return page.evaluate(async ({ admin, branchId, requestId, reason }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const {
      decideLeave,
      readAdminApprovalQueue,
      readApproverQueue,
    } = await import('/src/leaveApprovalApi.js')
    const authentication = authenticationSession()
    const items = admin
      ? await readAdminApprovalQueue(authentication, branchId)
      : await readApproverQueue(authentication)
    const item = items.find((candidate) => candidate.request.id === requestId)
    if (!item) throw new Error('Rendered approval request is no longer available')
    return decideLeave(
      authentication,
      admin ? branchId : null,
      requestId,
      'approve',
      reason,
      item.request.updatedAt,
    )
  }, { admin, branchId, requestId, reason })
}

async function assertLeaveApprovalJourney(page, persona) {
  const admin = persona.role === 'admin'
  if (admin && await page.locator('.branch-chooser').count()) {
    await page.getByRole('button', { name: 'Phase 3G main', exact: true }).click()
  }
  await page.getByRole('heading', {
    name: admin ? 'Branch leave decisions' : 'Leave approvals',
  }).waitFor({ timeout: 20_000 })
  if (admin) {
    stage('administrator leave delegation creation')
    const form = page.locator('.employee-form-grid').filter({
      has: page.getByRole('button', { name: 'Create delegation' }),
    })
    await form.getByLabel('Approver').selectOption(personas[1].employeeId)
    await form.getByLabel('Delegate').selectOption(personas[2].employeeId)
    await form.getByLabel('Starts').fill('2026-10-20')
    await form.getByLabel('Ends').fill('2026-10-21')
    const createResponsePromise = page.waitForResponse((response) => (
      response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/leave/delegations/branch'
    ))
    await form.getByRole('button', { name: 'Create delegation' }).click()
    const createResponse = await createResponsePromise
    assert.equal(createResponse.status(), 201, await createResponse.text())
    const delegation = (await createResponse.json()).data
    await page.getByText('Delegation saved.', { exact: true }).waitFor({ timeout: 20_000 })
    assert.equal(
      psql(
        "SELECT count(*) FROM leave_approval_delegates WHERE id = :'delegation_id'",
        { delegation_id: delegation.id },
      ),
      '1',
    )
  }

  const requestId = admin ? browserAdminApprovalRequestId : browserManagerApprovalRequestId
  const date = admin ? '2026-10-11' : '2026-10-12'
  stage(`${persona.role} leave approval decision`)
  const decided = await decideApprovalThroughTable(page, {
    admin,
    requestId,
    date,
    reason: admin ? 'Browser administrator override' : 'Browser manager approval',
  })
  assert.equal(decided.status, admin ? 'Approved' : 'ManagerApproved')
  assert.equal(
    psql(
      "SELECT count(*) FROM leave_audit_log WHERE leave_request_id = :'request_id'",
      { request_id: requestId },
    ),
    '1',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM audit_events WHERE entity_id = :'request_id' "
        + "AND action IN ('leave_request_approved', 'leave_request_manager_approved')",
      { request_id: requestId },
    ),
    '1',
  )
}

function businessFingerprint() {
  return psql(
    "SELECT md5(concat_ws('|', "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.id)::text, '[]') FROM companies c), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(b) ORDER BY b.id)::text, '[]') FROM branches b), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(e) ORDER BY e.id)::text, '[]') FROM employees e), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(h) ORDER BY h.id)::text, '[]') FROM employee_job_history h), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY a.id)::text, '[]') FROM app_users a), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.app_user_id)::text, '[]') FROM user_profiles p)))",
  )
}

async function assertEmployeeApi(page, persona) {
  if (persona.role === 'admin' && await page.locator('.branch-chooser').count()) {
    await page.getByRole('button', { name: 'Phase 3G main', exact: true }).click()
  }
  await page.locator('.employee-directory').waitFor({ timeout: 20_000 })
  const result = await page.evaluate(async ({ role, branchId, employeeId }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const session = authenticationSession()
    const capture = async (operation) => {
      try {
        return { response: await operation() }
      } catch (error) {
        return { error: { code: error.code, status: error.status } }
      }
    }
    const adminHeaders = { 'X-Workloop-Branch-ID': branchId }
    return {
      listing: await capture(() => session.request('/api/v1/employees', {
        access: 'protected', headers: adminHeaders,
      })),
      detail: await capture(() => session.request(`/api/v1/employees/${employeeId}`, {
        access: 'protected', headers: adminHeaders,
      })),
      self: await capture(() => session.request('/api/v1/employees/self', {
        access: 'protected',
      })),
      reports: await capture(() => session.request('/api/v1/employees/direct-reports', {
        access: 'protected',
      })),
      employeeHistory: await capture(() => session.request(
        `/api/v1/employees/${employeeId}/job-history`,
        { access: 'protected', headers: adminHeaders },
      )),
      branchHistory: await capture(() => session.request('/api/v1/employee-job-history', {
        access: 'protected', headers: adminHeaders,
      })),
      headerOnSelf: await capture(() => session.request('/api/v1/employees/self', {
        access: 'protected', headers: adminHeaders,
      })),
      role,
    }
  }, {
    role: persona.role,
    branchId,
    employeeId: personas[2].employeeId,
  })

  if (persona.role === 'admin') {
    assert.equal(result.listing.response.data.length, 2)
    assert.ok(result.listing.response.data.every((employee) => employee.basicSalary === '10000.00'))
    assert.deepEqual(Object.keys(result.detail.response.data).sort(), [
      'active', 'allowance', 'bankAccountHolder', 'bankName', 'bankRoutingCode',
      'basicSalary', 'createdAt', 'dateOfBirth', 'department', 'emergencyContactName',
      'emergencyContactPhone', 'emergencyContactRelationship', 'emiratesId',
      'emiratesIdExpiry', 'empNo', 'employmentStartDate', 'employmentStatus',
      'freeZoneName', 'gender', 'homeCountryAddress', 'housingAllowance', 'iban', 'id',
      'jobTitle', 'labourCardExpiry', 'labourCardNumber', 'licenceAuthority',
      'licenceExpiry', 'licenceNumber', 'maritalStatus', 'molId', 'nafisRegistrationNo',
      'name', 'nationality', 'otherAllowances', 'otherAllowancesLabel', 'passportExpiry',
      'passportNumber', 'personalEmail', 'phone', 'photoUrl', 'probationEndDate',
      'probationExtended', 'reportingManagerId', 'sponsoringEntity', 'terminationDate',
      'terminationReason', 'transportAllowance', 'updatedAt', 'visaExpiry', 'visaNumber',
      'visaType', 'workEmail', 'workLocationType',
    ])
    assert.equal(result.employeeHistory.response.data.length, 1)
    assert.equal(result.branchHistory.response.data.length, 1)
    assert.equal(result.self.error.code, 'operation_not_permitted')
    assert.equal(result.reports.error.code, 'operation_not_permitted')
    assert.equal(result.headerOnSelf.error.code, 'operation_not_permitted')
    await page.getByRole('button', { name: /Phase employee/ }).click()
    await page.getByRole('heading', { name: 'Phase employee' }).waitFor()

    stage('admin employee creation')
    const employeeForm = page.locator('[data-employee-create-form]')
    await employeeForm.getByLabel('Employee number').fill('E-7F-BROWSER')
    await employeeForm.getByLabel('Name', { exact: true }).fill('Phase 7F browser employee')
    await employeeForm.getByLabel('MOL ID').fill('10003048635715')
    await employeeForm.getByLabel('Work email').fill('PHASE7F-BROWSER@EXAMPLE.TEST')
    await employeeForm.getByLabel('Job title').fill('Browser verifier')
    await employeeForm.getByLabel('Department').selectOption({ label: 'Clinical' })
    await employeeForm.getByLabel('Reporting manager').selectOption(personas[1].employeeId)
    await employeeForm.getByLabel('Basic salary').fill('9000.00')
    const createPromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'POST' && new URL(response.url()).pathname === '/api/v1/employees'
    })
    await employeeForm.getByRole('button', { name: 'Create employee' }).click()
    const createResponse = await createPromise
    const createBody = await createResponse.json()
    assert.equal(createResponse.status(), 201)
    assert.equal(createBody.data.workEmail, 'phase7f-browser@example.test')
    assert.equal(createBody.data.reportingManagerId, personas[1].employeeId)
    createdRows.employees.push(createBody.data.id)
    await page.locator('[data-employee-create-status="saved"]').waitFor()
    await page.getByRole('heading', { name: 'Phase 7F browser employee' }).waitFor()

    stage('admin ordinary employee edit')
    const editForm = page.locator('[data-employee-edit-form]')
    await editForm.getByLabel('Name', { exact: true }).fill('Phase 7F browser employee edited')
    await editForm.getByLabel('Personal email').fill('browser-edit@example.test')
    const editPromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'PATCH'
        && new URL(response.url()).pathname === `/api/v1/employees/${createBody.data.id}`
    })
    await editForm.getByRole('button', { name: 'Save details' }).click()
    const editResponse = await editPromise
    const editBody = await editResponse.json()
    assert.equal(editResponse.status(), 200)
    assert.equal(editBody.data.name, 'Phase 7F browser employee edited')
    assert.equal(editBody.data.personalEmail, 'browser-edit@example.test')
    await page.locator('[data-employee-edit-status="saved"]').waitFor()

    stage('admin employee CSV import')
    const csv = [
      'Emp No,Name,MOL ID,Bank Name,Bank Routing Code,IBAN,Basic Salary,Allowance',
      'E-7F-I-1,Phase 7F imported one,10003048635714,Synthetic Bank,123456789,AE000000000000000000001,5000,250',
      'E-7F-I-2,Phase 7F imported two,10003048635713,Synthetic Bank,,,0,0',
    ].join('\n')
    await page.getByLabel('CSV file').setInputFiles({
      name: 'phase-7f-employees.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    })
    await page.getByText('2 rows ready for review.').waitFor()
    const importPromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'POST'
        && new URL(response.url()).pathname === '/api/v1/employee-imports'
    })
    await page.getByRole('button', { name: 'Import employees' }).click()
    const importResponse = await importPromise
    const importBody = await importResponse.json()
    assert.equal(importResponse.status(), 201)
    assert.equal(importBody.data.createdCount, 2)
    assert.deepEqual(importBody.data.rows.map(({ rowNumber }) => rowNumber), [2, 3])
    createdRows.employees.push(...importBody.data.rows.map(({ employeeId }) => employeeId))
    await page.locator('[data-employee-import-status="saved"]').waitFor()

    stage('admin employee lifecycle title change')
    const lifecycleForm = page.locator('[data-employee-lifecycle-form]')
    await lifecycleForm.getByLabel('New title').fill('Senior browser verifier')
    await lifecycleForm.getByLabel('Reason').fill('Approved browser lifecycle proof')
    const lifecyclePromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'POST'
        && new URL(response.url()).pathname === `/api/v1/employees/${createBody.data.id}/title-change`
    })
    await lifecycleForm.getByRole('button', { name: 'Run workflow' }).click()
    const lifecycleResponse = await lifecyclePromise
    assert.equal(lifecycleResponse.status(), 200)
    assert.equal((await lifecycleResponse.json()).data.jobTitle, 'Senior browser verifier')
    await page.getByRole('heading', { name: 'Phase 7F browser employee edited' }).waitFor()

    stage('admin employee portal role round trip')
    const portalReadPromise = page.waitForResponse((response) => (
      response.request().method() === 'GET'
      && new URL(response.url()).pathname
        === `/api/v1/employees/${personas[2].employeeId}/portal-role`
    ))
    await page.getByRole('button', { name: /Phase employee/ }).click()
    const portalReadResponse = await portalReadPromise
    assert.equal(portalReadResponse.status(), 200)
    const portalRead = (await portalReadResponse.json()).data
    if (!portalRead.activated) {
      const state = psql(
        "SELECT app_user.status::text,profile.role::text,profile.employee_id,"
          + "employee.active,employee.employment_status,employee.branch_id "
          + "FROM app_users AS app_user "
          + "LEFT JOIN user_profiles AS profile ON profile.app_user_id=app_user.id "
          + "LEFT JOIN employees AS employee ON employee.id=profile.employee_id "
          + "WHERE app_user.id=:'app_user_id'",
        { app_user_id: personas[2].appUserId },
      )
      throw new Error(`employee portal fixture is ineligible: ${state}`)
    }
    assert.deepEqual(portalRead, {
      activated: true,
      employeeId: personas[2].employeeId,
      role: 'employee',
    })
    const portalPanel = page.locator('.employee-portal-role')
    await portalPanel.getByText('Current role: employee').waitFor()
    const promotePromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'PUT'
        && new URL(response.url()).pathname === `/api/v1/employees/${personas[2].employeeId}/portal-role`
    })
    await portalPanel.getByRole('button', { name: 'Change to manager' }).click()
    const promoteResponse = await promotePromise
    assert.equal(promoteResponse.status(), 200)
    assert.equal((await promoteResponse.json()).data.role, 'manager')
    await portalPanel.getByText('Current role: manager').waitFor()
    const demotePromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'PUT'
        && new URL(response.url()).pathname === `/api/v1/employees/${personas[2].employeeId}/portal-role`
    })
    await portalPanel.getByRole('button', { name: 'Change to employee' }).click()
    const demoteResponse = await demotePromise
    assert.equal(demoteResponse.status(), 200)
    assert.equal((await demoteResponse.json()).data.role, 'employee')
    await portalPanel.getByText('Current role: employee').waitFor()

    stage('admin employee mutation cleanup')
    psql("DELETE FROM idempotency_records WHERE company_id = :'company_id'", {
      company_id: companyId,
    })
    psql("DELETE FROM audit_events WHERE company_id = :'company_id'", { company_id: companyId })
    psql("DELETE FROM employee_job_history WHERE employee_id = :'employee_id'", {
      employee_id: createBody.data.id,
    })
    for (const employeeId of [
      createBody.data.id,
      ...importBody.data.rows.map(({ employeeId }) => employeeId),
    ]) {
      psql("DELETE FROM employees WHERE id = :'employee_id'", { employee_id: employeeId })
    }
    psql("DELETE FROM departments WHERE id = :'department_id'", {
      department_id: browserDepartmentId,
    })
    await page.getByRole('button', { name: 'Change branch' }).click()
    await page.locator('.branch-chooser').waitFor()
    assert.equal(await page.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  } else {
    assert.equal(result.listing.error.code, 'operation_not_permitted')
    assert.equal(result.detail.error.code, 'operation_not_permitted')
    assert.equal(result.employeeHistory.error.code, 'operation_not_permitted')
    assert.equal(result.branchHistory.error.code, 'operation_not_permitted')
    assert.equal(result.headerOnSelf.error.code, 'operation_not_permitted')
    assert.equal(result.self.response.data.id, persona.employeeId)
    assert.equal(result.self.response.data.basicSalary, '10000.00')
    assert.match(result.self.response.data.updatedAt, /^\d{4}-\d{2}-\d{2}T/)
    if (persona.role === 'manager') {
      assert.equal(result.reports.response.data.length, 1)
      assert.deepEqual(Object.keys(result.reports.response.data[0]).sort(), [
        'department', 'empNo', 'employmentStartDate', 'employmentStatus', 'id', 'jobTitle',
        'name', 'photoUrl', 'probationEndDate',
      ])
      assert.equal(await page.locator('.direct-reports li').count(), 1)
    } else {
      assert.equal(result.reports.error.code, 'operation_not_permitted')
      assert.equal(await page.locator('.direct-reports').count(), 0)
    }
    stage(`${persona.role} self-contact update`)
    const contactForm = page.locator('[data-employee-self-contact-form]')
    const contactPhone = persona.role === 'manager' ? '+971500000072' : '+971500000073'
    await contactForm.getByLabel('Phone', { exact: true }).fill(contactPhone)
    const contactPromise = page.waitForResponse((response) => (
      response.request().method() === 'PATCH'
      && new URL(response.url()).pathname === '/api/v1/employees/self/contact'
    ))
    await contactForm.getByRole('button', { name: 'Save contact details' }).click()
    assert.equal((await contactPromise).status(), 200)
    await page.locator('[data-employee-self-contact-form]').getByLabel('Phone', { exact: true }).waitFor()
  }
}

async function assertOrganizationApi(page, persona) {
  await page.waitForFunction(
    (role) => role === 'admin'
      ? Boolean(document.querySelector('.branch-chooser'))
      : Boolean(document.querySelector('.organization-summary')),
    persona.role,
    { timeout: 20_000 },
  )

  const result = await page.evaluate(async ({ role, branchId, alternateBranchId }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const session = authenticationSession()
    const capture = async (operation) => {
      try {
        return { response: await operation() }
      } catch (error) {
        return { error: { code: error.code, status: error.status } }
      }
    }
    const branches = await session.request('/api/v1/branches?limit=1&sort=name', {
      access: 'protected',
    })
    const next = branches.page.nextCursor === null
      ? null
      : await session.request(`/api/v1/branches?limit=1&sort=name&cursor=${branches.page.nextCursor}`, {
        access: 'protected',
      })
    return {
      branches,
      next,
      company: await capture(() => session.request('/api/v1/company', { access: 'protected' })),
      employer: await capture(() => session.request('/api/v1/employer', { access: 'protected' })),
      detail: await capture(() => session.request(`/api/v1/branches/${branchId}`, {
        access: 'protected',
        headers: { 'X-Workloop-Branch-ID': branchId },
      })),
      mismatch: await capture(() => session.request(`/api/v1/branches/${alternateBranchId}`, {
        access: 'protected',
        headers: { 'X-Workloop-Branch-ID': branchId },
      })),
      unknown: await capture(() => session.request('/api/v1/branches?companyId=guessed', {
        access: 'protected',
      })),
      role,
    }
  }, { role: persona.role, branchId, alternateBranchId })

  stage(`${persona.role} organization API ${JSON.stringify({
    company: result.company.error ?? 'ok',
    detail: result.detail.error ?? 'ok',
    employer: result.employer.error ?? 'ok',
    mismatch: result.mismatch.error ?? 'ok',
    unknown: result.unknown.error ?? 'ok',
  })}`)

  if (persona.role === 'admin') {
    assert.deepEqual(Object.keys(result.company.response.data).sort(), [
      'createdAt', 'enableNafis', 'id', 'nafisQuotaPercent', 'name', 'sector', 'updatedAt',
    ])
    assert.equal(result.employer.error.code, 'operation_not_permitted')
    assert.equal(result.branches.data.length, 1)
    assert.equal(result.branches.page.hasMore, true)
    assert.equal(result.next.data.length, 1)
    assert.notEqual(result.branches.data[0].id, result.next.data[0].id)
    assert.deepEqual(Object.keys(result.detail.response.data).sort(), [
      'address', 'contactEmail', 'createdAt', 'defaultBankRoutingCode', 'defaultSalaryDay',
      'enableBiometricImport', 'enableStaffingRules', 'freeZoneName', 'id', 'logoUrl',
      'molEmployerId', 'name', 'updatedAt', 'workLocationType',
    ])
    assert.equal(result.mismatch.error.code, 'resource_not_found')
    assert.equal(result.mismatch.error.status, 404)
    const options = page.locator('.branch-options button')
    assert.equal(await options.count(), 2)
    const chosen = page.getByRole('button', { name: 'Phase 3G main', exact: true })
    const chosenName = (await chosen.textContent()).trim()
    await chosen.click()
    await page.locator('.organization-summary').waitFor()
    assert.equal((await page.locator('[data-selected-branch-name]').textContent()).trim(), chosenName)
    assert.match(
      await page.evaluate(() => sessionStorage.getItem('workloop.branchId')),
      /^[0-9a-f-]{36}$/,
    )

    const selectedBranchForm = page.locator('.settings-form').filter({
      has: page.getByRole('heading', { name: 'Selected branch' }),
    })
    await selectedBranchForm.getByRole('button', { name: 'Delete branch' }).click()
    await selectedBranchForm.getByText('Select delete again to confirm.').waitFor()
    await selectedBranchForm.getByRole('button', { name: 'Confirm delete' }).click()
    const guardedDeleteStatus = selectedBranchForm.getByRole('status')
    await page.waitForFunction(
      () => {
        const text = [...document.querySelectorAll('.settings-form')]
          .find((form) => form.querySelector('h3')?.textContent === 'Selected branch')
          ?.querySelector('[role="status"]')?.textContent
        return Boolean(text) && text !== 'Select delete again to confirm.'
      },
      undefined,
      { timeout: 30_000 },
    )
    const guardedDeleteMessage = (await guardedDeleteStatus.textContent()).trim()
    stage(`admin guarded delete ${guardedDeleteMessage}`)
    assert.equal(
      guardedDeleteMessage,
      'This branch name or its retained records prevent the change.',
    )

    const createBranchForm = page.locator('.settings-form').filter({
      has: page.getByRole('heading', { name: 'Create branch' }),
    })
    await createBranchForm.getByLabel('Name').fill('Phase 7C browser branch')
    const createResponsePromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'POST' && new URL(response.url()).pathname === '/api/v1/branches'
    })
    await createBranchForm.getByRole('button', { name: 'Create branch' }).click()
    const createResponse = await createResponsePromise
    const createResponseBody = await createResponse.json()
    const createdBranchId = createResponseBody?.data?.id
    if (typeof createdBranchId === 'string' && !createdRows.branches.includes(createdBranchId)) {
      createdRows.branches.push(createdBranchId)
    }
    stage(`admin create branch response ${createResponse.status()} ${JSON.stringify(createResponseBody)}`)
    assert.equal(createResponse.status(), 201)
    const createStatus = createBranchForm.getByRole('status')
    await createStatus.waitFor()
    const createMessage = (await createStatus.textContent()).trim()
    stage(`admin create branch ${createMessage}`)
    assert.equal(createMessage, 'Branch created.')
    assert.equal(
      (await page.locator('[data-selected-branch-name]').textContent()).trim(),
      'Phase 7C browser branch',
    )

    await selectedBranchForm.getByLabel('Name', { exact: true }).fill('Phase 7C browser branch updated')
    await selectedBranchForm.getByRole('button', { name: 'Save branch' }).click()
    await selectedBranchForm.getByText('Branch settings saved.').waitFor()
    await selectedBranchForm.getByRole('button', { name: 'Delete branch' }).click()
    await selectedBranchForm.getByRole('button', { name: 'Confirm delete' }).click()
    await page.locator('.branch-chooser').waitFor()
    assert.equal(await page.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  } else {
    assert.equal(result.company.error.code, 'operation_not_permitted')
    assert.deepEqual(Object.keys(result.employer.response.data).sort(), [
      'branchAddress', 'branchContactEmail', 'branchName', 'companyName',
      'freeZoneName', 'logoUrl', 'workLocationType',
    ])
    assert.equal(result.branches.data.length, 1)
    assert.equal(result.branches.data[0].id, branchId)
    assert.equal(result.next, null)
    assert.equal(result.detail.error.code, 'operation_not_permitted')
    assert.equal(result.mismatch.error.code, 'operation_not_permitted')
  }
  assert.equal(result.unknown.error.code, 'validation_failed')
  assert.equal(result.unknown.error.status, 422)
}

async function assertDepartmentApi(page, persona) {
  if (persona.role !== 'admin') {
    assert.equal(await page.locator('.department-manager').count(), 0)
    const result = await page.evaluate(async ({ branchId }) => {
      const { authenticationSession } = await import('/src/authSession.js')
      try {
        await authenticationSession().request('/api/v1/departments', {
          access: 'protected',
          headers: { 'X-Workloop-Branch-ID': branchId },
        })
        return null
      } catch (error) {
        return { code: error.code, status: error.status }
      }
    }, { branchId })
    assert.deepEqual(result, { code: 'operation_not_permitted', status: 403 })
    return
  }

  if (await page.locator('.branch-chooser').count()) {
    await page.getByRole('button', { name: 'Phase 3G main', exact: true }).click()
  }
  await page.locator('.department-manager').waitFor({ timeout: 20_000 })
  const departmentForm = page.locator('.department-editor')
  await departmentForm.getByLabel('Name').fill('Phase 7E browser department')
  const departmentCreatePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST' && new URL(response.url()).pathname === '/api/v1/departments'
  })
  await departmentForm.getByRole('button', { name: 'Save department' }).click()
  const departmentCreate = await departmentCreatePromise
  const departmentBody = await departmentCreate.json()
  assert.equal(departmentCreate.status(), 201)
  assert.equal(departmentBody.data.name, 'Phase 7E browser department')
  createdRows.departments.push(departmentBody.data.id)
  await page.getByText('Department created.', { exact: true }).waitFor()

  await page.getByRole('button', { name: 'Phase 7E browser department', exact: true }).click()
  await departmentForm.getByLabel('Department head').selectOption(personas[1].employeeId)
  await departmentForm.getByRole('button', { name: 'Save department' }).click()
  await page.getByText('Department saved.', { exact: true }).waitFor()

  const staffingForm = page.locator('.staffing-editor .settings-form')
  await staffingForm.getByLabel('Shift category').selectOption('night')
  await staffingForm.getByLabel('Minimum staff').fill('3')
  const staffingCreatePromise = page.waitForResponse((response) => {
    const request = response.request()
    return request.method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/department-staffing-rules'
  })
  await staffingForm.getByRole('button', { name: 'Save rule' }).click()
  const staffingCreate = await staffingCreatePromise
  const staffingBody = await staffingCreate.json()
  assert.equal(staffingCreate.status(), 201)
  assert.equal(staffingBody.data.minStaff, 3)
  createdRows.staffingRules.push(staffingBody.data.id)
  await page.getByText('Staffing rule created.', { exact: true }).waitFor()

  await page.getByRole('button', {
    name: 'Phase 7E browser department: night, minimum 3',
  }).click()
  await staffingForm.getByLabel('Minimum staff').fill('4')
  await staffingForm.getByRole('button', { name: 'Save rule' }).click()
  await page.getByText('Staffing rule saved.', { exact: true }).waitFor()
  await page.getByRole('button', {
    name: 'Phase 7E browser department: night, minimum 4',
  }).click()
  await staffingForm.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', {
    name: 'Phase 7E browser department: night, minimum 4',
  }).waitFor({ state: 'detached' })

  await page.getByRole('button', { name: 'Phase 7E browser department', exact: true }).click()
  await departmentForm.getByLabel('Department head').selectOption('')
  await departmentForm.getByRole('button', { name: 'Save department' }).click()
  await page.getByText('Department saved.', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Phase 7E browser department', exact: true }).click()
  await departmentForm.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', {
    name: 'Phase 7E browser department',
    exact: true,
  }).waitFor({ state: 'detached' })
  await page.getByRole('button', { name: 'Change branch' }).click()
  await page.locator('.branch-chooser').waitFor()
  assert.equal(await page.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
}

async function assertPhase9BrowserJourney(page, persona) {
  if (persona.role === 'employee') {
    const result = await page.evaluate(async ({ payslipId }) => {
      const { authenticationSession } = await import('/src/authSession.js')
      const { createExpense } = await import('/src/expenseApi.js')
      const { createSelfAdvance } = await import('/src/advanceApi.js')
      const { readSelfPayslip, readSelfPayslips } = await import('/src/payrollApi.js')
      const authentication = authenticationSession()
      const expense = await createExpense(authentication, {
        amount: '350.00',
        category: 'Travel',
        description: 'Phase 9H synthetic browser expense',
        expenseDate: '2026-09-17',
        receiptId: null,
      })
      const advance = await createSelfAdvance(authentication, {
        amount: '1500.00',
        installmentCount: 3,
        reason: 'Phase 9H synthetic browser advance',
        repaymentStartPeriod: '2026-09',
      })
      const payslips = await readSelfPayslips(authentication)
      const payslip = await readSelfPayslip(authentication, payslipId)
      return { advance, expense, payslip, payslipCount: payslips.items.length }
    }, { payslipId: browserPayslipId })
    assert.equal(result.expense.status, 'pending')
    assert.equal(result.advance.status, 'pending')
    assert.equal(result.payslip.id, browserPayslipId)
    assert.equal(result.payslip.netPay, '12750.00')
    assert.equal(result.payslipCount, 1)
    financialJourney.expenseId = result.expense.id
    financialJourney.advanceId = result.advance.id
    return
  }

  if (persona.role === 'manager') {
    assert.ok(financialJourney.expenseId)
    const result = await page.evaluate(async ({ expenseId }) => {
      const { authenticationSession } = await import('/src/authSession.js')
      const { managerApproveExpense, readManagerExpenses } = await import('/src/expenseApi.js')
      const authentication = authenticationSession()
      const queue = await readManagerExpenses(authentication, { status: 'pending' })
      const claim = queue.items.find((item) => item.id === expenseId)
      if (!claim) throw new Error('Phase 9H expense is missing from the manager queue')
      return managerApproveExpense(authentication, claim)
    }, { expenseId: financialJourney.expenseId })
    assert.equal(result.status, 'manager_approved')
    return
  }

  assert.ok(financialJourney.expenseId)
  assert.ok(financialJourney.advanceId)
  const result = await page.evaluate(async ({ advanceId, branchId, expenseId, payrollRunId }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const { adminApproveExpense, readAdminExpenses } = await import('/src/expenseApi.js')
    const { approveAdvance, readAdminAdvances } = await import('/src/advanceApi.js')
    const { createPayrollRun, deletePayrollRun, readPayrollRun } = await import('/src/payrollApi.js')
    const {
      confirmWps,
      readNafisSnapshots,
      readSifInput,
      readWps,
      recordSifProjection,
      replaceNafisSnapshot,
      submitWps,
      updateWpsEntry,
    } = await import('/src/wpsNafisApi.js')
    const authentication = authenticationSession()
    const expenses = await readAdminExpenses(authentication, branchId, { status: 'manager_approved' })
    const claim = expenses.items.find((item) => item.id === expenseId)
    if (!claim) throw new Error('Phase 9H expense is missing from the administrator queue')
    const expense = await adminApproveExpense(authentication, branchId, claim)
    const advances = await readAdminAdvances(authentication, branchId, { status: 'pending' })
    const pendingAdvance = advances.items.find((item) => item.id === advanceId)
    if (!pendingAdvance) throw new Error('Phase 9H advance is missing from the administrator queue')
    const advance = await approveAdvance(authentication, branchId, pendingAdvance)
    const draft = await createPayrollRun(authentication, branchId, {
      paymentDate: '2026-09-25',
      period: '2026-09',
    })
    const payroll = await readPayrollRun(authentication, branchId, draft.id)
    await deletePayrollRun(authentication, branchId, payroll)
    let wps = await readWps(authentication, branchId, payrollRunId)
    const sif = await readSifInput(authentication, branchId, payrollRunId)
    wps = await recordSifProjection(authentication, branchId, wps)
    wps = await submitWps(authentication, branchId, wps, 'PHASE9H-SYNTHETIC')
    wps = await updateWpsEntry(authentication, branchId, wps, wps.entries[0], 'paid')
    wps = await confirmWps(authentication, branchId, wps)
    const nafis = await replaceNafisSnapshot(authentication, branchId, '2026-08')
    const nafisList = await readNafisSnapshots(authentication, branchId, '2026-08')
    return {
      advanceStatus: advance.status,
      expenseStatus: expense.status,
      nafisCount: nafisList.items.length,
      nafisPeriod: nafis.period,
      payrollWarnings: payroll.sourceWarnings,
      sifTotal: sif.header.totalIntegerPay,
      wpsStatus: wps.status,
    }
  }, {
    advanceId: financialJourney.advanceId,
    branchId,
    expenseId: financialJourney.expenseId,
    payrollRunId: browserPayrollRunId,
  })
  assert.equal(result.expenseStatus, 'approved')
  assert.equal(result.advanceStatus, 'active')
  assert.deepEqual(result.payrollWarnings.sort(), [
    'attendance_input_not_ready',
    'roster_input_not_ready',
  ])
  assert.equal(result.sifTotal, 12750)
  assert.equal(result.wpsStatus, 'confirmed')
  assert.equal(result.nafisPeriod, '2026-08')
  assert.equal(result.nafisCount, 1)
}

async function assertPhase10BrowserJourney(page, persona) {
  stage(`${persona.role} Phase 10 attendance and roster journey`)
  const result = await page.evaluate(async ({ role, branchId, managerId, employeeId }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const {
      readPersonalSchedule,
      readRosterColleagues,
      readRosterMonth,
      readRosterPublication,
    } = await import('/src/rosterApi.js')
    const {
      approveShiftSwap,
      readAdminShiftSwaps,
      readPersonalShiftSwaps,
      submitShiftSwap,
    } = await import('/src/shiftSwapApi.js')
    const authentication = authenticationSession()

    if (role === 'employee') {
      const schedule = await readPersonalSchedule(authentication, '2026-11')
      const colleagues = await readRosterColleagues(authentication, '2026-11-04')
      const own = schedule.find((item) => item.date === '2026-11-03')
      const target = colleagues.find((item) => item.employeeId === managerId)
      if (!own || !target) throw new Error('Phase 10J employee roster fixture is unavailable')
      const submitted = await submitShiftSwap(authentication, {
        requesterDate: own.date,
        targetEmployeeId: managerId,
        targetDate: target.date,
        reason: 'Phase 10J browser coverage exchange',
        expectedSourceVersion: own.sourceVersion,
      }, { idempotencyKey: crypto.randomUUID() })
      const personal = await readPersonalShiftSwaps(authentication, { status: 'pending' })
      return {
        scheduleCount: schedule.length,
        colleagueCount: colleagues.length,
        swapId: submitted.id,
        swapStatus: submitted.status,
        personalCount: personal.length,
      }
    }

    if (role === 'manager') {
      const schedule = await readPersonalSchedule(authentication, '2026-11')
      const personal = await readPersonalShiftSwaps(authentication, { status: 'pending' })
      return {
        scheduleCount: schedule.length,
        pendingSwapId: personal[0]?.id ?? null,
        targetEmployeeId: personal[0]?.targetEmployeeId ?? null,
      }
    }

    const { readAttendanceSettings, updateAttendanceSettings } = await import(
      '/src/attendanceConfigurationApi.js'
    )
    const {
      importBiometricCandidates,
      readBiometricMappings,
      readClockEvents,
      replaceBiometricMapping,
    } = await import('/src/attendanceIngestionApi.js')
    const settings = await readAttendanceSettings(authentication, branchId)
    const savedSettings = await updateAttendanceSettings(authentication, branchId, {
      ...settings,
      lateGraceMinutes: 11,
    }, { idempotencyKey: crypto.randomUUID() })
    await replaceBiometricMapping(authentication, branchId, 'P10J-EMPLOYEE', {
      employeeId,
      deviceName: 'Phase 10J browser reader',
    }, { idempotencyKey: crypto.randomUUID() })
    const imported = await importBiometricCandidates(authentication, branchId, {
      sourceBytes: 96,
      candidates: [{
        badgeNo: 'P10J-EMPLOYEE',
        eventType: 'CLOCK_IN',
        eventTime: '2026-09-22T04:00:00.000Z',
        deviceName: 'Phase 10J browser reader',
      }],
    }, { idempotencyKey: crypto.randomUUID() })
    const mappings = await readBiometricMappings(authentication, branchId)
    const events = await readClockEvents(authentication, branchId, { employeeId })
    const queue = await readAdminShiftSwaps(authentication, branchId, { status: 'pending' })
    if (queue.length !== 1) throw new Error('Phase 10J shift-swap queue is unavailable')
    const approved = await approveShiftSwap(authentication, branchId, queue[0], {
      idempotencyKey: crypto.randomUUID(),
    })
    const publication = await readRosterPublication(authentication, branchId, '2026-11')
    const roster = await readRosterMonth(authentication, branchId, '2026-11')
    return {
      settingsGrace: savedSettings.data.lateGraceMinutes,
      acceptedCount: imported.acceptedCount,
      mappingCount: mappings.data.length,
      eventMethods: events.data.map((item) => item.method),
      approvedSwapId: approved.id,
      approvedStatus: approved.status,
      publicationVersion: publication.version,
      rosterOwners: roster.data.map((item) => item.employeeId).sort(),
    }
  }, {
    role: persona.role,
    branchId,
    managerId: personas[1].employeeId,
    employeeId: personas[2].employeeId,
  })

  if (persona.role === 'employee') {
    assert.equal(result.scheduleCount, 1, 'employee schedule count')
    assert.equal(result.colleagueCount, 1, 'employee colleague count')
    assert.equal(result.swapStatus, 'pending', 'submitted swap status')
    assert.equal(result.personalCount, 1, 'employee pending swap count')
    phase10Journey.swapId = result.swapId
  } else if (persona.role === 'manager') {
    assert.equal(result.scheduleCount, 1, 'manager schedule count')
    assert.equal(result.pendingSwapId, phase10Journey.swapId, 'manager pending swap id')
    assert.equal(result.targetEmployeeId, personas[1].employeeId, 'manager target employee')
  } else {
    assert.equal(result.settingsGrace, 11, 'attendance grace minutes')
    assert.equal(result.acceptedCount, 1, 'accepted biometric row count')
    assert.equal(result.mappingCount, 1, 'biometric mapping count')
    assert.deepEqual(result.eventMethods, ['BIOMETRIC'], 'clock event methods')
    assert.equal(result.approvedSwapId, phase10Journey.swapId, 'approved swap id')
    assert.equal(result.approvedStatus, 'approved', 'approved swap status')
    assert.equal(result.publicationVersion, 2, 'successor publication version')
    assert.deepEqual(
      result.rosterOwners,
      [personas[1].employeeId, personas[2].employeeId].sort(),
      'post-swap roster owners',
    )
  }
}

async function browserChecks(viteServer) {
  const browser = await chromium.launch({ headless: true })
  try {
    for (const persona of [personas[2], personas[1], personas[0]]) {
      stage(`${persona.role} initial session`)
      const context = await browser.newContext({ acceptDownloads: true })
      const page = await context.newPage()
      let callbackUrl
      let leakedCallbackReferrer = null
      let tokenRequestCount = 0
      let accountRequestCount = 0
      let accountRequestsUsedBearer = true
      let healthRequestCount = 0
      let healthRequestUsedAuthorization = false
      let publicStatusRequestCount = 0
      let publicStatusUsedAuthorization = false
      let currentAccountRequestCount = 0
      let currentAccountRequestsUsedBearer = true
      let bearerLeftApiOrigin = false
      page.on('request', (request) => {
        const requestUrl = new URL(request.url())
        const authorization = request.headers().authorization
        if (authorization?.startsWith('Bearer ') && requestUrl.origin !== apiOrigin) {
          bearerLeftApiOrigin = true
        }
        if (
          requestUrl.origin === keycloakOrigin
          && requestUrl.pathname.endsWith('/protocol/openid-connect/token')
        ) {
          tokenRequestCount += 1
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/auth/token-check'
        ) {
          accountRequestCount += 1
          accountRequestsUsedBearer &&= authorization?.startsWith('Bearer ') === true
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/health'
        ) {
          healthRequestCount += 1
          healthRequestUsedAuthorization ||= Boolean(authorization)
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/public/status'
        ) {
          publicStatusRequestCount += 1
          publicStatusUsedAuthorization ||= Boolean(authorization)
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/account/me'
        ) {
          currentAccountRequestCount += 1
          currentAccountRequestsUsedBearer &&= authorization?.startsWith('Bearer ') === true
        }
        if (
          requestUrl.origin === 'http://127.0.0.1:5174'
          && requestUrl.pathname === '/oidc/callback'
          && requestUrl.searchParams.has('code')
        ) {
          callbackUrl = requestUrl.toString()
        }
        const referrer = request.headers().referer
        if (
          requestUrl.origin === 'http://127.0.0.1:5174'
          && request.resourceType() !== 'document'
          && referrer
          && new URL(referrer).searchParams.has('code')
        ) {
          leakedCallbackReferrer = `${request.resourceType()}:${requestUrl.pathname}`
        }
      })

      await page.goto('http://127.0.0.1:5174/')
      await waitForSettledStatus(page, 'signed-out', `${persona.role} initial session`)
      stage(`${persona.role} interactive login`)
      await interactiveLogin(page, persona)
      await assertSampleApi(page, persona)
      const beforeOrganizationReads = businessFingerprint()
      await assertOrganizationApi(page, persona)
      assert.equal(businessFingerprint(), beforeOrganizationReads)
      if (persona.role === 'admin') {
        await assertLeaveApprovalJourney(page, persona)
        await assertLeaveSubmissionJourney(page, persona)
      }
      await assertEmployeeApi(page, persona)
      await assertPhase9BrowserJourney(page, persona)
      await assertPhase10BrowserJourney(page, persona)
      const afterEmployeeWorkflows = businessFingerprint()
      await assertDepartmentApi(page, persona)
      assert.equal(businessFingerprint(), afterEmployeeWorkflows)
      assert.equal(accountRequestCount, 1)
      assert.ok(publicStatusRequestCount >= 1)
      assert.ok(currentAccountRequestCount >= 1)
      assert.equal(new URL(page.url()).pathname, '/')
      assert.equal(new URL(page.url()).search, '')
      stage(`${persona.role} callback captured ${Boolean(callbackUrl)}`)
      assert.ok(callbackUrl)
      stage(`${persona.role} callback referrer ${leakedCallbackReferrer ?? 'none'}`)
      assert.equal(leakedCallbackReferrer, null)
      await assertNoPersistedTokens(page)

      stage(`${persona.role} public health client`)
      const health = await page.evaluate(async () => {
        const { authenticationSession } = await import('/src/authSession.js')
        return authenticationSession().request('/health', { access: 'public' })
      })
      assert.deepEqual(health.data, { status: 'ok', database: 'ok' })
      assert.equal(healthRequestCount, 1)
      assert.equal(healthRequestUsedAuthorization, false)
      assert.equal(publicStatusUsedAuthorization, false)
      assert.equal(accountRequestsUsedBearer, true)
      assert.equal(currentAccountRequestsUsedBearer, true)
      assert.equal(bearerLeftApiOrigin, false)

      if (persona.role === 'admin') {
        stage('admin refresh-token renewal')
        const requestsBeforeRenewal = tokenRequestCount
        const accountRequestsBeforeRenewal = accountRequestCount
        await page.evaluate(async () => {
          const { authenticationSession } = await import('/src/authSession.js')
          await authenticationSession().renew()
        })
        await waitForStatus(page, 'signed-in')
        assert.equal(tokenRequestCount, requestsBeforeRenewal + 1)
        assert.equal(accountRequestCount, accountRequestsBeforeRenewal + 1)
        await assertNoPersistedTokens(page)
      }

      stage(`${persona.role} session restoration`)
      const accountRequestsBeforeRestoration = accountRequestCount
      const currentAccountRequestsBeforeRestoration = currentAccountRequestCount
      await page.reload()
      await waitForStatus(page, 'signed-in')
      await assertSampleApi(page, persona)
      assert.equal(accountRequestCount, accountRequestsBeforeRestoration + 1)
      assert.ok(currentAccountRequestCount > currentAccountRequestsBeforeRestoration)
      await assertNoPersistedTokens(page)

      if (persona.role === 'manager') {
        await assertLeaveApprovalJourney(page, persona)
        stage('manager changed email')
        kcadm([
          'update', `users/${persona.identityId}`, '-r', 'workloop-dev',
          '-s', 'email=phase-3g-manager-changed@example.test',
        ])
        await page.reload()
        await waitForStatus(page, 'signed-in')
      }

      if (persona.role === 'employee') {
        await assertLeaveAttachmentJourney(page)
        await assertLeaveSubmissionJourney(page, persona)
        stage('employee disablement')
        psql(
          "UPDATE app_users SET status = 'disabled' WHERE id = :'app_user_id'",
          { app_user_id: persona.appUserId },
        )
        const disabledRead = await page.evaluate(async () => {
          const { authenticationSession } = await import('/src/authSession.js')
          try {
            await authenticationSession().request('/api/v1/employer', { access: 'protected' })
          } catch (error) {
            return { code: error.code, status: error.status }
          }
          return null
        })
        assert.deepEqual(disabledRead, { code: 'application_account_unavailable', status: 403 })
        await page.reload()
        await waitForStatus(page, 'account-unavailable')
      }

      stage(`${persona.role} logout`)
      await page.getByRole('button', { name: 'Sign out' }).click()
      await waitForStatus(page, 'signed-out')
      await page.reload()
      await waitForStatus(page, 'signed-out')

      if (persona.role === 'admin') {
        stage('callback replay rejection')
        await page.goto(callbackUrl)
        await waitForStatus(page, 'error')
        await assertNoPersistedTokens(page)
        stage('wrong state rejection')
        const wrongState = new URL(callbackUrl)
        wrongState.searchParams.set('state', 'invalid-state')
        await page.goto(wrongState.toString())
        await waitForStatus(page, 'error')
        await assertNoPersistedTokens(page)
      }
      assert.equal(accountRequestsUsedBearer, true)
      assert.equal(healthRequestUsedAuthorization, false)
      assert.equal(publicStatusUsedAuthorization, false)
      assert.equal(currentAccountRequestsUsedBearer, true)
      assert.equal(bearerLeftApiOrigin, false)
      await context.close()
      if (persona.role === 'employee') {
        stage('employee fixture account restoration')
        psql(
          "UPDATE app_users SET status = 'active' WHERE id = :'app_user_id'",
          { app_user_id: persona.appUserId },
        )
      }
    }

    stage('wrong nonce rejection')
    const nonceContext = await browser.newContext()
    const noncePage = await nonceContext.newPage()
    await noncePage.goto('http://127.0.0.1:5174/')
    await waitForStatus(noncePage, 'signed-out')
    await noncePage.evaluate(() => {
      const originalSetItem = Storage.prototype.setItem
      Storage.prototype.setItem = function setItem(key, value) {
        if (this === sessionStorage && key.startsWith('workloop.oidc.')) {
          const transactionState = JSON.parse(value)
          if (typeof transactionState.nonce === 'string') {
            transactionState.nonce = 'invalid-nonce'
            return originalSetItem.call(this, key, JSON.stringify(transactionState))
          }
        }
        return originalSetItem.call(this, key, value)
      }
    })
    await noncePage.getByRole('button', { name: 'Sign in' }).click()
    stage('wrong nonce login callback')
    await noncePage.locator('#username').fill(personas[0].userName)
    await noncePage.locator('#password').fill(personas[0].password)
    await noncePage.locator('#kc-login').click()
    await noncePage.waitForFunction(
      () => {
        const status = document.querySelector('main')?.dataset.sessionStatus
        return status && status !== 'loading'
      },
      undefined,
      { timeout: 20_000 },
    )
    const nonceStatus = await noncePage.locator('main').getAttribute('data-session-status')
    stage(`wrong nonce rejection ${nonceStatus}`)
    assert.equal(nonceStatus, 'error')
    await assertNoPersistedTokens(noncePage)
    await nonceContext.close()
  } finally {
    await browser.close()
    await viteServer.close()
  }
}

async function main() {
  let fixturesCreated = false
  let viteServer
  let primaryError
  try {
    stage('synthetic fixture creation')
    fixturesCreated = true
    createFixtures()
    Object.assign(process.env, {
      VITE_API_BASE_URL: apiBaseUrl,
      VITE_OIDC_AUTHORITY: issuer,
      VITE_OIDC_CLIENT_ID: 'workloop-migration-web',
      VITE_OIDC_REDIRECT_URI: 'http://127.0.0.1:5174/oidc/callback',
      VITE_OIDC_POST_LOGOUT_REDIRECT_URI: 'http://127.0.0.1:5174/',
      VITE_OIDC_AUDIENCE: 'workloop-api',
    })
    stage('migration server startup')
    viteServer = await createServer({
      configFile: path.join(root, 'migration', 'vite.migration.config.js'),
      envFile: false,
      logLevel: 'silent',
    })
    await viteServer.listen()
    stage('browser checks')
    await browserChecks(viteServer)
    viteServer = undefined
  } catch (error) {
    primaryError = error
    throw error
  } finally {
    if (viteServer) await viteServer.close()
    if (fixturesCreated) {
      try {
        cleanupFixtures()
      } catch (error) {
        if (!primaryError) throw error
        console.error(
          `Phase 3G browser cleanup failed: ${error instanceof Error ? error.message : 'unknown error'}`,
        )
      }
    }
  }

  console.log('Phase 3G browser checks passed')
}

main().catch((error) => {
  console.error(`Phase 3G browser checks failed at ${activeStage}`)
  console.error(error instanceof Error ? error.message : 'Unknown browser check failure')
  process.exitCode = 1
})

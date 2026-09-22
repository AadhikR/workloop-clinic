# Part 11A dependency inventory

## Scope and method

This inventory reconciles the Phase 0 feature matrix, the Phase 4 schema catalogue, the Phase 5
permission design, the Phase 8 private-file implementation, the Phase 9 financial contract, and the
repository at commit `ce2f788fb4d4646271e0ca58cea1aa4cd5b649bf`. It covers Phase 11 storage,
documents, benefits, contracts, assets, training, certifications, CME, appraisals, incidents,
requests, offboarding, and final settlement. Every dependency below has an owner in 11B through 11G,
Phase 12, or Phase 13.

## Common storage and recovery

| ID | Source | Current contract | Owner and disposition |
| --- | --- | --- | --- |
| `P11-STO-01` | `backend/app/storage/base.py` | Provider-neutral put, get, head, delete, conditional create, and signed download interface | 11B retains and extends it with bounded streaming and malware scan coordination. |
| `P11-STO-02` | `backend/app/storage/synthetic.py` | Persistent filesystem provider with encrypted five-minute download tokens | 11B retains it for synthetic restart, backup, and restore proof. |
| `P11-STO-03` | `backend/app/storage/spaces.py` | S3-compatible conditional create, metadata, bounded get, and signed download adapter | 11B tests it against a local S3-compatible service. No DigitalOcean resource is authorized. |
| `P11-STO-04` | `backend/app/storage/factory.py`; `backend/app/core/config.py` | Disabled, synthetic, and Spaces selection with secret validation | 11B adds scanner and backup settings. Secrets remain server-only. |
| `P11-STO-05` | `backend/app/models/storage.py`; revision `4d8a7c2e9f31` | Durable `storage_operations` queue, eight attempt limit, leases, retry schedule, and terminal failure | 11B retains the state machine and adds no retry of upload bytes. |
| `P11-STO-06` | `backend/app/storage/reconciler.py` | Delete retry, upload-orphan cleanup, exhausted-lease terminalization, and 90-day successful-row purge | 11B adds missing-object classification, operator inspection, and approved manual requeue without widening business-table access. |
| `P11-STO-07` | `backend/app/services/leave_attachment.py`; `leave_attachments` | Phase 8 file validation, upload intent, private signing, cleanup, and metadata | 11B adds scan release and recovery proof. Phase 8 permissions remain unchanged. |
| `P11-STO-08` | `backend/app/services/expense_receipt.py`; `expense_receipts` | Phase 9 receipt validation, upload intent, private signing, cleanup, and metadata | 11B adds scan release and recovery proof. Phase 9 permissions remain unchanged. |
| `P11-STO-09` | `scripts/verify-phase-8d-storage-restart.py`; `backend/tests/test_storage.py` | Existing restart and provider contract proof | 11B extends it for local S3, scan state, backup, restore, and credential rotation. |
| `P11-STO-10` | `employee-documents` Supabase bucket | Legacy document, training, and certification bytes share one bucket | 11C and 11D replace these paths. Phase 13 removes the final Supabase dependency. |

## Employee documents, insurance, and contracts

| ID | Source | Readers and writers | Owner and disposition |
| --- | --- | --- | --- |
| `P11-DOC-01` | `src/utils/storage.js` | `getEmployeeDocuments`, `getAllEmployeeDocuments`, upload, signed read, verify, reject, and delete | 11C replaces all operations with scoped FastAPI routes and the 11B file contract. |
| `P11-DOC-02` | `src/utils/profileStorage.js` | `getMyDocuments` reads employee document metadata directly | 11C replaces it with the employee-self projection. |
| `P11-DOC-03` | `src/components/employee/EmpDocuments.jsx` | Direct bucket upload and `employee_submit_document` RPC | 11C replaces both and freezes the RPC and bucket path. |
| `P11-DOC-04` | `src/components/EmployeeModal.jsx` | Administrator document upload, review, signing, and deletion | 11C replaces the Documents tab. |
| `P11-DOC-05` | `employee_documents`; Phase 4 and 5 rules | Branch admin plus employee self scope, pending employee submissions, trusted verified admin creation, retained verified rows | 11C keeps these rules and adds private-file metadata and scan linkage. |
| `P11-INS-01` | `src/utils/storage.js` | Policy CRUD, all coverage reads, employee coverage replacement, and dependant CRUD | 11C replaces these calls with selected-branch routes. |
| `P11-INS-02` | `src/components/CompanySettings.jsx` | Policy maintenance | 11C replaces the insurance section. Phase 12 owns renewal notifications. |
| `P11-INS-03` | `src/components/EmployeeModal.jsx` | Coverage and dependant maintenance | 11C replaces the Insurance tab. |
| `P11-INS-04` | `insurance_policies`; `employee_insurance`; `insurance_dependants` | Branch policy, one current employee coverage, linked self read, admin-only dependant access | 11C retains the Phase 4 and 5 ownership rules and adds optimistic-lock fields. |
| `P11-CON-01` | `src/utils/storage.js` | `getEmployeeContracts` and generic `saveEmployeeContract` | 11C replaces the generic writer with named new, renew, convert, and non-renew commands. |
| `P11-CON-02` | `src/components/EmployeeModal.jsx` | Contract history, renewal, conversion, and non-renewal controls | 11C replaces the Contracts tab. |
| `P11-CON-03` | `employee_contracts`; `employees`; `employee_job_history` | Append-only events plus current employee contract fields | 11C uses one transaction owner and keeps prior events immutable. |

## Assets, training, certifications, and CME

| ID | Source | Readers and writers | Owner and disposition |
| --- | --- | --- | --- |
| `P11-AST-01` | `src/utils/assetStorage.js` | Asset CRUD, assignment, return, history, and employee current assets | 11D replaces the module. |
| `P11-AST-02` | `src/components/AssetsManager.jsx` | Administrator inventory and custody | 11D replaces the screen. |
| `P11-AST-03` | `src/components/employee/EmpHome.jsx` | Employee current asset summary | 11D supplies a safe self projection. Phase 12 may move the summary into a dashboard. |
| `P11-AST-04` | `assets`; `asset_assignments` | Unique nonempty branch code, one open assignment, retained assignment history | 11D keeps these invariants and adds optimistic locking. |
| `P11-TRN-01` | `src/utils/trainingStorage.js` | Administrator, manager, and employee training and certification CRUD; file upload and signing; CME targets and totals | 11D replaces every database and bucket call. |
| `P11-TRN-02` | `src/components/TrainingManager.jsx` | Administrator training, certification, file, and CME maintenance | 11D replaces the screen. |
| `P11-TRN-03` | `src/components/manager/ManagerTraining.jsx` | Manager self and direct-report maintenance | 11D replaces it under the Phase 5 `M1` boundary. |
| `P11-TRN-04` | `src/components/employee/EmpTraining.jsx` | Employee self-enrolment, certification submission, upload, and signed read | 11D replaces it. Non-admin certifications remain pending. |
| `P11-TRN-05` | `training_records`; `certifications`; `cme_requirements` | Trusted completion, verified evidence retention, and per-employee yearly target | 11D retains the Phase 4 and 5 rules, adds scan linkage, and calculates achieved hours on the server. |

## Appraisals and incidents

| ID | Source | Readers and writers | Owner and disposition |
| --- | --- | --- | --- |
| `P11-APP-01` | `src/utils/appraisalStorage.js` | Cycle CRUD, employee and team reads, section ratings, generation, review, calibration, and delete | 11E replaces the module. Hard appraisal delete stays unsupported. |
| `P11-APP-02` | `src/components/AppraisalManager.jsx` | Administrator cycle, generation, review, calibration, and close flows | 11E replaces the screen. |
| `P11-APP-03` | `src/components/manager/ManagerAppraisals.jsx` | Manager direct-report ratings and manager self history | 11E replaces it under `M1` and `E1`. |
| `P11-APP-04` | `src/components/employee/EmpAppraisal.jsx` | Employee self history | 11E replaces it. Self-rating is not approved. |
| `P11-APP-05` | `appraisal_cycles`; `appraisals`; `appraisal_sections` | Draft, active, and closed cycles; pending, reviewed, and calibrated appraisals; parent locking through `updated_at` | 11E retains the schema and fixes the section template and weighted calculation contract. |
| `P11-INC-01` | `src/utils/incidentStorage.js` | Branch filter, generic create or update, and hard delete | 11E replaces it with named create, investigate, corrective-action, and close commands. Hard delete is frozen. |
| `P11-INC-02` | `src/components/IncidentManager.jsx` | Administrator incident list and editor | 11E replaces the screen. |
| `P11-INC-03` | `incident_reports`; joined employees and departments | Sensitive clinical history with branch-scoped employee references | 11E retains every created report and adds safe, versioned workflows. |

## Letter and custom requests

| ID | Source | Readers and writers | Owner and disposition |
| --- | --- | --- | --- |
| `P11-REQ-01` | `src/utils/letterStorage.js` | Admin queue, pending count, complete, reject, and employee history | 11F replaces the module. |
| `P11-REQ-02` | `src/components/employee/EmpRequests.jsx` | Direct `employee_request_letter` and `employee_request_custom` RPC calls plus completed-letter printing | 11F replaces submission and reads. Phase 12 owns rendered bytes. |
| `P11-REQ-03` | `src/components/LetterRequestsManager.jsx` | Administrator queue, decision, and print action | 11F replaces queue and decisions. |
| `P11-REQ-04` | `src/utils/letterTemplates.js`; `src/utils/safePrint.js` | Browser HTML generation and print window | Phase 12 owns output rendering. 11F exposes a strict completed-request source projection only. |
| `P11-REQ-05` | `letter_requests`; employee and employer fields | Self submission and history, selected-branch admin decisions, retained final states | 11F keeps the Phase 4 and 5 state and scope rules. |

## Offboarding and final settlement

| ID | Source | Readers and writers | Owner and disposition |
| --- | --- | --- | --- |
| `P11-OFF-01` | `src/utils/storage.js` | Checklist load and seed, task toggle and add, unsupported custom-task delete, visa state, and completion | 11G replaces the module. Task deletion remains unavailable until provenance exists. |
| `P11-OFF-02` | `src/components/OffboardingModal.jsx` | Checklist execution, visa state, NOC and experience-letter HTML, and completion that can bypass required tasks | 11G replaces checklist actions and rejects incomplete completion. Phase 12 owns letter bytes. |
| `P11-OFF-03` | `src/components/EndOfServiceScreen.jsx` | Browser final salary, gratuity, leave encashment, advance deduction, and print | 11G replaces calculation only after the project owner approves the legal and policy inputs. Phase 12 owns print bytes. |
| `P11-OFF-04` | `src/utils/gratuityCalculator.js`; `src/utils/leaveEngine.js` | Conflicting browser legal assumptions, floating-point arithmetic, and no immutable source snapshot | 11G freezes these calculators. Their formulas are evidence of legacy behavior, not an approved contract. |
| `P11-OFF-05` | `src/utils/reportUtils.js` | EOS liability report calls the legacy gratuity calculator | Phase 12 owns the report and may consume only the approved 11G projection. |
| `P11-OFF-06` | `offboarding_checklists`; `offboarding_tasks`; `offboarding_task_templates` | Selected-branch workflow, retained completion, and seed-owned templates | 11G adds durable task provenance and final settlement linkage. |
| `P11-OFF-07` | Phase 7 employee lifecycle | Trusted employment state, termination date, salary, allowances, contract fields, and job history | 11G consumes a locked projection and invokes the named Phase 7 termination workflow. |
| `P11-OFF-08` | Phase 8 leave balance | Approved annual-leave balance and source version | 11G consumes a strict read-only projection after the owner approves encashment policy. |
| `P11-OFF-09` | Phase 9 payroll, advances, and repayments | Finalized pay snapshot and exact outstanding advance balance | 11G consumes immutable source identities. It does not rewrite Phase 9 rows. |
| `P11-OFF-10` | Phase 11 contracts and assets | Current contract outcome and open asset custody | 11G blocks completion on approved contract or return rules. |

## Indirect consumers and later owners

| ID | Source | Dependency | Owner and disposition |
| --- | --- | --- | --- |
| `P11-LTR-01` | `src/components/Dashboard.jsx`; `ClinicalDashboard.jsx` | Document, insurance, certification, request, and appraisal cards | Phase 12 replaces these reads with named projections. |
| `P11-LTR-02` | `src/utils/taskStorage.js`; `TasksPanel.jsx` | Requests, documents, certifications, contracts, offboarding, and appraisals | Phase 12 replaces task aggregation. Stale `doc_type` and payroll columns are not copied. |
| `P11-LTR-03` | `src/utils/notificationStorage.js`; `NotificationBell.jsx` | Expiry and workflow notifications | Phase 12 owns producers and presentation. No Phase 11 command inserts a notification. |
| `P11-LTR-04` | `src/components/Reports.jsx`; `src/utils/reportUtils.js` | Document, asset, training, incident, request, appraisal, and EOS reports and exports | Phase 12 owns all reports, CSV, PDF, ZIP, and print bytes. |
| `P11-LTR-05` | Supabase client, RPCs, bucket, and retained legacy components | Final legacy runtime dependency | Phase 13 removes it only after every cutover is complete. |

## Cutover and freeze order

The cutover units are common storage recovery, employee documents, insurance, employment contracts,
assets, training and certifications with CME, appraisals, clinical incidents, letter requests, and
offboarding with final settlement. Each starts in `preparation` with legacy Supabase as the sole read
and write authority. No 11A record changes authority.

Rollback reverses dependencies: offboarding and final settlement, letter requests, clinical
incidents, appraisals, training and certifications with CME, assets, employment contracts,
insurance, employee documents, then common storage recovery. Common storage cannot roll back while
any Phase 8, 9, or 11 file consumer depends on it. The inventory has no unexplained dependency.

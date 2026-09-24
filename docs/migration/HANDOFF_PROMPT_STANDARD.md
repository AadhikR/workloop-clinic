# Phase part handoff prompt standard

This document defines the handoff from one migration part to the next. The completed part generates
the prompt and starts a new Codex task automatically. Read
`docs/migration/PHASE_EXECUTION_WORKFLOW.md` first.

A handoff is an execution brief. It is not a new approval request, a copy of the migration plan, or
a reason to keep working in the completed task.

## Source of truth

Before writing the prompt:

1. Read `AGENTS.md`, `docs/migration/PHASE_EXECUTION_WORKFLOW.md`, and the current phase plan.
2. Inspect the branch, commit, working tree, upstream synchronization, Alembic head, and latest
   required GitHub result.
3. Read the completion record for the part that just ended.
4. Read the approved design documents that govern the next part.
5. Identify the next part's changes, decision boundaries, rollback order, and prohibited work.
6. Check whether a machine-readable catalogue already names the affected objects and operations.

Reference canonical files by path. Do not repeat their full tables, test inventories, or design
arguments. Include an exact object list only when it defines the next part's change or no canonical
catalogue exists.

The prompt must describe verified repository state. If the branch is dirty, a required GitHub job
failed, or the predecessor is incomplete, fix that condition before creating the next task.

## Required prompt sections

Use these sections in order.

### Active authorization and task boundary

Name the current phase's standing authorization and the one part assigned to the new task. State
that the owner already authorized this part when Part A started. Tell the new task to begin
immediately without asking for approval.

Name the following part. If one exists, require this task to create it automatically after the
current part passes. If this is the final part, require whole-phase signoff and prohibit starting the
next phase.

### Starting state

Record only facts needed to resume work:

- branch and full commit;
- clean working-tree and upstream synchronization state;
- Alembic or schema head when relevant;
- latest successful required GitHub run;
- completed prerequisite parts; and
- preserved resources that must not change.

### Read before implementation

List the smallest set of canonical files needed for the part. Include the current phase plan,
governing design or catalogue, latest completion record, `AGENTS.md`, and the two workflow documents.

### Part delta

Describe only what this part adds, changes, or removes. Name exact tables, services, routes, roles,
migrations, or artifacts when their identity controls scope. Point to the governing design for
unchanged rules.

Separate required work from prohibited work. The task should decide routine policy, product,
feature-scope, and review questions itself. It must choose the smallest fail-closed option and record
the reason. Do not ask the owner to choose among recommended options.

### Deliverables

Name the concrete outputs. Examples include migration revisions, services, frontend clients,
focused verifiers, cutover records, or a completion record. Do not invent helpers or files when the
approved design does not need them.

### Verification by layer

Group checks by the boundary they prove:

- catalogue and schema;
- database, RLS, grants, and protected functions;
- application and repository behavior;
- affected regressions;
- the boundary-matched local gate; and
- routed GitHub checks.

Reference existing scripts instead of copying their cases. State only new cases, known gaps, and
part-specific success or denial behavior. Do not claim that a catalogue test proves a business
workflow.

### Execution order

Use this order unless the phase plan requires another sequence:

1. Perform a read-only preflight and resolve revision IDs, fixture IDs, ports, volumes, and
   ownership.
2. Create the focused verifier or catalogue skeleton before broad implementation.
3. Implement one bounded unit and run its focused checks.
4. Repeat for the remaining units.
5. Run one boundary-matched local gate after the code settles.
6. If the gate fails, reproduce and fix the failure with focused checks, then rerun the gate once.
7. Update the completion record, commit, and push according to the source-control instruction.
8. Wait for every required GitHub job and fix any failure.
9. Confirm a clean synchronized branch.
10. Generate the next handoff and create its Codex task automatically. If this is the final part,
    request whole-phase signoff instead.

Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Do not rerun unaffected suites. A
documentation-only follow-up after a passing code gate does not repeat that gate.

### Resource and data boundaries

State the allowed data class, environment, network access, cloud cost, credential handling, and
cleanup rule. Name preserved volumes or services exactly. Use an isolated environment when the
verification workflow or phase plan requires it.

### Completion and automatic continuation

Define the evidence that closes this part. Require a clean synchronized branch. Name the completion
record and the exact next part.

For a nonfinal part, tell the task to create the next Codex task in the same saved project and local
checkout, pass it the generated handoff, start it immediately, report the task, and stop. For the
final part, tell the task to request phase signoff and stop before the next phase.

## Efficiency and source control

Keep the handoff prompt under 900 words. Aim for 500 to 700 words.

- Do not paste content that already exists in a canonical file.
- Keep successful command output quiet and preserve complete failure details.
- Run focused checks while editing and one final local gate after code settles.
- Do not repeat a passing code gate for a documentation-only edit.
- Prefer one local commit per independently reviewable migration or domain and one push after the
  final local gate.
- Put the successful workflow URL in the handoff. Do not make a second commit only to store it.
- Make cleanup idempotent and verify exact disposable targets before removal.
- Report GitHub status changes instead of narrating unchanged polls.

## Prompt template

Replace bracketed fields and remove instructions that do not apply.

```text
# Phase [part ID] execution handoff

The project owner authorized Phase [phase ID] from [phase ID]A through [final part] when Part A
started. This handoff is already authorized. Begin Part [part ID] immediately without asking for
approval. Work only on Part [part ID] in this Codex task.

After Part [part ID] passes, generate the handoff for Part [next part ID], create a new Codex task in
the same saved project and local checkout, and start it automatically. Do not implement Part
[next part ID] in this task.

## Starting state

- Branch: [branch]
- Commit: [full commit]
- Working tree and upstream: [verified state]
- Alembic or schema head: [head]
- Latest required GitHub run: [URL and result]
- Completed prerequisites: [parts]
- Preserved resources: [exact names and restrictions]

## Read before implementation

- AGENTS.md
- docs/migration/PHASE_EXECUTION_WORKFLOW.md
- docs/migration/HANDOFF_PROMPT_STANDARD.md
- docs/migration/VERIFICATION_WORKFLOW.md
- [current phase plan]
- [governing design, catalogue, and latest completion record]

## Part [part ID] delta

[Describe only the new work and exact boundaries.]

Make routine policy, design, review, and feature-scope decisions without asking the owner. Choose
the smallest fail-closed option inside the approved phase and record the reason. Do not add
[explicit exclusions].

## Deliverables

- [artifact]
- [artifact]
- [completion record]

## Verification by layer

- Catalogue and schema: [checks]
- Database and security: [checks]
- Application and repository: [checks]
- Regressions: [affected suites]
- Final local gate: [required proof]
- GitHub: [workflow and required result]

## Execution order

Perform the read-only preflight. Build the focused verifier first. Implement and test bounded units.
Run one final local gate. Fix failures with focused checks and repeat that gate once. Update the
completion record, commit, push once, and wait for every routed GitHub job.

## Resource and data boundaries

[Synthetic data, isolated resources, preserved resources, cloud-cost limits, secrets, and cleanup.]

## Completion and automatic continuation

[Exact completion evidence.] End with a clean synchronized branch. Generate Part [next part ID]'s
handoff, create its Codex task in the same saved project and local checkout, start it immediately,
report the created task, and stop this task. No owner approval is required between parts.
```

For the final part, replace the opening continuation paragraph and final section with this rule:

```text
This is the final part of Phase [phase ID]. After every local and GitHub gate passes, record the
complete phase result and request one project-owner signoff. Do not create or start Phase [next
phase ID].
```

## Final review checklist

Before creating the next task, confirm that the prompt:

- uses verified branch, commit, schema, and workflow facts;
- says the part is already authorized and starts immediately;
- assigns exactly one part to the new task;
- gives Codex routine decision authority without a recommendation pause;
- contains the part's changes without copying canonical documents;
- assigns each check to the boundary it proves;
- names preserved resources and cleanup behavior;
- requires automatic creation of the following part's task, or final phase signoff;
- keeps the next phase unauthorized after the final part; and
- stays within the default length limit.

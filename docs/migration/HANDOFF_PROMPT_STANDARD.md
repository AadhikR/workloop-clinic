# Phase handoff prompt standard

This document defines how to write a handoff prompt for the next migration phase. It keeps the
prompt short enough to use as working context while preserving the decisions and checks that protect
the project.

Use this standard whenever the project owner asks for a "handoff prompt for the next phase" or a
similar phase-transition prompt.

## Source of truth

A handoff prompt is an execution brief. It is not a copy of the migration plan, permission matrix,
completion record, workflow, or test scripts.

Before writing the prompt:

1. Read `AGENTS.md` and the current phase plan.
2. Inspect the current branch, commit, working-tree state, Alembic head, and latest GitHub result.
3. Read the completion record for the phase that just ended.
4. Read the approved design documents that govern the next phase.
5. Identify the next phase's changes, unresolved decisions, rollback boundary, and prohibited work.
6. Check whether a machine-readable catalogue already names the affected objects and operations.

Reference canonical documents by path. Do not repeat their full tables, test inventories, or design
arguments. Include an exact object list only when the list is the phase-specific change or when no
canonical catalogue exists.

The prompt must describe the repository state that was verified, not an assumed state. If the branch
is dirty, the GitHub run failed, or an owner decision remains open, say so plainly.

## Required prompt sections

Use these sections in this order.

### Authorization boundary

State the phase that the owner may authorize. State that later phases remain unauthorized. A handoff
prompt does not grant authorization by itself unless the project owner explicitly asks it to do so.

### Starting state

Record only facts needed to resume work:

- branch;
- commit;
- working-tree and synchronization state;
- schema or Alembic head when relevant;
- latest successful GitHub run;
- completed prerequisite phases; and
- preserved local or remote resources that must not be changed.

### Canonical sources

List the smallest set of files the next phase must read. Prefer the current plan, approved design,
latest completion record, and any exact machine-readable catalogue. Do not list old records that the
current documents already supersede.

### Phase delta

Describe only what the next phase adds, changes, or removes. Name exact tables, services, routes,
roles, migrations, or artifacts when their identity controls scope. Point to the governing design
for unchanged rules.

Separate required work from prohibited work. Call out any condition that requires the agent to stop
for project-owner review.

### Deliverables

Name the concrete outputs expected from the phase. Examples include migration revisions, application
modules, focused verification scripts, completion records, or deployment evidence. Do not prescribe
new helpers or files unless the approved design requires them.

### Verification by layer

Group checks by the boundary they prove:

- catalogue and schema checks;
- direct database or RLS checks;
- protected-function checks;
- application and repository checks;
- affected regression checks;
- final clean-environment checks; and
- GitHub checks.

Reference existing scripts instead of copying their cases. State only new cases, known gaps, and
phase-specific success or denial behavior.

Do not claim that a catalogue check proves a business workflow. Do not require an RLS-only phase to
simulate route or service behavior that does not exist yet. Mark those checks as deferred to the
phase that adds the consumer.

### Execution order

Use this default order unless the phase plan requires something else:

1. Perform a read-only preflight and resolve revision IDs, fixture IDs, ports, volumes, and
   ownership.
2. Create the expected catalogue or verifier skeleton before the implementation grows large.
3. Implement one bounded unit, such as one migration or service boundary.
4. Run focused checks for that unit.
5. Repeat for the remaining units.
6. After phase code settles, run one complete local gate in a fresh isolated environment.
7. If the final gate fails, reproduce and fix the failure with focused checks, then rerun the final
   gate once.
8. Update the completion record after the implementation and evidence are stable.
9. Commit and push according to the phase's explicit source-control instruction.
10. Wait for the workflow result and report the final URL.

Run unaffected full suites locally only when the change can reach them or the phase plan explicitly
requires them. Follow `docs/migration/VERIFICATION_WORKFLOW.md` for path-based GitHub routing. A
documentation-only edit after a passing phase gate does not require another local or GitHub full-stack
run.

### Resource and data boundaries

State the allowed data class, environment, network access, cloud cost, credential handling, and
cleanup rule. Name preserved volumes or services exactly. Use one isolated environment for the final
gate and remove it only after recording the required evidence.

### Completion and stop condition

Define the evidence that closes the phase. Require a clean and synchronized branch when applicable.
State where the completion record lives, whether the GitHub run belongs in the file or the handoff,
and where work must stop.

## Efficiency rules

Keep the generated handoff prompt under 900 words by default. Aim for 500 to 700 words. Exceed that
only when the phase contains unresolved owner decisions that must appear directly in the prompt.

Use these rules to control token and execution cost:

- Do not paste content that already exists in a canonical repository file.
- Do not repeat unchanged security rules in several sections.
- Prefer one exact catalogue over prose lists repeated in design, implementation, and verification.
- Keep routine successful command output quiet. Preserve full failure output.
- Run focused checks while editing and one complete local gate after the code settles.
- Treat that complete gate as the phase-code completion gate. Do not repeat it for later
  documentation-only commits.
- Do not rerun frontend, browser, cloud, or full-stack checks locally when the changed files cannot
  affect them, unless the phase plan requires the run.
- Use synthetic identifiers from a reserved namespace and check them for collisions before database
  setup.
- Make verification cleanup idempotent and test cleanup order before the final gate.
- Validate the effective Compose configuration before starting an isolated database.
- Report GitHub status changes instead of repeatedly emitting unchanged polling results.

When parallel agents are explicitly authorized, use them for independent, bounded review or for
separate domains with no shared files. Do not use parallel agents for the same migration or
verifier. Parallel work usually spends more tokens, so use it when review independence or elapsed
time matters more than token cost.

## Source-control guidance

Prefer one local commit per independently reviewable migration or domain and one push after the
final local gate. This gives reviewers useful history without triggering several GitHub runs.
Follow an explicit owner request for a single commit or another history shape.

The path-routed GitHub workflow must use the lightweight validation path for documentation-only
follow-ups. Code changes must use the checks assigned by `docs/migration/VERIFICATION_WORKFLOW.md`.

Do not make a second commit only to add a successful workflow URL. Put that URL in the task handoff
unless the phase plan says otherwise.

## Prompt template

Use the following structure. Replace bracketed fields with verified facts and remove instructions
that do not apply.

```text
# Phase [ID] handoff

This prompt prepares Phase [ID]. It does not authorize Phase [ID] or any later phase. Begin only
after the project owner explicitly authorizes Phase [ID]. Stop before Phase [next ID].

## Starting state

- Branch: [branch]
- Commit: [full commit]
- Working tree: [clean or exact exception]
- Alembic or schema head: [head]
- Latest GitHub run: [URL and result]
- Completed prerequisites: [phases]
- Preserved resources: [exact names and restrictions]

## Read before implementation

- [current plan]
- [governing design or catalogue]
- [latest completion record]
- [other file needed for this phase only]
- AGENTS.md

## Phase [ID] delta

[Describe only the new work and exact objects in scope. Reference the governing design for rules
that do not change.]

Do not add or change [explicit exclusions]. Stop for project-owner review if [decision conditions].

## Deliverables

- [concrete artifact]
- [concrete artifact]
- [completion record]

## Verification by layer

- Catalogue and schema: [new assertions or existing verifier references]
- Database or RLS: [new allow and deny cases]
- Protected functions: [new success, denial, and unchanged-state cases]
- Application and repository: [affected checks]
- Regressions: [affected suites only]
- Final gate: [fresh isolated environment and rollback or restart proof]
- GitHub: [workflow and required conclusion]

Checks that require consumers not added in this phase are deferred to [phase].

## Execution order

Perform a read-only preflight. Build the verifier skeleton first. Implement and test each bounded
unit. Run one complete local gate after the code settles. Fix failures with focused checks, then
repeat the final gate once. Update the completion record, commit, push once, and report the final
workflow URL.

## Resource and data boundaries

[Synthetic data, isolated volume, preserved resources, cloud-cost limit, secrets, and cleanup.]

## Completion and stop condition

[Exact completion evidence.] Record completion in [path]. End with a clean synchronized branch and
stop before Phase [next ID].
```

## Final review checklist

Before returning a handoff prompt, confirm that it:

- uses verified branch, commit, schema, and workflow facts;
- distinguishes preparation from authorization;
- contains the next phase's changes without copying its governing documents;
- assigns every test to the boundary it proves;
- requests focused development checks and one final clean gate;
- names preserved resources and cleanup behavior;
- states the commit and push policy;
- has an explicit stop boundary; and
- stays within the default length limit.

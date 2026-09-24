# Migration phase execution workflow

This document controls how Codex runs every remaining migration phase. It supersedes older process
language that required separate authorization for each part or kept several parts in one task.
Historical completion records still describe what happened at the time. They do not control future
execution.

## One approval starts the whole phase

When the project owner starts Part A of a phase, that instruction authorizes every listed part of
that phase through its final review and completion gate. For example, authorization to start 12A
also authorizes 12B through the last Phase 12 part.

Do not ask the owner to approve the next part. Do not present recommended features for approval
during the phase. Do not treat a handoff prompt as a new authorization gate. The only routine owner
approval after Part A is the signoff requested after the whole phase passes.

This standing authorization covers repository changes, synthetic local verification, completion
records, commits, pushes, routed GitHub checks, and creation of the next Codex task. It does not
expand the phase's stated resource and data boundaries.

## One Codex task per part

Each part runs in its own Codex task. Do not implement two parts in the same task.

After a part passes its required local and GitHub checks:

1. Confirm the branch is clean, synchronized, and still on the approved migration branch.
2. Generate the next part's prompt from verified repository state by following
   `docs/migration/HANDOFF_PROMPT_STANDARD.md`.
3. Create a new Codex task automatically in the same saved project and local checkout. The new task
   must start from the synchronized branch that contains the completed part.
4. Put the generated handoff prompt in that task and start it immediately.
5. Report the created task, then stop work in the completed part's task.

Do not wait for the owner between steps 2 and 4. Do not fork the current conversation as a substitute
for a new task. If task creation returns a temporary setup state, wait for it to finish and then
continue the handoff.

The final part does not create the next phase. It records the complete phase result and asks the
project owner for one explicit phase signoff.

## Decision authority during a phase

Codex makes routine product, policy, design, review, and feature-scope decisions without asking the
owner. Use the repository's approved contracts first. When those contracts leave a gap, choose the
smallest fail-closed option that preserves data, authorization, audit, rollback, and later-phase
ownership. Record the decision and its reason in the current phase's canonical design or review
file.

Do not pause to ask which recommended option the owner prefers. Do not add optional features merely
because they are useful. Keep them with their assigned later phase or leave them out.

A mid-phase pause is allowed only when work cannot continue safely inside the authorized phase. The
usual reasons are:

- required production data, a paid service, or a new cloud resource;
- access to a real employee, patient, banking, payroll, or other regulated record;
- deletion or irreversible modification of a preserved resource outside the phase's explicit scope;
- a missing credential or external action that Codex cannot supply;
- an irreconcilable requirement conflict where every available choice would violate an approved
  security, legal, or data-preservation boundary; or
- a repeated technical blocker that remains after the repository's safe alternatives are exhausted.

When a decision can stay local, synthetic, reversible, and inside the phase boundary, make it and
continue.

## Verification and source control

Every part follows `docs/migration/VERIFICATION_WORKFLOW.md`. Run focused checks during development
and one boundary-matched local gate when the part is ready. Push the settled part once, wait for all
routed GitHub jobs, and fix any failure before creating the next task.

Do not rerun a passing code gate for a later documentation-only completion edit. Do not create a
second commit only to store a workflow URL when the handoff can carry that URL.

## Final phase signoff

The last part must prove the complete phase boundary, record its completion, and leave a clean,
synchronized branch. It then asks the project owner for one explicit signoff covering the whole
phase.

Do not start Part A of the next phase until the owner signs off the completed phase and separately
starts the next phase. That new Part A instruction begins the same automatic task chain again.

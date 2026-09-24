# AGENTS.md

## Writing style

Always load and follow the `unslop` skill (.opencode/skill/unslop/SKILL.md) for any prose you write or edit: commit messages, PR descriptions, docs, comments, README files, checklists, user-facing copy. Code itself is exempt, but comments inside code are not.

## Phase execution

For every migration phase, read and follow `docs/migration/PHASE_EXECUTION_WORKFLOW.md`. Starting
Part A authorizes every listed part through the final phase gate. Run each part in a separate Codex
task. After a part passes its local and GitHub gates, generate the next part's handoff, create its task
automatically in the same saved project and local checkout, and start it without another owner
approval. Ask for owner signoff only after the whole phase is complete.

Make routine product, policy, design, review, and feature-scope decisions without asking the owner.
Choose the smallest fail-closed option that stays inside the approved phase and record the decision.
Pause only for a boundary named in the execution workflow that Codex cannot safely resolve.

## Phase handoff prompts

Read and follow `docs/migration/HANDOFF_PROMPT_STANDARD.md` whenever a part completes or the owner
asks for a handoff. Build the prompt from verified repository state and the current canonical design.
Keep it part-specific and avoid copying existing test inventories or design tables. A handoff inside
an active phase carries the phase's standing authorization and must not ask for another approval.

## Verification workflow

For every migration phase or task, read and follow `docs/migration/VERIFICATION_WORKFLOW.md`. Choose
checks from the files and boundaries changed. Run one complete local gate when phase code is ready,
then push once. After that gate passes, documentation-only follow-up work must not repeat the local or
GitHub full-stack gate.

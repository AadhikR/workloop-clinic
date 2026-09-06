# AGENTS.md

## Writing style

Always load and follow the `unslop` skill (.opencode/skill/unslop/SKILL.md) for any prose you write or edit: commit messages, PR descriptions, docs, comments, README files, checklists, user-facing copy. Code itself is exempt, but comments inside code are not.

## Phase handoff prompts

When the project owner asks for a handoff prompt for the next phase, read and follow
`docs/migration/HANDOFF_PROMPT_STANDARD.md`. Build the prompt from verified repository state and the
current canonical design. Keep it phase-specific, avoid copying existing test inventories or design
tables, and distinguish prompt preparation from authorization to begin the phase.

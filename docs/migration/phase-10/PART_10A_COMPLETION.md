# Part 10A completion

Status: complete.

## Result

Part 10A accounts for the legacy modules, direct component calls, tables, RPCs, calculations,
employee paths, payroll consumers, and later-phase consumers. The domain contract fixes UAE date
ownership, shift precedence, event provenance and deduplication, status precedence, decimal rules,
correction and close immutability, roster publication versions, actual-hours authority, overtime
separation, staffing and leave gates, swap versioning, and the two Phase 9 projections.

The amendment proposal records fifteen approved decisions. It authorizes the bounded 10B schema,
constraint, index, audit, idempotency, and security changes without adding a role or broadening staff
access. The roster mismatch is resolved through month publication versions and append-only actual
hours rather than direct changes to published rows.

Eight cutover templates under `docs/migration/phase-10/cutover/` name the legacy authority,
migration freeze, rollback order, synthetic identity mapping, and validation source. They remain in
`preparation` until their owning implementation part passes.

## Validation

10A uses documentation-only validation: Markdown structure and whitespace, internal references,
inventory and decision coverage, cutover schema and digest validation, part status, and
`git diff --check`. No backend, frontend, database, browser, or Phase 9 full-stack gate is required.

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. All prose received a manual
review for direct language, sentence-case headings, concrete claims, and consistent terminology.

## Authorization boundary

Part 10B is authorized and begins after the 10A documentation commit. Parts 10C through 10J remain
unauthorized. The 10A commit changes no migration, route, service, UI, writer, database object, or
cutover authority.

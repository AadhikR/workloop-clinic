import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readText(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

const agents = readText('AGENTS.md')
const execution = readText('docs/migration/PHASE_EXECUTION_WORKFLOW.md')
const handoff = readText('docs/migration/HANDOFF_PROMPT_STANDARD.md')
const verification = readText('docs/migration/VERIFICATION_WORKFLOW.md')
const workflow = readText('.github/workflows/migration-foundation.yml')

test('one Part A approval authorizes the complete phase', () => {
  assert.match(execution, /starts Part A[\s\S]+authorizes every listed part/)
  assert.match(execution, /only routine owner[\s\S]+signoff requested after the whole phase passes/)
  assert.match(agents, /Starting[\s\S]+Part A authorizes every listed part/)
})

test('each completed part starts the next part in a new task', () => {
  for (const source of [agents, execution, handoff, verification]) {
    assert.match(source, /separate Codex\s+task|new Codex task/)
    assert.match(source, /create[\s\S]{0,80}task[\s\S]{0,80}automatically/i)
  }
  assert.match(execution, /Do not implement two parts in the same task/)
  assert.match(handoff, /No owner approval is required between parts/)
})

test('routine decisions do not create approval pauses', () => {
  assert.match(execution, /makes routine product, policy, design, review, and feature-scope decisions/)
  assert.match(execution, /Do not pause to ask which recommended option/)
  assert.match(handoff, /Do not ask the owner to choose among recommended options/)
})

test('active instructions contain no superseded part-approval gate', () => {
  const activeInstructions = [agents, execution, handoff, verification].join('\n')
  for (const forbidden of [
    /This prompt prepares Phase \[ID\]\. It does not authorize/,
    /Begin only after the project owner explicitly authorizes/,
    /State the phase that the owner may authorize/,
    /distinguish prompt preparation from authorization/,
  ]) {
    assert.doesNotMatch(activeInstructions, forbidden)
  }
})

test('the final part stops for whole-phase signoff', () => {
  assert.match(execution, /final part does not create the next phase/)
  assert.match(handoff, /request one project-owner signoff/)
  assert.match(verification, /last part[\s\S]+requests one project-owner signoff/)
})

test('GitHub validates the execution workflow on every routed run', () => {
  assert.match(
    workflow,
    /Classify and validate changes[\s\S]+Verify phase execution workflow[\s\S]+node --test tests\/phase-execution-workflow\.test\.js/,
  )
})

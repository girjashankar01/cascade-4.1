/**
 * pages.test.ts — rewritten for new page structure.
 * Tests cover: scenario fixture shape, coverage item structure.
 * Old secondaryData exports (paymentRequests, approvedPlans, getAuditSteps)
 * are removed — pages now own their data inline.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { coverageGuarantees, coverageLimitations } from '../src/data/secondaryData.ts'
import { scenarios } from '../src/data/fixtures.ts'
import { VERDICT_PLAIN } from '../src/data/types.ts'
import type { ScenarioId } from '../src/data/types.ts'

test('all five scenarios are defined with correct shape', () => {
  const ids: ScenarioId[] = ['A', 'B1', 'B2', 'B3', 'C']
  assert.equal(scenarios.length, 5)
  for (const id of ids) {
    const s = scenarios.find(x => x.id === id)
    assert.ok(s, `Scenario ${id} missing`)
    assert.ok(s!.title.length > 0, `Scenario ${id} has no title`)
    assert.ok(s!.story.length > 0, `Scenario ${id} has no story`)
    assert.ok(['VERIFIED', 'MISMATCH', 'UNSUPPORTED', 'UNCERTAIN'].includes(s!.expectedVerdict),
      `Scenario ${id} has invalid expectedVerdict: ${s!.expectedVerdict}`)
  }
})

test('expected verdicts match truth file §5', () => {
  const expected: Record<ScenarioId, 'VERIFIED' | 'MISMATCH'> = {
    A: 'VERIFIED', B1: 'MISMATCH', B2: 'VERIFIED', B3: 'MISMATCH', C: 'VERIFIED',
  }
  for (const [id, verdict] of Object.entries(expected) as [ScenarioId, 'VERIFIED' | 'MISMATCH'][]) {
    const s = scenarios.find(x => x.id === id)!
    assert.equal(s.expectedVerdict, verdict, `Scenario ${id} expected ${verdict}, got ${s.expectedVerdict}`)
  }
})

test('scenario C is a reset, not a payment', () => {
  const c = scenarios.find(s => s.id === 'C')!
  assert.equal(c.actionKind, 'reset')
  assert.match(c.story.toLowerCase(), /reset/)
})

test('VERDICT_PLAIN maps all four verdicts to plain language per §4', () => {
  assert.equal(VERDICT_PLAIN['VERIFIED'],    'Verified')
  assert.equal(VERDICT_PLAIN['MISMATCH'],    'Does not match')
  assert.equal(VERDICT_PLAIN['UNSUPPORTED'], 'Cannot be checked, needs review')
  assert.equal(VERDICT_PLAIN['UNCERTAIN'],   'Evidence unclear')
})

test('secondaryData coverage stubs exist (real data is inline in CoveragePage)', () => {
  // These are now stubs — real data is in CoveragePage.tsx
  assert.ok(Array.isArray(coverageGuarantees))
  assert.ok(Array.isArray(coverageLimitations))
})

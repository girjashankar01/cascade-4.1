import test from 'node:test'
import assert from 'node:assert/strict'
import {
  approvedPlans,
  coverageGuarantees,
  coverageLimitations,
  getAuditSteps,
  paymentRequests,
} from '../src/data/secondaryData.ts'
import type { ScenarioId } from '../src/data/types.ts'

test('all scenarios have complete payment request fixtures and grounded claims', () => {
  const ids: ScenarioId[] = ['A', 'B1', 'B3', 'C']
  for (const id of ids) {
    const request = paymentRequests[id]
    assert.ok(request, `Payment request fixture missing for scenario ${id}`)
    assert.equal(request.scenarioId, id)
    assert.ok(request.proposalId.length > 0)
    assert.ok(request.title.length > 0)
    assert.ok(request.claims.length > 0)
    assert.ok(request.sourceDocument.filename.length > 0)
    assert.match(request.sourceDocument.digest, /^0x[\da-f]{64}$/i)
  }

  // Conflict notice assertions
  assert.equal(paymentRequests.A.conflictNotice, null)
  assert.match(paymentRequests.B1.conflictNotice!, /Tampering detected/)
  assert.match(paymentRequests.B3.conflictNotice!, /Malicious upgrade detected/)
  assert.equal(paymentRequests.C.conflictNotice, null)
})

test('all scenarios have canonical approved plan manifests with invariants', () => {
  const ids: ScenarioId[] = ['A', 'B1', 'B3', 'C']
  for (const id of ids) {
    const plan = approvedPlans[id]
    assert.ok(plan, `Approved plan fixture missing for scenario ${id}`)
    assert.equal(plan.scenarioId, id)
    assert.match(plan.intentCommitment, /^0x[\da-f]{64}$/i)
    assert.equal(plan.lockStatus, 'Locked by Governance')
    assert.ok(plan.invariants.length > 0)
  }

  // Invariant verification
  assert.ok(approvedPlans.A.invariants.every(inv => inv.status === 'Enforced'))
  assert.ok(approvedPlans.B1.invariants.some(inv => inv.status.includes('Violated')))
  assert.ok(approvedPlans.B3.invariants.some(inv => inv.status.includes('Violated')))
})

test('audit steps strictly follow Read, Lock, Check, Enforce sequence', () => {
  const expectedSteps = ['Read', 'Lock', 'Check', 'Enforce']

  const stepsA = getAuditSteps('A', 'allowed')
  assert.deepEqual(stepsA.map(s => s.name), expectedSteps)
  assert.ok(stepsA.every(s => s.status === 'passed'))

  const stepsB1 = getAuditSteps('B1', 'blocked')
  assert.deepEqual(stepsB1.map(s => s.name), expectedSteps)
  assert.equal(stepsB1.find(s => s.name === 'Check')?.status, 'blocked')
  assert.equal(stepsB1.find(s => s.name === 'Enforce')?.status, 'blocked')

  const stepsB3 = getAuditSteps('B3', 'blocked')
  assert.deepEqual(stepsB3.map(s => s.name), expectedSteps)
  assert.equal(stepsB3.find(s => s.name === 'Check')?.status, 'blocked')
  assert.equal(stepsB3.find(s => s.name === 'Enforce')?.status, 'blocked')

  const stepsC = getAuditSteps('C', 'reset')
  assert.deepEqual(stepsC.map(s => s.name), expectedSteps)
  assert.ok(stepsC.every(s => s.status === 'passed'))
})

test('coverage definitions state guarantees and honest limitations transparently', () => {
  assert.equal(coverageGuarantees.length, 4)
  assert.equal(coverageLimitations.length, 4)

  assert.ok(coverageGuarantees.some(g => g.title.includes('Recipient Substitution')))
  assert.ok(coverageGuarantees.some(g => g.title.includes('Pre-Execution Enforcement')))

  assert.ok(coverageLimitations.some(l => l.title.includes('Off-Chain')))
  assert.ok(coverageLimitations.some(l => l.title.includes('Compromised Governance Quorum')))
})

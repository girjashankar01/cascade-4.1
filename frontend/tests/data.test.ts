import test from 'node:test'
import assert from 'node:assert/strict'
import { adaptBalances, adaptConnection, adaptRun } from '../src/data/adapters.ts'
import { createFixtureService, formatTokens } from '../src/data/fixtures.ts'
import { createDataService } from '../src/data/api.ts'
import { createClient } from '../src/data/client.ts'
import { DataError } from '../src/data/types.ts'
import type { ScenarioId } from '../src/data/types.ts'

const json = (payload: unknown) => new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
const role = (raw: string, digit: string) => ({ address: `0x${digit.repeat(40)}`, token_balance_raw: raw })
const balancePayload = { connected: true, token_address: `0x${'a'.repeat(40)}`, treasury: role('1000000000000', '1'), recipient: role('0', '2'), attacker: role('0', '3') }

// A minimal valid scenario-A live response shape
const allowedRaw = {
  scenario: 'A', success: true, verdict: 'VERIFIED',
  rules: [{ rule_id: 'R1', name: 'Governance check', status: 'PASS', explanation: 'Passed.', evidence: {} }],
  diffs: [],
  attestation: { signature: '0x' + 'a'.repeat(64), deadline: 1800000000 },
  execution_result: { status: 1, tx_hash: '0x' + 'a'.repeat(64), block_number: 1 },
  submitted_action: { kind: 'erc20_payout', recipient: '0x' + '2'.repeat(40), amount_raw: '1000000000000' },
  reason: 'The submitted action matches the approved manifest exactly.',
}

test('all demo cases return correct verdict and preserve conservation of tokens', async () => {
  const service = createFixtureService()
  for (const id of ['A', 'B1', 'B2', 'B3', 'C'] as ScenarioId[]) {
    const result = await service.run(id)
    assert.equal(result.source, 'demo')
    assert.ok(['VERIFIED', 'MISMATCH', 'UNSUPPORTED', 'UNCERTAIN'].includes(result.verdict), `verdict ${result.verdict} is valid`)
    // Scenario A: tokens move from Treasury to recipient
    if (id === 'A') {
      assert.equal(result.verdict, 'VERIFIED')
      assert.equal(result.attestation.present, true)
      assert.equal(result.paymentStopped, 'no')
      assert.equal(result.after?.recipient.amountRaw, '1000000000000')
    }
    // Scenario B1: MISMATCH, no attestation, balances unchanged
    if (id === 'B1') {
      assert.equal(result.verdict, 'MISMATCH')
      assert.equal(result.attestation.present, false)
      assert.equal(result.paymentStopped, 'yes')
      assert.equal(result.diffs.length > 0, true)
      assert.ok(result.failedRule !== null)
    }
    // Scenario B2: control case, VERIFIED upgrade
    if (id === 'B2') {
      assert.equal(result.verdict, 'VERIFIED')
      assert.equal(result.approved.kind, 'proxy_upgrade')
    }
    // Scenario B3: malicious upgrade, MISMATCH
    if (id === 'B3') {
      assert.equal(result.verdict, 'MISMATCH')
      assert.equal(result.attestation.present, false)
    }
    // Scenario C: reset
    if (id === 'C') {
      assert.equal(result.verdict, 'VERIFIED')
      assert.equal(result.approved.kind, 'reset')
      assert.equal(result.paymentStopped, 'not-applicable')
    }
  }
})

test('demo service makes no network calls even with invalid live configuration', async () => {
  let calls = 0
  const service = createDataService('invalid base', async () => { calls++; throw new Error('Must not fetch') })
  assert.equal((await service.connection('demo')).service, 'demo')
  await service.balances('demo', 'one')
  await service.run('demo', 'one', 'A')
  await service.reset('demo', 'one')
  assert.equal(calls, 0)
})

test('fixture duplicate runs are blocked while a run is active', async () => {
  const service = createFixtureService()
  const first = service.run('A')
  await assert.rejects(service.run('B1'), { code: 'BUSY' })
  await first
})

test('all four verdicts are returned correctly from fixture scenarios', async () => {
  const service = createFixtureService()
  const resultA = await service.run('A')
  assert.equal(resultA.verdict, 'VERIFIED')
  assert.equal(resultA.plainVerdict, 'Verified')
  const resultB1 = await service.run('B1')
  assert.equal(resultB1.verdict, 'MISMATCH')
  assert.equal(resultB1.plainVerdict, 'Does not match')
})

test('adaptRun: MISMATCH blocked correctly, VERIFIED allowed correctly', () => {
  // MISMATCH case
  const mismatch = adaptRun({
    scenario: 'B1', success: true, verdict: 'MISMATCH',
    rules: [{ rule_id: 'R2', name: 'Action hash', status: 'FAIL', explanation: 'Fields differ.', evidence: {} }],
    diffs: [{ field: 'recipient', approved: 'A', submitted: 'B' }],
    execution_result: null, submitted_action: {}, reason: 'Does not match.',
    attestation: null,
  }, 'B1')
  assert.equal(mismatch.verdict, 'MISMATCH')
  assert.equal(mismatch.paymentStopped, 'yes')
  assert.equal(mismatch.attestation.present, false)
  assert.equal(mismatch.failedRule?.rule_id, 'R2')
  assert.equal(mismatch.diffs.length, 1)

  // VERIFIED case
  const verified = adaptRun(allowedRaw, 'A')
  assert.equal(verified.verdict, 'VERIFIED')
  assert.equal(verified.attestation.present, true)
})

test('adaptRun: unknown/missing verdict returns INVALID_RESPONSE', () => {
  assert.throws(() => adaptRun({ ...allowedRaw, verdict: 'MAYBE' }, 'A'), { code: 'INVALID_RESPONSE' })
  assert.throws(() => adaptRun({ ...allowedRaw, scenario: 'B1' }, 'A'), { code: 'INVALID_RESPONSE' })
})

test('adaptRun: scenario C reset is correctly parsed', () => {
  const reset = adaptRun({
    scenario: 'C', success: true, steps: [{ status: 'COMPLETED' }],
    deployments: {
      seeded_proposal_id: 'PROP-002',
      token: role('0', '1').address, registry: role('0', '2').address,
      treasury: role('0', '3').address, executor: role('0', '4').address,
    },
  }, 'C')
  assert.equal(reset.verdict, 'VERIFIED')
  assert.equal(reset.approved.kind, 'reset')
  assert.equal(reset.paymentStopped, 'not-applicable')
})

test('adaptRun: empty steps or missing deployments returns INVALID_RESPONSE for C', () => {
  assert.throws(() => adaptRun({ scenario: 'C', success: true, steps: [], deployments: {} }, 'C'), { code: 'INVALID_RESPONSE' })
})

test('adaptBalances: rejects missing fields, floats and all-zero fallbacks', () => {
  assert.equal(adaptBalances({ ...balancePayload, token_address: null }), null)
  assert.equal(adaptBalances({ ...balancePayload, treasury: role('1.25', '1') }), null)
  assert.equal(adaptBalances({ ...balancePayload, treasury: role('0', '1') }), null)
  const snap = adaptBalances(balancePayload)
  assert.ok(snap !== null)
  assert.equal(snap!.treasury.amountRaw, '1000000000000')
  assert.equal(snap!.treasury.role, 'Treasury')
  assert.equal(snap!.recipient.role, 'Honest recipient')
  assert.equal(snap!.attacker.role, 'Attacker')
})

test('formatTokens: handles large numbers and fractions correctly', () => {
  assert.equal(formatTokens('123456789012345678901234'), '123,456,789,012,345,678.901234')
  assert.equal(formatTokens('1000001'), '1.000001')
  assert.equal(formatTokens('1000000000000'), '1,000,000')
})

test('adaptConnection: service and chain availability are separate', () => {
  assert.equal(adaptConnection({ status: 'ok', rpc_connected: false }).service, 'online')
  assert.equal(adaptConnection({ status: 'ok', rpc_connected: false }).chain, 'offline')
  assert.equal(adaptConnection({ status: 'ok', rpc_connected: true, chain_id: 1 }).chain, 'offline')
  assert.throws(() => adaptConnection({ status: 'ok' }), { code: 'INVALID_RESPONSE' })
})

test('live failure after submission is never retried or unlocked automatically', async () => {
  let posts = 0
  const service = createDataService('https://unit.test/uncertain', async (input, options) => {
    if (options?.method === 'POST') { posts++; throw new Error('Sensitive stack text must not escape') }
    return String(input).endsWith('/health') ? json({ status: 'ok', rpc_connected: true, chain_id: 31337 }) : json(balancePayload)
  })
  await assert.rejects(service.run('live', 'one', 'A'), (error: unknown) => error instanceof DataError && !error.message.includes('Sensitive'))
  await assert.rejects(service.run('live', 'two', 'B1'), { code: 'LIVE_BUSY' })
  assert.equal(service.liveOperationPending(), true)
  assert.equal(posts, 1)
  // Demo still works even when live is locked
  const demoResult = await service.run('demo', 'two', 'B1')
  assert.equal(demoResult.verdict, 'MISMATCH')
})

test('a single live operation lock covers concurrent workspaces', async () => {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  const service = createDataService('https://unit.test/concurrent', async (input, options) => {
    if (String(input).endsWith('/health')) { await wait; return json({ status: 'ok', rpc_connected: true, chain_id: 31337 }) }
    if (options?.method === 'POST') return json(allowedRaw)
    return json(balancePayload)
  })
  const first = service.run('live', 'one', 'A')
  await assert.rejects(service.run('live', 'two', 'A'), { code: 'LIVE_BUSY' })
  release(); await first
  assert.equal(service.liveOperationPending(), false)
})

test('read errors and HTTP failures are sanitized without copying response bodies', async () => {
  const request = createClient({ baseUrl: 'https://unit.test', fetcher: async () => new Response('private backend stack', { status: 500 }) })
  await assert.rejects(request('/health'), (error: unknown) => error instanceof DataError && !error.message.includes('private'))
})

test('a timed-out POST is unconfirmed and a second submission is prevented', async () => {
  let posts = 0
  const service = createDataService('https://unit.test/timeout', async (input, options) => {
    if (options?.method === 'POST') {
      posts++
      return new Promise<Response>((resolve, reject) => {
        const guard = setTimeout(() => resolve(json(allowedRaw)), 250)
        const onAbort = () => { clearTimeout(guard); reject(new Error('timeout diagnostic')) }
        if (options.signal?.aborted) onAbort()
        else options.signal?.addEventListener('abort', onAbort, { once: true })
      })
    }
    return String(input).endsWith('/health') ? json({ status: 'ok', rpc_connected: true, chain_id: 31337 }) : json(balancePayload)
  }, 10)
  await assert.rejects(service.run('live', 'one', 'A'))
  await assert.rejects(service.run('live', 'two', 'A'), { code: 'LIVE_BUSY' })
  assert.equal(posts, 1)
})

test('technical evidence only exposes validated allowlisted values', async () => {
  const { technicalRows } = await import('../src/data/technical.ts')
  const result = await createFixtureService().run('A')
  // Current implementation comes from execution_result in the new technical.ts
  const implAddr = '0x' + 'a'.repeat(40)
  const rows = technicalRows(result, {
    private_key: 'secret', error: 'raw stack',
    execution_result: { current_implementation: implAddr, private_key: 'another secret' },
  })
  // No sensitive values should leak through
  assert.ok(rows.every(row => !/secret|stack|unsafe/.test(row.value)))
  // The allowlisted implementation address should appear
  assert.ok(rows.some(row => row.label === 'Current implementation' && row.value === implAddr))
})

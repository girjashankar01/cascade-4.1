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
const allowed = { scenario: 'A', success: true, verdict: 'VERIFIED', verification_report: { verdict: 'VERIFIED', all_passed: true }, execution_result: { status: 1, tx_hash: '0x' + 'a'.repeat(64) } }

test('all four demo cases preserve exact balances, reset and isolation', async () => {
  const service = createFixtureService()
  for (const id of ['A', 'B1', 'C', 'B3'] as ScenarioId[]) {
    const result = await service.run(id)
    assert.equal(result.source, 'demo')
    assert.equal(BigInt(result.after!.fund) + BigInt(result.after!.recipient) + BigInt(result.after!.badActor), 1000000000000n)
    if (id === 'A') assert.equal(result.after!.recipient, '1000000000000')
    else assert.equal(result.after!.badActor, '0')
    if (id === 'C') { assert.equal(result.outcome, 'reset'); assert.equal(result.paymentStopped, 'not-applicable') }
    result.after!.fund = '999'
    assert.notEqual(service.balances().fund, '999')
  }
  await service.run('A')
  const reset = await service.run('C')
  assert.equal(reset.before!.fund, '0'); assert.equal(reset.before!.recipient, '1000000000000')
  assert.equal(reset.after!.fund, '1000000000000'); assert.equal(reset.after!.recipient, '0')
  assert.deepEqual(service.reset(), { fund: '1000000000000', recipient: '0', badActor: '0', quality: 'demo' })
  assert.equal(createFixtureService().balances().recipient, '0')
})
test('demo service makes no network calls even with invalid live configuration', async () => {
  let calls = 0
  const service = createDataService('invalid base', async () => { calls++; throw new Error('Must not fetch') })
  assert.equal((await service.connection('demo')).service, 'demo')
  await service.balances('demo', 'one')
  await service.run('demo', 'one', 'A')
  await service.reset('demo', 'one')
  assert.equal((await service.balances('demo', 'two'))!.recipient, '0')
  assert.equal(calls, 0)
})
test('fixture duplicate runs and resets are blocked while a run is active', async () => {
  const service = createFixtureService()
  const first = service.run('A')
  assert.throws(() => service.reset(), { code: 'BUSY' })
  await assert.rejects(service.run('B1'), { code: 'BUSY' })
  await first
})
test('runner success is not payment permission; blocked proof stays explicit', () => {
  const result = adaptRun({ scenario: 'B1', success: true, verdict: 'MISMATCH', verification_report: { verdict: 'MISMATCH' }, blocked_as_expected: true, execution_result: null, balances_verified: { treasury_protected: true, attacker_zero_gain: true, recipient_unaffected: true } }, 'B1')
  assert.equal(result.outcome, 'blocked'); assert.equal(result.paymentStopped, 'yes')
  const unproven = adaptRun({ scenario: 'B3', success: true, verdict: 'MISMATCH', verification_report: { verdict: 'MISMATCH' }, blocked_as_expected: true, execution_result: null }, 'B3')
  assert.equal(unproven.paymentStopped, 'unknown')
})
test('unknown, mismatched and contradictory run responses never become allowed', () => {
  assert.throws(() => adaptRun({ ...allowed, verdict: 'MAYBE' }, 'A'), { code: 'INVALID_RESPONSE' })
  assert.throws(() => adaptRun({ ...allowed, execution_result: { status: 0 } }, 'A'), { code: 'INVALID_RESPONSE' })
  assert.throws(() => adaptRun({ ...allowed, execution_result: { status: 1, tx_hash: 'not a receipt' } }, 'A'), { code: 'INVALID_RESPONSE' })
  assert.throws(() => adaptRun(allowed, 'B1'), { code: 'INVALID_RESPONSE' })
  assert.throws(() => adaptRun({ ...allowed, verification_report: { verdict: 'MISMATCH' } }, 'A'), { code: 'INVALID_RESPONSE' })
  assert.equal(adaptRun(allowed, 'A').outcome, 'allowed')
})
test('reset and unsupported responses are not disguised as payments', () => {
  assert.throws(() => adaptRun({ scenario: 'C', success: true, steps: [], deployments: {} }, 'C'), { code: 'INVALID_RESPONSE' })
  const reset = adaptRun({ scenario: 'C', success: true, steps: [{ status: 'COMPLETED' }], deployments: { seeded_proposal_id: 'PROP-002', token: role('0', '1').address, registry: role('0', '2').address, treasury: role('0', '3').address, executor: role('0', '4').address } }, 'C')
  assert.equal(reset.outcome, 'reset'); assert.equal(reset.approved.kind, 'reset'); assert.equal(reset.paymentStopped, 'not-applicable')
  const unknown = adaptRun({ scenario: 'B3', success: true, verdict: 'UNSUPPORTED', verification_report: { verdict: 'UNSUPPORTED' }, execution_result: null }, 'B3')
  assert.equal(unknown.outcome, 'needs-review'); assert.equal(unknown.paymentStopped, 'unknown')
})
test('balances reject missing deployments, floats and ambiguous zero fallbacks', () => {
  assert.equal(adaptBalances({ ...balancePayload, token_address: null }), null)
  assert.equal(adaptBalances({ ...balancePayload, treasury: role('1.25', '1') }), null)
  assert.equal(adaptBalances({ ...balancePayload, treasury: role('0', '1') }), null)
  assert.equal(adaptBalances(balancePayload)!.fund, '1000000000000')
  assert.equal(formatTokens('123456789012345678901234'), '123,456,789,012,345,678.901234')
  assert.equal(formatTokens('1000001'), '1.000001')
})
test('service availability and chain availability are separate', () => {
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
  await assert.rejects(service.run('live', 'one', 'A'), (error: unknown) => error instanceof DataError && error.code === 'RUN_UNCONFIRMED' && !error.message.includes('Sensitive'))
  await assert.rejects(service.run('live', 'two', 'B1'), { code: 'LIVE_BUSY' })
  assert.equal(service.liveOperationPending(), true); assert.equal(posts, 1)
  assert.equal((await service.run('demo', 'two', 'B1')).outcome, 'blocked')
})
test('a single live operation lock covers concurrent workspaces', async () => {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  const service = createDataService('https://unit.test/concurrent', async (input, options) => {
    if (String(input).endsWith('/health')) { await wait; return json({ status: 'ok', rpc_connected: true, chain_id: 31337 }) }
    if (options?.method === 'POST') return json(allowed)
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
        const guard = setTimeout(() => resolve(json(allowed)), 250)
        const onAbort = () => { clearTimeout(guard); reject(new Error('timeout diagnostic')) }
        if (options.signal?.aborted) onAbort()
        else options.signal?.addEventListener('abort', onAbort, { once: true })
      })
    }
    return String(input).endsWith('/health') ? json({ status: 'ok', rpc_connected: true, chain_id: 31337 }) : json(balancePayload)
  }, 10)
  await assert.rejects(service.run('live', 'one', 'A'), { code: 'RUN_UNCONFIRMED' })
  await assert.rejects(service.run('live', 'two', 'A'), { code: 'LIVE_BUSY' })
  assert.equal(posts, 1)
})

test('technical evidence only exposes validated allowlisted values', async () => {
  const { technicalRows } = await import('../src/data/technical.ts')
  const result = await createFixtureService().run('A')
  const rows = technicalRows(result, { private_key: 'secret', error: 'raw stack', execution_result: { tx_hash: 'unsafe text', private_key: 'another secret' }, slot_verified: { current_implementation: '0x' + 'a'.repeat(40) } })
  assert.ok(rows.some(row => row.label === 'Current implementation'))
  assert.ok(rows.every(row => !/secret|stack|unsafe/.test(row.value)))
  assert.ok(!rows.some(row => row.label === 'Transaction hash'))
  const hash = '0x' + 'b'.repeat(64)
  assert.equal(technicalRows(result, { execution_result: { tx_hash: hash } }).find(row => row.label === 'Transaction hash')?.value, hash)
})

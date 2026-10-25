import { DataError, unavailableAction } from './types.ts'
import type { ActionSummary, Balances, Connection, RunResult, ScenarioId } from './types.ts'

type ObjectValue = Record<string, unknown>
export function asObject(value: unknown): ObjectValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as ObjectValue : {}
}
const integerString = (value: unknown): value is string => typeof value === 'string' && /^\d+$/.test(value)
const address = (value: unknown): value is string => typeof value === 'string' && /^0x[\da-f]{40}$/i.test(value) && !/^0x0{40}$/i.test(value)
function invalid(): never { throw new DataError('INVALID_RESPONSE', 'The service returned an incomplete result. Keep using demo data or check the record before trying again.') }

export function adaptConnection(payload: unknown): Connection {
  const data = asObject(payload)
  if (data.status !== 'ok' || typeof data.rpc_connected !== 'boolean') return invalid()
  if (data.rpc_connected && (typeof data.chain_id !== 'number' || ![31337, 1337].includes(data.chain_id))) return { service: 'online', chain: 'offline', message: 'The service has not confirmed a local test chain. Use demo data.' }
  return { service: 'online', chain: data.rpc_connected ? 'online' : 'offline', message: data.rpc_connected ? 'Local service and chain are available.' : 'The local service is available. The chain is not connected.' }
}

export function adaptBalances(payload: unknown): Balances | null {
  const data = asObject(payload)
  const fund = asObject(data.treasury), recipient = asObject(data.recipient), badActor = asObject(data.attacker)
  if (data.connected !== true || !address(data.token_address)) return null
  if (![fund, recipient, badActor].every(role => address(role.address) && integerString(role.token_balance_raw))) return null
  const result: Balances = { fund: fund.token_balance_raw as string, recipient: recipient.token_balance_raw as string, badActor: badActor.token_balance_raw as string, quality: 'reported' }
  // This seeded system always has funds somewhere. A zero-only fallback is ambiguous.
  if ([result.fund, result.recipient, result.badActor].every(raw => BigInt(raw) === 0n)) return null
  return result
}

export function adaptPlan(payload: unknown): ActionSummary {
  const action = asObject(asObject(asObject(payload).manifest).action)
  if (action.kind === 'erc20_payout' && integerString(action.amountRaw) && address(action.recipient) && (action.decimals === 6 || action.decimals === '6')) {
    return { kind: 'payment', description: 'The payment recorded in the approved plan.', recipient: 'Approved recipient', amountRaw: action.amountRaw }
  }
  if (action.kind === 'proxy_upgrade' && address(action.newImpl)) return { kind: 'upgrade', description: 'The software change recorded in the approved plan.', recipient: null, amountRaw: null }
  return { ...unavailableAction }
}

export function adaptRun(payload: unknown, expected: ScenarioId, approved: ActionSummary = unavailableAction): RunResult {
  const data = asObject(payload)
  if (data.scenario !== expected || data.success !== true) return invalid()
  const base: RunResult = { id: crypto.randomUUID(), scenario: expected, source: 'live', outcome: 'needs-review', reason: 'The result needs review.', paymentStopped: 'unknown', approved: { ...approved }, submitted: { ...unavailableAction }, before: null, after: null, startedFromCleanState: false }
  if (expected === 'C') {
    const deployments = asObject(data.deployments)
    if (!Array.isArray(data.steps) || data.steps.length === 0 || !data.steps.every(step => asObject(step).status === 'COMPLETED') || !['token', 'registry', 'treasury', 'executor'].every(key => address(deployments[key])) || typeof deployments.seeded_proposal_id !== 'string') return invalid()
    return { ...base, outcome: 'reset', reason: 'The service reports a fresh demo environment. No payment was made.', paymentStopped: 'not-applicable', approved: { kind: 'reset', description: 'Restore the demo environment.', recipient: null, amountRaw: null }, submitted: { kind: 'reset', description: 'A fresh demo environment was prepared.', recipient: null, amountRaw: null } }
  }
  const report = asObject(data.verification_report)
  if (!['VERIFIED', 'MISMATCH', 'UNSUPPORTED', 'UNCERTAIN'].includes(String(data.verdict))) return invalid()
  if (report.verdict !== data.verdict) return invalid()
  const execution = asObject(data.execution_result)
  if (data.verdict === 'VERIFIED') {
    if (expected !== 'A' || execution.status !== 1 || report.all_passed !== true || typeof execution.tx_hash !== 'string' || !/^(0x)?[\da-f]{64}$/i.test(execution.tx_hash)) return invalid()
    return { ...base, outcome: 'allowed', reason: 'The service reports that the approved payment was executed.', paymentStopped: 'no', submitted: { ...approved } }
  }
  if (data.verdict === 'MISMATCH') {
    if (data.blocked_as_expected !== true || data.execution_result !== null) return invalid()
    const balances = asObject(data.balances_verified), slot = asObject(data.slot_verified)
    const proof = expected === 'B1' ? balances.treasury_protected === true && balances.attacker_zero_gain === true && balances.recipient_unaffected === true : expected === 'B3' && slot.slot_protected === true
    return { ...base, outcome: 'blocked', reason: expected === 'B3' ? 'The software update includes an undeclared change.' : 'The submitted payment differs from the approved plan.', paymentStopped: proof ? 'yes' : 'unknown', submitted: { kind: expected === 'B3' ? 'upgrade' : 'unavailable', description: expected === 'B3' ? 'A software change outside the approved plan.' : 'A changed payment was submitted. Open the record for its evidence.', recipient: null, amountRaw: null } }
  }
  if (data.execution_result) return invalid()
  return { ...base, reason: data.verdict === 'UNSUPPORTED' ? 'This action is outside the checks the service supports.' : 'There is not enough reliable evidence to allow this action.' }
}

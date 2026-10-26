import { DataError, unavailableAction, unavailableAttestation, VERDICT_PLAIN } from './types.ts'
import type {
  ApprovedAction, Attestation, BalanceSnapshot, Connection, FieldDiff,
  RoleBalance, RunResult, RuleResult, ScenarioId, SubmittedAction, Verdict,
} from './types.ts'

type ObjectValue = Record<string, unknown>
export function asObject(value: unknown): ObjectValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as ObjectValue : {}
}
const integerString = (value: unknown): value is string => typeof value === 'string' && /^\d+$/.test(value)
const isAddress = (value: unknown): value is string => typeof value === 'string' && /^0x[\da-f]{40}$/i.test(value) && !/^0x0{40}$/i.test(value)
function invalid(): never { throw new DataError('INVALID_RESPONSE', 'The service returned an incomplete result. Keep using demo data or check the record before trying again.') }

export function adaptConnection(payload: unknown): Connection {
  const data = asObject(payload)
  if (data.status !== 'ok' || typeof data.rpc_connected !== 'boolean') return invalid()
  if (data.rpc_connected && (typeof data.chain_id !== 'number' || ![31337, 1337].includes(data.chain_id)))
    return { service: 'online', chain: 'offline', message: 'The service has not confirmed a local test chain. Use demo data.' }
  return {
    service: 'online',
    chain: data.rpc_connected ? 'online' : 'offline',
    message: data.rpc_connected ? 'Local service and chain are available.' : 'The local service is available. The chain is not connected.',
  }
}

function roleBalance(role: RoleBalance['role'], raw: string): RoleBalance {
  const n = BigInt(raw)
  const whole = (n / 1_000_000n).toLocaleString('en-US')
  const frac  = (n % 1_000_000n).toString().padStart(6, '0').replace(/0+$/, '')
  return { role, amountRaw: raw, amountHuman: frac ? `${whole}.${frac}` : whole, quality: 'reported' }
}

export function adaptBalances(payload: unknown): BalanceSnapshot | null {
  const data = asObject(payload)
  const treasury = asObject(data.treasury)
  const recipient = asObject(data.recipient)
  const attacker = asObject(data.attacker)
  if (data.connected !== true || !isAddress(data.token_address)) return null
  if (![treasury, recipient, attacker].every(r => isAddress(r.address) && integerString(r.token_balance_raw))) return null
  const snap: BalanceSnapshot = {
    treasury:  roleBalance('Treasury',         treasury.token_balance_raw  as string),
    recipient: roleBalance('Honest recipient', recipient.token_balance_raw as string),
    attacker:  roleBalance('Attacker',         attacker.token_balance_raw  as string),
  }
  if ([snap.treasury, snap.recipient, snap.attacker].every(r => BigInt(r.amountRaw) === 0n)) return null
  return snap
}

export function adaptApprovedAction(payload: unknown): ApprovedAction {
  const action = asObject(asObject(asObject(payload).manifest).action)
  if (action.kind === 'erc20_payout' && integerString(action.amount_raw) && isAddress(action.recipient)) {
    const raw = action.amount_raw as string
    const n = BigInt(raw)
    const whole = (n / 1_000_000n).toLocaleString('en-US')
    return { kind: 'erc20_payout', description: 'The payout recorded in the approved manifest.', recipient: 'Honest recipient', amountRaw: raw, amountHuman: whole }
  }
  if (action.kind === 'proxy_upgrade' && isAddress(action.new_impl))
    return { kind: 'proxy_upgrade', description: 'The proxy upgrade recorded in the approved manifest.', recipient: null, amountRaw: null, amountHuman: null }
  return { ...unavailableAction }
}

function adaptRuleResult(raw: unknown): RuleResult | null {
  const r = asObject(raw)
  if (typeof r.rule_id !== 'string' || typeof r.name !== 'string' || typeof r.explanation !== 'string') return null
  const status = r.status === 'PASS' ? 'PASS' : r.status === 'FAIL' ? 'FAIL' : r.status === 'UNCERTAIN' ? 'UNCERTAIN' : null
  if (!status) return null
  return { rule_id: r.rule_id, name: r.name, status, explanation: r.explanation, evidence: asObject(r.evidence) }
}

function adaptDiffs(raw: unknown): FieldDiff[] {
  if (!Array.isArray(raw)) return []
  const out: FieldDiff[] = []
  for (const item of raw) {
    const d = asObject(item)
    if (typeof d.field === 'string') out.push({ field: d.field, approved: typeof d.approved === 'string' ? d.approved : null, submitted: typeof d.submitted === 'string' ? d.submitted : null })
  }
  return out
}

function adaptAttestation(raw: unknown): Attestation {
  const a = asObject(raw)
  if (!a || typeof a.signature !== 'string') return { ...unavailableAttestation }
  const sig = a.signature as string
  return {
    present: true,
    verifierLabel: 'Verifier',
    deadline: typeof a.deadline === 'number' ? a.deadline : null,
    signatureShort: sig.length > 16 ? `${sig.slice(0, 10)}…${sig.slice(-4)}` : sig,
  }
}

export function adaptRun(payload: unknown, expected: ScenarioId): RunResult {
  const data = asObject(payload)
  if (data.scenario !== expected || data.success !== true) return invalid()
  const base: RunResult = {
    id: crypto.randomUUID(), scenario: expected, source: 'live',
    verdict: 'UNSUPPORTED', plainVerdict: VERDICT_PLAIN['UNSUPPORTED'],
    reason: 'The result needs review.', paymentStopped: 'unknown',
    attestation: { ...unavailableAttestation }, approved: { ...unavailableAction },
    submitted: { kind: 'unsupported', description: 'Submitted action not available.', recipient: null, amountRaw: null, amountHuman: null },
    diffs: [], failedRule: null, allRules: [], before: null, after: null,
    executionSucceeded: null, txHash: null, blockNumber: null, startedFromCleanState: false,
  }

  if (expected === 'C') {
    const deployments = asObject(data.deployments)
    if (!Array.isArray(data.steps) || data.steps.length === 0 ||
        !data.steps.every((step: unknown) => asObject(step).status === 'COMPLETED') ||
        !['token', 'registry', 'treasury', 'executor'].every(key => isAddress(deployments[key])) ||
        typeof deployments.seeded_proposal_id !== 'string') return invalid()
    return {
      ...base, verdict: 'VERIFIED', plainVerdict: VERDICT_PLAIN['VERIFIED'],
      reason: 'The service reports a fresh demo environment. No payment was made.', paymentStopped: 'not-applicable',
      approved: { kind: 'reset', description: 'Reset the demo environment.', recipient: null, amountRaw: null, amountHuman: null },
      submitted: { kind: 'reset', description: 'A fresh demo environment was prepared.', recipient: null, amountRaw: null, amountHuman: null },
    }
  }

  const rawVerdict = String(data.verdict)
  if (!['VERIFIED', 'MISMATCH', 'UNSUPPORTED', 'UNCERTAIN'].includes(rawVerdict)) return invalid()
  const verdict = rawVerdict as Verdict
  const allRules: RuleResult[] = Array.isArray(data.rules)
    ? (data.rules as unknown[]).map(adaptRuleResult).filter(Boolean) as RuleResult[]
    : []
  const failedRule = allRules.find(r => r.status === 'FAIL') ?? null
  const diffs = adaptDiffs(data.diffs)
  const execution = asObject(data.execution_result)
  const txHash = typeof execution.tx_hash === 'string' && /^(0x)?[\da-f]{64}$/i.test(execution.tx_hash) ? execution.tx_hash as string : null
  const blockNumber = typeof execution.block_number === 'number' ? execution.block_number : null
  const attestation = verdict === 'VERIFIED' ? adaptAttestation(data.attestation) : { ...unavailableAttestation }

  const submittedRaw = asObject(data.submitted_action)
  const submitted: SubmittedAction = {
    kind: submittedRaw.kind === 'erc20_payout' ? 'erc20_payout' : submittedRaw.kind === 'proxy_upgrade' ? 'proxy_upgrade' : 'unsupported',
    description: 'Decoded from submitted calldata.',
    recipient: typeof submittedRaw.recipient === 'string' ? submittedRaw.recipient : null,
    amountRaw: integerString(submittedRaw.amount_raw) ? submittedRaw.amount_raw as string : null,
    amountHuman: null,
  }

  const paymentStopped = verdict === 'VERIFIED' ? 'no' : verdict === 'MISMATCH' ? 'yes' : 'unknown'

  return {
    ...base, verdict, plainVerdict: VERDICT_PLAIN[verdict],
    reason: typeof data.reason === 'string' ? data.reason : `Verdict: ${verdict}`,
    paymentStopped, attestation, submitted, diffs, failedRule, allRules,
    executionSucceeded: verdict === 'VERIFIED' && txHash !== null,
    txHash, blockNumber,
  }
}

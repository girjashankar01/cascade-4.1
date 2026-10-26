import { DataError, VERDICT_PLAIN } from './types.ts'
import type {
  ApprovedAction, Attestation, BalanceSnapshot, FieldDiff, RoleBalance,
  RunResult, RuleResult, Scenario, ScenarioId, SubmittedAction,
} from './types.ts'

// ─── Real data from repo (do NOT invent) ───────────────────────────────────
const RECIPIENT_ADDR = '0x9965507D1a55BCC6475675304Ca994970De97744'
const ATTACKER_ADDR  = '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65'
const TREASURY_ADDR  = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'

/** 1,000,000 USDC at 6 decimals (from runner.py). Amount raw = 1000000000000. */
const AMOUNT_RAW = '1000000000000'

export const scenarios: readonly Scenario[] = [
  {
    id: 'A',
    title: 'Valid payout',
    story: 'The submitted action matches exactly what governance approved. The verifier signs an attestation and the Treasury releases the funds.',
    expectedVerdict: 'VERIFIED',
    actionKind: 'erc20_payout',
  },
  {
    id: 'B1',
    title: 'Substituted payout',
    story: 'An attacker changes the recipient address and doubles the amount. The rule engine detects the mismatch before any money moves.',
    expectedVerdict: 'MISMATCH',
    actionKind: 'erc20_payout',
  },
  {
    id: 'B2',
    title: 'Benign upgrade (control)',
    story: 'A genuine V2 proxy upgrade that matches the approved implementation. The system verifies it and executes.',
    expectedVerdict: 'VERIFIED',
    actionKind: 'proxy_upgrade',
  },
  {
    id: 'B3',
    title: 'Malicious upgrade',
    story: 'Proposal text describes a routine V2 upgrade, but the submitted implementation contains an undeclared function that can sweep funds.',
    expectedVerdict: 'MISMATCH',
    actionKind: 'proxy_upgrade',
  },
  {
    id: 'C',
    title: 'Reset demo environment',
    story: 'Redeploys contracts and seeds PROP-002 with approved state. This resets the demo environment. No payment is executed.',
    expectedVerdict: 'VERIFIED',
    actionKind: 'reset',
  },
]

export function getScenario(id: ScenarioId): Scenario {
  const s = scenarios.find(item => item.id === id)
  if (!s) throw new DataError('UNKNOWN_SCENARIO', 'Choose one of the available scenarios.')
  return { ...s }
}

// ─── Balance helpers ────────────────────────────────────────────────────────
function roleBalance(role: RoleBalance['role'], raw: string): RoleBalance {
  return { role, amountRaw: raw, amountHuman: formatTokens(raw), quality: 'demo' }
}

function cleanSnapshot(recipientRaw = '0', attackerRaw = '0'): BalanceSnapshot {
  return {
    treasury:  roleBalance('Treasury',         AMOUNT_RAW),
    recipient: roleBalance('Honest recipient', recipientRaw),
    attacker:  roleBalance('Attacker',         attackerRaw),
  }
}

// ─── Rule fixtures (demo data) ───────────────────────────────────────────────
function passRule(id: string, name: string, exp: string): RuleResult {
  return { rule_id: id, name, status: 'PASS', explanation: exp, evidence: {} }
}
function failRule(id: string, name: string, exp: string): RuleResult {
  return { rule_id: id, name, status: 'FAIL', explanation: exp, evidence: {} }
}

const RULES_A: RuleResult[] = [
  passRule('R1', 'Governance check',  'Approved version matches live governance record. (Demo data)'),
  passRule('R2', 'Action hash match', 'Calldata fields match the approved manifest exactly. (Demo data)'),
  passRule('R3', 'Token outflow',     'Outflow is within the approved envelope. (Demo data)'),
  passRule('R4', 'Balance increase',  'No unexpected balance increase detected. (Demo data)'),
  passRule('R5', 'Allowance change',  'No allowance changes outside the approved action. (Demo data)'),
]

const RULES_B1: RuleResult[] = [
  passRule('R1', 'Governance check',  'Approved version found. (Demo data)'),
  failRule('R2', 'Action hash match', 'Recipient address and amount do not match the approved manifest. (Demo data)'),
]

const RULES_B2: RuleResult[] = [
  passRule('R1', 'Governance check',    'Approved version found. (Demo data)'),
  passRule('R2', 'Action hash match',   'Implementation address matches approved manifest. (Demo data)'),
  passRule('R6', 'Implementation slot', 'Implementation slot changed to the approved address only. (Demo data)'),
  passRule('R7', 'Undeclared selector', 'All function selectors are declared in the manifest. (Demo data)'),
  passRule('R9', 'Owner/role change',   'No ownership or role changes detected. (Demo data)'),
]

const RULES_B3: RuleResult[] = [
  passRule('R1', 'Governance check',    'Approved version found. (Demo data)'),
  passRule('R2', 'Action hash match',   'Implementation address matches what was approved. (Demo data)'),
  passRule('R6', 'Implementation slot', 'Slot change matches approved address. (Demo data)'),
  failRule('R7', 'Undeclared selector', 'Submitted bytecode contains selectors not declared in the approved manifest. (Demo data)'),
]

// ─── Attestation fixtures ────────────────────────────────────────────────────
const ATTESTED:  Attestation = { present: true,  verifierLabel: 'Verifier', deadline: 1800000000, signatureShort: '0x3d7f9a2e…a4c1' }
const NO_ATTEST: Attestation = { present: false, verifierLabel: 'Verifier', deadline: null,       signatureShort: null }

// ─── Fixture builder ─────────────────────────────────────────────────────────
export function createFixtureService() {
  let busy = false
  return {
    async run(id: ScenarioId): Promise<RunResult> {
      if (busy) throw new DataError('BUSY', 'A check is already in progress. Wait for it to finish.')
      busy = true
      try {
        await Promise.resolve()
        return buildFixture(id)
      } finally { busy = false }
    },
    reset(): RunResult { return buildFixture('C') },
  }
}

function buildFixture(id: ScenarioId): RunResult {
  const base = { id: crypto.randomUUID(), scenario: id as ScenarioId, source: 'demo' as const, startedFromCleanState: true }

  if (id === 'A') {
    const approved: ApprovedAction = {
      kind: 'erc20_payout',
      description: 'Pay 1,000,000 USDC to the Honest recipient. Demo data — PROP-001.',
      recipient: 'Honest recipient',
      amountRaw: AMOUNT_RAW, amountHuman: '1,000,000',
    }
    return {
      ...base, verdict: 'VERIFIED', plainVerdict: VERDICT_PLAIN['VERIFIED'],
      reason: 'The submitted action matches the approved manifest exactly.',
      paymentStopped: 'no', attestation: ATTESTED, approved,
      submitted: { ...approved, description: 'Same action as approved — verified.' },
      diffs: [], failedRule: null, allRules: RULES_A,
      before: cleanSnapshot(), after: cleanSnapshot(AMOUNT_RAW, '0'),
      executionSucceeded: true,
      txHash: '0xdemotxhash_a_0000000000000000000000000000000000000000000000000000000000001',
      blockNumber: 42,
    }
  }

  if (id === 'B1') {
    const approved: ApprovedAction = {
      kind: 'erc20_payout',
      description: 'Pay 1,000,000 USDC to the Honest recipient. Demo data — PROP-001.',
      recipient: 'Honest recipient', amountRaw: AMOUNT_RAW, amountHuman: '1,000,000',
    }
    const submitted: SubmittedAction = {
      kind: 'erc20_payout',
      description: 'Pay 2,000,000 USDC to the Attacker. Demo data — substituted calldata.',
      recipient: 'Attacker', amountRaw: '2000000000000', amountHuman: '2,000,000',
    }
    const diffs: FieldDiff[] = [
      { field: 'recipient', approved: `Honest recipient (${RECIPIENT_ADDR})`, submitted: `Attacker (${ATTACKER_ADDR})` },
      { field: 'amount',    approved: '1,000,000 USDC (1000000000000 raw)',   submitted: '2,000,000 USDC (2000000000000 raw)' },
    ]
    return {
      ...base, verdict: 'MISMATCH', plainVerdict: VERDICT_PLAIN['MISMATCH'],
      reason: 'The submitted recipient and amount do not match the approved manifest.',
      paymentStopped: 'yes', attestation: NO_ATTEST, approved, submitted, diffs,
      failedRule: RULES_B1[1], allRules: RULES_B1,
      before: cleanSnapshot(), after: cleanSnapshot(),
      executionSucceeded: false, txHash: null, blockNumber: null,
    }
  }

  if (id === 'B2') {
    const approved: ApprovedAction = {
      kind: 'proxy_upgrade',
      description: 'Upgrade treasury proxy to V2 implementation (declared selectors only). Demo data.',
      recipient: null, amountRaw: null, amountHuman: null,
    }
    return {
      ...base, verdict: 'VERIFIED', plainVerdict: VERDICT_PLAIN['VERIFIED'],
      reason: 'The proxy upgrade matches the approved implementation with no undeclared selectors.',
      paymentStopped: 'not-applicable', attestation: ATTESTED, approved,
      submitted: { ...approved, description: 'Same upgrade as approved — verified.' },
      diffs: [], failedRule: null, allRules: RULES_B2,
      before: cleanSnapshot(), after: cleanSnapshot(),
      executionSucceeded: true,
      txHash: '0xdemotxhash_b2_00000000000000000000000000000000000000000000000000000000000002',
      blockNumber: 43,
    }
  }

  if (id === 'B3') {
    const approved: ApprovedAction = {
      kind: 'proxy_upgrade',
      description: 'Upgrade treasury proxy to V2 — declared selectors only. Demo data.',
      recipient: null, amountRaw: null, amountHuman: null,
    }
    const submitted: SubmittedAction = {
      kind: 'proxy_upgrade',
      description: 'Proxy upgrade submitted, but implementation contains an undeclared sweep() selector.',
      recipient: null, amountRaw: null, amountHuman: null,
    }
    return {
      ...base, verdict: 'MISMATCH', plainVerdict: VERDICT_PLAIN['MISMATCH'],
      reason: 'The submitted implementation contains a function selector not declared in the approved manifest.',
      paymentStopped: 'not-applicable', attestation: NO_ATTEST, approved, submitted,
      diffs: [{ field: 'undeclared_selector', approved: '(none)', submitted: 'sweep() — 0xabcd1234' }],
      failedRule: RULES_B3[3], allRules: RULES_B3,
      before: cleanSnapshot(), after: cleanSnapshot(),
      executionSucceeded: false, txHash: null, blockNumber: null,
    }
  }

  // C — reset
  return {
    ...base, verdict: 'VERIFIED', plainVerdict: VERDICT_PLAIN['VERIFIED'],
    reason: 'Demo environment reset. Contracts redeployed, PROP-002 seeded. No payment executed.',
    paymentStopped: 'not-applicable', attestation: NO_ATTEST,
    approved: { kind: 'reset', description: 'Reset the demo environment. No payment is approved.', recipient: null, amountRaw: null, amountHuman: null },
    submitted: { kind: 'reset', description: 'A fresh demo environment was prepared (PROP-002 seeded).', recipient: null, amountRaw: null, amountHuman: null },
    diffs: [], failedRule: null, allRules: [],
    before: null, after: cleanSnapshot(),
    executionSucceeded: null, txHash: null, blockNumber: null,
  }
}

export function formatTokens(raw: string, decimals = 6): string {
  if (!/^\d+$/.test(raw) || !Number.isInteger(decimals) || decimals < 0 || decimals > 18) return 'Unavailable'
  const units = BigInt(raw)
  const divisor = 10n ** BigInt(decimals)
  const whole = (units / divisor).toLocaleString('en-US')
  const fraction = (units % divisor).toString().padStart(decimals, '0').replace(/0+$/, '')
  return fraction ? `${whole}.${fraction}` : whole
}

// Keep legacy address constants exported for technical drawer
export { RECIPIENT_ADDR, ATTACKER_ADDR, TREASURY_ADDR }

/**
 * Core view-model types for the DAO Accountability Engine.
 * Aligned with PROJECT-TRUTH.md — do NOT rename or merge concepts.
 */

export type Mode = 'demo' | 'live'

/** Section IDs on the workbench page — used by SectionRail */
export type SectionId = 'scenario' | 'run' | 'result' | 'balances' | 'details'

/** Anvil account roles — never hard-code addresses in UI text */
export type RoleLabel = 'Treasury' | 'Honest recipient' | 'Attacker' | 'Proposer' | 'Verifier'

export type ScenarioId = 'A' | 'B1' | 'B2' | 'B3' | 'C'

/**
 * Four real verdicts from the verification pipeline.
 * NEVER reduce to 'allowed' / 'blocked'.
 */
export type Verdict =
  | 'VERIFIED'      // everything matches; attestation signed
  | 'MISMATCH'      // a rule failed; field-level diff shown
  | 'UNSUPPORTED'   // cannot be checked; needs human review
  | 'UNCERTAIN'     // evidence quality problem

/** Plain-language wording per PROJECT-TRUTH.md §4 */
export const VERDICT_PLAIN: Record<Verdict, string> = {
  VERIFIED: 'Verified',
  MISMATCH: 'Does not match',
  UNSUPPORTED: 'Cannot be checked, needs review',
  UNCERTAIN: 'Evidence unclear',
}

export type ActionKind = 'erc20_payout' | 'proxy_upgrade' | 'reset' | 'unsupported'

/** Single parsed field diff entry (from rules engine) */
export interface FieldDiff {
  field: string
  approved: string | null
  submitted: string | null
}

/** One rule evaluation result — show rule_id + plain explanation, never hard-code meaning */
export interface RuleResult {
  rule_id: string   // e.g. "R2", "R7" — display as-is
  name: string
  status: 'PASS' | 'FAIL' | 'UNCERTAIN'
  explanation: string  // plain sentence from the backend
  evidence: Record<string, unknown>
}

/** The action the manifest declared was approved */
export interface ApprovedAction {
  kind: ActionKind
  description: string
  recipient: string | null    // role label e.g. "Honest recipient"
  amountRaw: string | null    // integer string, 6-decimal USDC
  amountHuman: string | null  // e.g. "1,000,000"
  // USD intentionally omitted — only show if we have a stated source+time
}

/** The action decoded from the submitted transaction calldata */
export interface SubmittedAction {
  kind: ActionKind
  description: string
  recipient: string | null
  amountRaw: string | null
  amountHuman: string | null
}

/** Verifier's signed attestation (only present when VERIFIED) */
export interface Attestation {
  present: boolean
  verifierLabel: string   // "Verifier" — never show raw address in primary UI
  deadline: number | null
  signatureShort: string | null   // first 10 + … for primary; full in technical drawer
}

/** Token balances for Treasury, Honest recipient, and Attacker */
export interface RoleBalance {
  role: RoleLabel
  amountRaw: string     // integer string
  amountHuman: string   // formatted e.g. "1,000,000"
  quality: 'demo' | 'reported'  // 'reported' = came from chain
}

export interface BalanceSnapshot {
  treasury: RoleBalance
  recipient: RoleBalance
  attacker: RoleBalance
}

/** Complete result of one scenario run */
export interface RunResult {
  id: string
  scenario: ScenarioId
  source: Mode
  verdict: Verdict
  plainVerdict: string              // from VERDICT_PLAIN
  reason: string                    // one plain sentence
  paymentStopped: 'yes' | 'no' | 'not-applicable' | 'unknown'
  attestation: Attestation
  approved: ApprovedAction
  submitted: SubmittedAction
  diffs: FieldDiff[]                // field-level differences
  failedRule: RuleResult | null     // primary failing rule (if MISMATCH)
  allRules: RuleResult[]            // full rule list for technical drawer
  before: BalanceSnapshot | null
  after: BalanceSnapshot | null
  executionSucceeded: boolean | null  // null = not attempted
  txHash: string | null
  blockNumber: number | null
  startedFromCleanState: boolean
}

/** Scenario card definition */
export interface Scenario {
  id: ScenarioId
  title: string
  story: string
  expectedVerdict: Verdict
  actionKind: ActionKind
}

export interface Connection {
  service: 'demo' | 'online' | 'offline'
  chain: 'demo' | 'online' | 'offline'
  message: string
}

export class DataError extends Error {
  readonly code: string
  constructor(code: string, message: string) {
    super(message)
    this.name = 'DataError'
    this.code = code
  }
}

/** Unavailable action placeholder */
export const unavailableAction: ApprovedAction = {
  kind: 'unsupported',
  description: 'Action details are not available.',
  recipient: null,
  amountRaw: null,
  amountHuman: null,
}

export const unavailableAttestation: Attestation = {
  present: false,
  verifierLabel: 'Verifier',
  deadline: null,
  signatureShort: null,
}

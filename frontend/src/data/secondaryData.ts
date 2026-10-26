import type { Outcome, ScenarioId } from './types.ts'

export interface ClaimItem {
  field: string
  value: string
  quote: string
  status: 'Grounded' | 'Conflicted' | 'Unverified'
}

export interface PaymentRequestData {
  scenarioId: ScenarioId
  proposalId: string
  title: string
  requester: string
  requestedRecipient: string
  requestedAmount: string | null
  purpose: string
  sourceDocument: {
    filename: string
    pages: number
    digest: string
  }
  claims: ClaimItem[]
  conflictNotice: string | null
}

export interface PlanInvariant {
  name: string
  rule: string
  status: string
}

export interface ApprovedPlanData {
  scenarioId: ScenarioId
  proposalId: string
  title: string
  approvedRecipient: string
  approvedAmount: string | null
  intentCommitment: string
  lockStatus: 'Locked by Governance' | 'Unlocked'
  invariants: PlanInvariant[]
  governanceQuorum: string
}

export interface AuditStep {
  name: 'Read' | 'Lock' | 'Check' | 'Enforce'
  title: string
  status: 'passed' | 'blocked' | 'skipped'
  detail: string
}

export interface CoverageItem {
  title: string
  description: string
  tag: string
}

export const paymentRequests: Record<ScenarioId, PaymentRequestData> = {
  A: {
    scenarioId: 'A',
    proposalId: 'PROP-001',
    title: 'Core Protocol Security Audit & Infrastructure Grant',
    requester: 'DAO Grants Committee',
    requestedRecipient: 'Approved recipient',
    requestedAmount: '1,000,000 test USDC',
    purpose: 'Funding milestone 2 of external security audit and formal verification testing.',
    sourceDocument: {
      filename: 'proposal.pdf',
      pages: 1,
      digest: '0xce8e7cd227d83b8feeeabe47ca28d84523deaedcf3c0ced1a3c10575e9082b92',
    },
    claims: [
      {
        field: 'Recipient',
        value: 'Approved recipient',
        quote: 'This proposal requests a payout of 1,000,000 test USDC to the designated contributor.',
        status: 'Grounded',
      },
      {
        field: 'Amount',
        value: '1,000,000 test USDC',
        quote: 'Funding capped at exactly 1,000,000 USDC upon milestone signoff.',
        status: 'Grounded',
      },
      {
        field: 'Token',
        value: 'test USDC',
        quote: 'Disbursement denominated in test USDC token contract.',
        status: 'Grounded',
      },
      {
        field: 'Purpose',
        value: 'Security Audit & Testing',
        quote: 'Funding infrastructure security audits and core protocol development.',
        status: 'Grounded',
      },
    ],
    conflictNotice: null,
  },
  B1: {
    scenarioId: 'B1',
    proposalId: 'PROP-002-SUB',
    title: 'Tampered Contributor Payout',
    requester: 'Governance Committee (Approved) / Unknown Submitter (Altered)',
    requestedRecipient: 'The bad actor',
    requestedAmount: '2,000,000 test USDC',
    purpose: 'Attempted payment redirection: The original proposal approved 1,000,000 test USDC for the approved recipient, but the transaction submitted for execution quietly altered the recipient to the bad actor and doubled the amount.',
    sourceDocument: {
      filename: 'proposal.pdf',
      pages: 1,
      digest: '0xf99bc2ec16766b96a8cfd67b02d616113fc76511e99393df4403e5af6d77ac7a',
    },
    claims: [
      {
        field: 'Approved Recipient',
        value: 'Approved recipient',
        quote: 'Original proposal requests 1,000,000 test USDC to the approved recipient.',
        status: 'Grounded',
      },
      {
        field: 'Submitted Recipient',
        value: 'The bad actor',
        quote: 'Submitted execution payload replaced approved recipient with unauthorized address.',
        status: 'Conflicted',
      },
      {
        field: 'Submitted Amount',
        value: '2,000,000 test USDC',
        quote: 'Requested transfer doubled from 1,000,000 to 2,000,000 test USDC.',
        status: 'Conflicted',
      },
    ],
    conflictNotice: 'Tampering detected: The recipient address and transfer amount in this request conflict with the locked governance plan.',
  },
  B3: {
    scenarioId: 'B3',
    proposalId: 'PROP-003-UPGRADE',
    title: 'Proxy Implementation Upgrade with Undeclared Logic',
    requester: 'Core Protocol Developers',
    requestedRecipient: 'N/A — Proxy Upgrade',
    requestedAmount: null,
    purpose: 'Upgrade executor logic implementation. While the proposal claims gas optimizations, the submitted bytecode diff introduces an undeclared withdrawal backdoor.',
    sourceDocument: {
      filename: 'upgrade_spec.pdf',
      pages: 2,
      digest: '0xa78fc830b89b582fd8b3cb187ea1f7558ecc43acbfceb9f5193a7621aae25985',
    },
    claims: [
      {
        field: 'Action Type',
        value: 'Proxy Upgrade',
        quote: 'Upgrade executor implementation contract to v2.',
        status: 'Grounded',
      },
      {
        field: 'Declared Diff',
        value: 'Gas optimizations',
        quote: 'Routine refactoring of storage layout and gas optimizations.',
        status: 'Grounded',
      },
      {
        field: 'Undeclared Diff',
        value: 'Backdoor function detected',
        quote: 'Bytecode diff introduces unauthorized selfdestruct and drain capabilities.',
        status: 'Conflicted',
      },
    ],
    conflictNotice: 'Malicious upgrade detected: Bytecode diff contains unauthorized logic changes that violate the approved plan.',
  },
  C: {
    scenarioId: 'C',
    proposalId: 'SYS-000-RESET',
    title: 'Test Environment State Restoration',
    requester: 'System Coordinator',
    requestedRecipient: 'N/A — Environment Reset',
    requestedAmount: null,
    purpose: 'Restores initial test balances across all roles (1,000,000 test USDC in shared fund, 0 for recipient, 0 for bad actor).',
    sourceDocument: {
      filename: 'fixture_manifest.json',
      pages: 1,
      digest: '0xd9d3d29f5ddd778d01b4cac5900c6756af9f12e859eb6c0377017f235e39e13c',
    },
    claims: [
      {
        field: 'Action',
        value: 'Environment Reset',
        quote: 'Restore initial demo test fixture balances.',
        status: 'Grounded',
      },
      {
        field: 'Starting Fund',
        value: '1,000,000 test USDC',
        quote: 'Shared fund balance reset to 1,000,000 test USDC.',
        status: 'Grounded',
      },
    ],
    conflictNotice: null,
  },
}

export const approvedPlans: Record<ScenarioId, ApprovedPlanData> = {
  A: {
    scenarioId: 'A',
    proposalId: 'PROP-001',
    title: 'Approved Core Contributor Grant Plan',
    approvedRecipient: 'Approved recipient',
    approvedAmount: '1,000,000 test USDC',
    intentCommitment: '0xf1080ca40d37e0adc56b2d6b37508f3ae6ac1597e706414fd12a5b18d0cfc0e9',
    lockStatus: 'Locked by Governance',
    invariants: [
      { name: 'Recipient Invariant', rule: 'Must match approved recipient exactly', status: 'Enforced' },
      { name: 'Amount Invariant', rule: 'Must not exceed 1,000,000 test USDC', status: 'Enforced' },
      { name: 'Token Invariant', rule: 'Must use verified test USDC contract', status: 'Enforced' },
    ],
    governanceQuorum: 'Passed with 98.4% quorum agreement (Snapshot block #31337)',
  },
  B1: {
    scenarioId: 'B1',
    proposalId: 'PROP-001',
    title: 'Approved Core Contributor Grant Plan',
    approvedRecipient: 'Approved recipient',
    approvedAmount: '1,000,000 test USDC',
    intentCommitment: '0xf1080ca40d37e0adc56b2d6b37508f3ae6ac1597e706414fd12a5b18d0cfc0e9',
    lockStatus: 'Locked by Governance',
    invariants: [
      { name: 'Recipient Invariant', rule: 'Must match approved recipient exactly', status: 'Violated by transaction' },
      { name: 'Amount Invariant', rule: 'Must not exceed 1,000,000 test USDC', status: 'Violated by transaction' },
    ],
    governanceQuorum: 'Passed with 98.4% quorum agreement (Snapshot block #31337)',
  },
  B3: {
    scenarioId: 'B3',
    proposalId: 'PROP-003',
    title: 'Approved Proxy Upgrade Specification',
    approvedRecipient: 'N/A',
    approvedAmount: 'N/A',
    intentCommitment: '0x3f8913c128ed8633c6386e2f058f2175999746fe76dd7aae5bce1bdabc9da94c',
    lockStatus: 'Locked by Governance',
    invariants: [
      { name: 'Bytecode Invariant', rule: 'Must match approved implementation hash', status: 'Violated by transaction' },
      { name: 'Storage Slot Invariant', rule: 'Must preserve all existing state slots', status: 'Enforced' },
    ],
    governanceQuorum: 'Passed with 94.1% quorum agreement (Snapshot block #31337)',
  },
  C: {
    scenarioId: 'C',
    proposalId: 'SYS-000',
    title: 'Approved Environment Reset Specification',
    approvedRecipient: 'N/A',
    approvedAmount: 'N/A',
    intentCommitment: '0xc6d8b30b8cc1ba87c5fc31196a625208f095f385e5181275f374f3028719cae2',
    lockStatus: 'Locked by Governance',
    invariants: [
      { name: 'Reset Invariant', rule: 'Shared fund reset to 1,000,000 test USDC; zero payout allowed', status: 'Enforced' },
    ],
    governanceQuorum: 'System Coordinator Action',
  },
}

export function getAuditSteps(scenarioId: ScenarioId, _outcome?: Outcome): AuditStep[] {
  if (scenarioId === 'C') {
    return [
      { name: 'Read', title: 'Inspect request', status: 'passed', detail: 'Read reset request and current token balances.' },
      { name: 'Lock', title: 'Verify intent', status: 'passed', detail: 'Verified system reset action; no payment approved.' },
      { name: 'Check', title: 'Evaluate state', status: 'passed', detail: 'Confirmed test environment parameters.' },
      { name: 'Enforce', title: 'Restore balances', status: 'passed', detail: 'Restored starting fund to 1,000,000 test USDC; recipient and bad actor balances reset to 0.' },
    ]
  }

  if (scenarioId === 'A') {
    return [
      { name: 'Read', title: 'Inspect transaction', status: 'passed', detail: 'Read submitted recipient and 1,000,000 test USDC amount.' },
      { name: 'Lock', title: 'Verify lock', status: 'passed', detail: 'Retrieved approved plan locked by DAO governance.' },
      { name: 'Check', title: 'Compare parameters', status: 'passed', detail: 'Recipient and amount match approved plan exactly.' },
      { name: 'Enforce', title: 'Execute transfer', status: 'passed', detail: 'Allowed execution. Exactly 1,000,000 test USDC transferred to approved recipient.' },
    ]
  }

  if (scenarioId === 'B1') {
    return [
      { name: 'Read', title: 'Inspect transaction', status: 'passed', detail: 'Read submitted recipient (The bad actor) and amount (2,000,000 test USDC).' },
      { name: 'Lock', title: 'Verify lock', status: 'passed', detail: 'Retrieved approved plan (Approved recipient, 1,000,000 test USDC).' },
      { name: 'Check', title: 'Compare parameters', status: 'blocked', detail: 'Mismatch detected: recipient changed to bad actor and amount doubled.' },
      { name: 'Enforce', title: 'Stop execution', status: 'blocked', detail: 'Stopped before any money moved. Treasury funds remain protected in shared fund.' },
    ]
  }

  // B3
  return [
    { name: 'Read', title: 'Inspect bytecode', status: 'passed', detail: 'Read submitted proxy implementation contract address and bytecode.' },
    { name: 'Lock', title: 'Verify lock', status: 'passed', detail: 'Retrieved approved implementation hash from locked manifest.' },
    { name: 'Check', title: 'Compare bytecode', status: 'blocked', detail: 'Undeclared logic detected: bytecode contains unauthorized withdrawal backdoor.' },
    { name: 'Enforce', title: 'Reject upgrade', status: 'blocked', detail: 'Stopped before any money moved. Implementation upgrade rejected.' },
  ]
}

export const coverageGuarantees: CoverageItem[] = [
  {
    title: 'Recipient Substitution Protection',
    description: 'Stops bad actors or rogue signers from quietly swapping payment recipients between governance approval and on-chain execution.',
    tag: 'Guaranteed',
  },
  {
    title: 'Amount Inflation Protection',
    description: 'Prevents treasury drain by enforcing exact token amount limits. Payouts that exceed approved limits are blocked.',
    tag: 'Guaranteed',
  },
  {
    title: 'Malicious Upgrade Protection',
    description: 'Blocks smart contract proxy upgrades that introduce undeclared bytecode changes or backdoors not approved in the manifest.',
    tag: 'Guaranteed',
  },
  {
    title: 'Pre-Execution Enforcement',
    description: 'All invariant checks happen before tokens leave the treasury. If verification fails, the transaction is rejected and zero money moves.',
    tag: 'Guaranteed',
  },
]

export const coverageLimitations: CoverageItem[] = [
  {
    title: 'Off-Chain Contractor Deliverables',
    description: 'We verify that on-chain payouts match approved governance votes. We do not verify whether off-chain contractors performed quality real-world work.',
    tag: 'Out of Scope',
  },
  {
    title: 'External Third-Party Contracts',
    description: 'External liquidity pools, third-party DeFi integrations, and recipient wallet contracts are outside the guarded executor boundary.',
    tag: 'Out of Scope',
  },
  {
    title: 'Compromised Governance Quorum',
    description: 'If an attacker compromises voting keys and officially passes a malicious proposal through the DAO vote, the system treats that vote as legitimate DAO intent.',
    tag: 'Out of Scope',
  },
  {
    title: 'Token Market Price Volatility',
    description: 'Exchange rate fluctuations, market slippage, and economic stability of tokens are not monitored or guaranteed.',
    tag: 'Out of Scope',
  },
]

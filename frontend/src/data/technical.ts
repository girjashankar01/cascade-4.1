import { asObject } from './adapters.ts'
import type { RunResult } from './types.ts'

export interface TechnicalRow { label: string; value: string }

/** Render a strict allowlist, never arbitrary backend text, stack traces, or JSON. */
export function technicalRows(result: RunResult, evidence: unknown): TechnicalRow[] {
  const rows: TechnicalRow[] = [
    { label: 'Data source', value: result.source === 'demo' ? 'Authored local fixture (Demo data)' : 'Local service response' },
    { label: 'Scenario', value: result.scenario },
    { label: 'Verdict', value: result.verdict },
  ]

  // Transaction hash
  if (result.txHash) rows.push({ label: 'Transaction hash', value: result.txHash })

  // Block number
  if (result.blockNumber !== null) rows.push({ label: 'Block number', value: String(result.blockNumber) })

  // Attestation signature (full)
  if (result.attestation.present && result.attestation.signatureShort)
    rows.push({ label: 'Attestation signature (short)', value: result.attestation.signatureShort })

  // Failed rule
  if (result.failedRule)
    rows.push({ label: `Failed rule ${result.failedRule.rule_id}`, value: result.failedRule.explanation })

  // All rule IDs
  if (result.allRules.length > 0)
    rows.push({ label: 'Rules evaluated', value: result.allRules.map(r => r.rule_id).join(', ') })

  // Raw amounts
  if (result.approved.amountRaw) rows.push({ label: 'Approved token units (6 decimals)', value: result.approved.amountRaw })
  if (result.submitted.amountRaw) rows.push({ label: 'Submitted token units (6 decimals)', value: result.submitted.amountRaw })

  // Implementation addresses from evidence (B2/B3)
  const data = asObject(evidence)
  const executionResult = asObject(data.execution_result)
  for (const [key, label] of [['current_implementation', 'Current implementation'], ['rejected_implementation', 'Rejected implementation']] as const) {
    const value = executionResult[key]
    if (typeof value === 'string' && /^0x[\da-f]{40}$/i.test(value)) rows.push({ label, value })
  }

  return rows
}

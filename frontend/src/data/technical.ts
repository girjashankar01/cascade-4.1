import { asObject } from './adapters.ts'
import type { RunResult } from './types.ts'

export interface TechnicalRow { label: string; value: string }
/** Render a strict allowlist, never arbitrary backend text, stack traces, or JSON. */
export function technicalRows(result: RunResult, evidence: unknown): TechnicalRow[] {
  const rows: TechnicalRow[] = [{ label: 'Data source', value: result.source === 'demo' ? 'Authored local fixture' : 'Local service response' }, { label: 'Scenario', value: result.scenario }, { label: 'Outcome', value: result.outcome }]
  const data = asObject(evidence), execution = asObject(data.execution_result)
  const hash = execution.tx_hash
  if (typeof hash === 'string' && /^(0x)?[\da-f]{64}$/i.test(hash)) rows.push({ label: 'Transaction hash', value: hash })
  const slot = asObject(data.slot_verified)
  for (const [key, label] of [['current_implementation', 'Current implementation'], ['rejected_implementation', 'Rejected implementation']] as const) {
    const value = slot[key]
    if (typeof value === 'string' && /^0x[\da-f]{40}$/i.test(value)) rows.push({ label, value })
  }
  if (result.approved.amountRaw) rows.push({ label: 'Approved token units (6 decimals)', value: result.approved.amountRaw })
  if (result.submitted.amountRaw) rows.push({ label: 'Sent token units (6 decimals)', value: result.submitted.amountRaw })
  return rows
}

import { DataError } from './types.ts'
import type { ActionSummary, Balances, RunResult, Scenario, ScenarioId } from './types.ts'

export const scenarios: readonly Scenario[] = [
  { id: 'A', title: 'Valid payment', story: 'The recipient and amount match the approved plan.', expected: 'allowed', kind: 'payment' },
  { id: 'B1', title: 'Recipient changed', story: 'The payment is redirected and the amount is doubled.', expected: 'blocked', kind: 'payment' },
  { id: 'C', title: 'A clean start', story: 'Restore the shared fund and the approved plan for another demonstration.', expected: 'allowed', kind: 'reset' },
  { id: 'B3', title: 'Hidden upgrade', story: 'A software change adds a hidden way to take money from the shared fund.', expected: 'blocked', kind: 'upgrade' },
]
const initialBalances: Balances = { fund: '1000000000000', recipient: '0', badActor: '0', quality: 'demo' }
export function getStartingBalances(): Balances { return { ...initialBalances } }
export function getScenario(id: ScenarioId): Scenario {
  const scenario = scenarios.find(item => item.id === id)
  if (!scenario) throw new DataError('UNKNOWN_SCENARIO', 'Choose one of the available scenarios.')
  return { ...scenario }
}
export function getDemoPlan(id: ScenarioId): ActionSummary {
  const scenario = getScenario(id)
  if (scenario.kind === 'reset') return { kind: 'reset', description: 'Restore the starting demo data. No payment is approved.', recipient: null, amountRaw: null }
  if (scenario.kind === 'upgrade') return { kind: 'upgrade', description: 'A software update with only the changes described in the approved plan.', recipient: null, amountRaw: null }
  return { kind: 'payment', description: 'Pay the approved recipient 1,000,000 test USDC.', recipient: 'Approved recipient', amountRaw: '1000000000000' }
}

/** An independent fixture session per workspace, never a simulated live response. */
export function createFixtureService() {
  let balances = getStartingBalances()
  let busy = false
  let used = false
  return {
    balances: () => ({ ...balances }),
    async run(id: ScenarioId): Promise<RunResult> {
      if (busy) throw new DataError('BUSY', 'A check is already in progress. Wait for it to finish.')
      const scenario = getScenario(id)
      busy = true
      try {
        await Promise.resolve()
        const before = id === 'C' ? { ...balances } : getStartingBalances()
        const after = id === 'C' ? getStartingBalances() : id === 'A' ? { ...before, fund: '0', recipient: before.fund } : { ...before }
        const approved = getDemoPlan(id)
        const submitted: ActionSummary = id === 'B1'
          ? { kind: 'payment', description: 'Pay the bad actor 2,000,000 test USDC.', recipient: 'The bad actor', amountRaw: '2000000000000' }
          : id === 'B3' ? { kind: 'upgrade', description: 'A software update with an undeclared way to take funds.', recipient: null, amountRaw: null } : { ...approved }
        const result: RunResult = {
          id: crypto.randomUUID(), scenario: id, source: 'demo', outcome: id === 'C' ? 'reset' : scenario.expected,
          reason: id === 'A' ? 'The payment matches the approved plan.' : id === 'B1' ? 'The recipient and amount were changed.' : id === 'B3' ? 'The update includes a change that was not declared.' : 'The starting demo data has been restored. No payment was made.',
          paymentStopped: id === 'C' ? 'not-applicable' : id === 'A' ? 'no' : 'yes', approved, submitted,
          before, after, startedFromCleanState: id !== 'C' && used,
        }
        balances = { ...after }
        used = id !== 'C'
        return structuredClone(result)
      } finally { busy = false }
    },
    reset() {
      if (busy) throw new DataError('BUSY', 'Wait for the current check before resetting.')
      balances = getStartingBalances(); used = false
      return { ...balances }
    },
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

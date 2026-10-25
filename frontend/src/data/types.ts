export type Mode = 'demo' | 'live'
export type ScenarioId = 'A' | 'B1' | 'C' | 'B3'
export type SectionId = 'scenario' | 'run' | 'result' | 'balances' | 'details'
export type Outcome = 'allowed' | 'blocked' | 'reset' | 'needs-review'
export interface Scenario {
  id: ScenarioId
  title: string
  story: string
  expected: 'allowed' | 'blocked'
  kind: 'payment' | 'upgrade' | 'reset'
}
export interface ActionSummary {
  kind: 'payment' | 'upgrade' | 'reset' | 'unavailable'
  description: string
  recipient: string | null
  amountRaw: string | null
}
export interface Balances {
  fund: string
  recipient: string
  badActor: string
  quality: 'demo' | 'reported'
}
export interface RunResult {
  id: string
  scenario: ScenarioId
  source: Mode
  outcome: Outcome
  reason: string
  paymentStopped: 'yes' | 'no' | 'not-applicable' | 'unknown'
  approved: ActionSummary
  submitted: ActionSummary
  before: Balances | null
  after: Balances | null
  startedFromCleanState: boolean
}
export interface Connection {
  service: 'demo' | 'online' | 'offline'
  chain: 'demo' | 'online' | 'offline'
  message: string
}
export class DataError extends Error {
  readonly code: string
  constructor(code: string, message: string) { super(message); this.name = 'DataError'; this.code = code }
}
export const unavailableAction: ActionSummary = { kind: 'unavailable', description: 'The action details are not available.', recipient: null, amountRaw: null }

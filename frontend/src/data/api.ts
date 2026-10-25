import { adaptBalances, adaptConnection, adaptPlan, adaptRun, asObject } from './adapters.ts'
import { createClient } from './client.ts'
import { createFixtureService, getScenario, scenarios } from './fixtures.ts'
import { DataError } from './types.ts'
import type { Balances, Connection, Mode, RunResult, ScenarioId } from './types.ts'

/** One coordinator per backend address, shared by every workspace. */
export function createDataService(baseUrl: string, fetcher?: typeof fetch, timeoutMs?: number) {
  let client: ReturnType<typeof createClient> | undefined
  const request = (path: string, method: 'GET' | 'POST' = 'GET', signal?: AbortSignal) => {
    client ??= createClient({ baseUrl, fetcher, timeoutMs })
    return client(path, method, signal)
  }
  const fixtureSessions = new Map<string, ReturnType<typeof createFixtureService>>()
  const evidence = new Map<string, Record<string, unknown>>()
  const marker = `dao-pending-live:${baseUrl}`
  let liveBusy = false
  function hasPending() { try { return typeof sessionStorage !== 'undefined' && sessionStorage.getItem(marker) !== null } catch { return false } }
  let uncertain = hasPending()
  function setPending(value: boolean) { try { if (typeof sessionStorage !== 'undefined') { if (value) sessionStorage.setItem(marker, 'unconfirmed'); else sessionStorage.removeItem(marker) } } catch { /* In-memory lock remains authoritative for this app session. */ } }
  function fixture(workspace: string) {
    if (!fixtureSessions.has(workspace)) fixtureSessions.set(workspace, createFixtureService())
    return fixtureSessions.get(workspace)!
  }
  const service = {
    catalog: () => scenarios.map(scenario => ({ ...scenario })),
    async connection(mode: Mode, signal?: AbortSignal): Promise<Connection> {
      if (mode === 'demo') return { service: 'demo', chain: 'demo', message: 'Demo data is ready. No live service is needed.' }
      return adaptConnection(await request('/health', 'GET', signal))
    },
    async balances(mode: Mode, workspace: string, signal?: AbortSignal) { return mode === 'demo' ? fixture(workspace).balances() : adaptBalances(await request('/balances', 'GET', signal)) },
    async run(mode: Mode, workspace: string, id: ScenarioId): Promise<RunResult> {
      getScenario(id)
      if (mode === 'demo') return fixture(workspace).run(id)
      if (liveBusy || uncertain) throw new DataError('LIVE_BUSY', 'A live run is still unconfirmed. Check its record before starting another. Demo data remains available.')
      liveBusy = true
      let submitted = false
      try {
        const health = adaptConnection(await request('/health'))
        if (health.chain !== 'online') throw new DataError('CHAIN_OFFLINE', 'The local chain is unavailable. Use demo data or reconnect the chain.')
        const before = adaptBalances(await request('/balances'))
        submitted = true; setPending(true)
        const raw = await request(`/scenarios/${id}/run`, 'POST')
        const result = adaptRun(raw, id)
        // A valid response confirms completion even if subsequent read enrichment fails.
        uncertain = false; setPending(false); submitted = false
        result.before = before
        const proposal = asObject(raw).proposal_id
        if (id !== 'C' && typeof proposal === 'string' && /^[A-Za-z0-9_-]+$/.test(proposal)) {
          try { result.approved = adaptPlan(await request(`/manifest/${encodeURIComponent(proposal)}`)); if (id === 'A') result.submitted = { ...result.approved } } catch { /* Unknown action stays explicitly unavailable. */ }
        }
        try { result.after = adaptBalances(await request('/balances')) } catch { result.after = null }
        // Only evidence fields are retained; errors, secrets and arbitrary response text are excluded.
        const data = asObject(raw)
        evidence.set(result.id, { scenario: id, proposal_id: proposal, verdict: data.verdict, execution_result: data.execution_result, state_deltas: data.state_deltas, balances_verified: data.balances_verified, slot_verified: data.slot_verified })
        return result
      } catch (error) {
        if (submitted) { uncertain = true; setPending(true) }
        throw error
      } finally { liveBusy = false }
    },
    async reset(mode: Mode, workspace: string): Promise<Balances | RunResult> { if (mode === 'demo') return fixture(workspace).reset(); return service.run('live', workspace, 'C') },
    technicalEvidence: (runId: string) => structuredClone(evidence.get(runId) ?? {}),
    liveOperationPending: () => liveBusy || uncertain,
  }
  return service
}

let sharedService: ReturnType<typeof createDataService> | undefined
export function getDataService() {
  sharedService ??= createDataService(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')
  return sharedService
}

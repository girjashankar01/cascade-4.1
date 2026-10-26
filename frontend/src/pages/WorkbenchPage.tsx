import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { getDataService } from '../data/api'
import { getScenario } from '../data/fixtures'
import type { BalanceSnapshot } from '../data/types'
import type { useConnection } from '../hooks/useConnection'
import { Button } from '../components/ui/Button'
import { Icon } from '../components/ui/Icon'
import { VerdictMark } from '../components/ui/StatusMark'
import { LazyLock } from '../components/lock/LazyLock'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import { BalanceComparison, RunResult } from '../features/workbench/RunResult'
import '../features/workbench/workbench.css'

const steps = ['Read', 'Lock', 'Check', 'Enforce']

export function WorkbenchPage() {
  const { active, dispatch, run, reset } = useWorkspaces()
  const service = getDataService()
  const { connection, checking } = useOutletContext<ReturnType<typeof useConnection>>()
  const busy = active.phase === 'running'
  const livePending = active.mode === 'live' && service.liveOperationPending()
  const canRead = active.mode === 'demo' || connection?.chain === 'online'
  const key = `${active.id}:${active.mode}:${connection?.chain}:${active.phase}:${active.notice}`
  const [balanceState, setBalanceState] = useState<{ key: string; value: BalanceSnapshot | null } | null>(null)
  const [copied, setCopied] = useState('')
  const balances = balanceState?.key === key ? balanceState.value : null
  const loadingBalances = canRead && balanceState?.key !== key
  useEffect(() => {
    const abort = new AbortController()
    if (!canRead || busy) return () => abort.abort()
    service.balances(active.mode, active.id, abort.signal).then(value => { if (!abort.signal.aborted) setBalanceState({ key, value }) }).catch(() => { if (!abort.signal.aborted) setBalanceState({ key, value: null }) })
    return () => abort.abort()
  }, [active.id, active.mode, busy, canRead, key, service])
  const selected = active.scenario ? getScenario(active.scenario) : null
  const result = active.result
  const runDisabled = !selected || busy || livePending || checking || !canRead

  async function copyError() {
    try {
      await navigator.clipboard.writeText(`DAO Accountability Engine: ${active.mode} safety check did not finish. Scenario ${active.scenario ?? 'none'}. Submitted live operations may remain unconfirmed. Inspect backend records before retrying.`)
      setCopied('Details copied.')
    } catch { setCopied('Copy is unavailable. Ask the developer to inspect the local service record.') }
  }

  const verdictAnnouncement = result
    ? ({ VERIFIED: 'Verified.', MISMATCH: 'Does not match.', UNSUPPORTED: 'Cannot be checked, needs review.', UNCERTAIN: 'Evidence unclear.' })[result.verdict] + ' ' + result.reason
    : null

  return <>
    <header className="workbench-intro">
      <div>
        <h1>Execution workbench</h1>
        <p>Choose a scenario, run the safety check, and see whether the submitted action matches what governance approved.</p>
      </div>
      <span className="preview-note">{active.mode === 'demo' ? 'Demo data · test tokens' : 'Local test chain · no real money'}</span>
    </header>

    {/* Scenario selection */}
    <section id="scenario" className="workbench-section" aria-labelledby="scenario-title">
      <div className="workbench-section-heading">
        <div>
          <h2 id="scenario-title">Choose a scenario</h2>
          <p>A valid payout, a substituted payout, a benign upgrade, a malicious upgrade, or an environment reset.</p>
        </div>
        <span className="expected-key">Marks show the expected verdict.</span>
      </div>
      <fieldset className="workbench-scenarios">
        <legend className="visually-hidden">Choose a scenario for this workspace</legend>
        {service.catalog().map(scenario => (
          <label key={scenario.id} className={`workbench-scenario ${active.scenario === scenario.id ? 'is-selected' : ''}`}>
            <input type="radio" name={`scenario-${active.id}`} value={scenario.id} checked={active.scenario === scenario.id} disabled={busy}
              onChange={() => dispatch({ type: 'select', id: active.id, scenario: scenario.id })} />
            <div>
              <div className="scenario-row">
                <h3>{scenario.title}</h3>
                <div className="scenario-outcome">
                  <VerdictMark verdict={scenario.expectedVerdict} />
                  {scenario.actionKind === 'reset' && <span>Reset</span>}
                </div>
              </div>
              <p>{scenario.story}</p>
            </div>
          </label>
        ))}
      </fieldset>
      <div className="approved-preview">
        <Icon name="lock" />
        <div>
          <h3>Approved manifest</h3>
          <p>{selected
            ? (active.mode === 'demo'
              ? `Scenario ${selected.id}: ${selected.title} — action sheet will appear in the result.`
              : 'The local service will read the approved manifest. Use demo data for a complete preview.')
            : 'Choose a scenario to see the approved manifest before a check begins.'}</p>
          {active.mode === 'live' && selected && (
            <p className="run-note">Running sends one request to the local service and may change the test chain. If the local examples are not ready, use demo data.</p>
          )}
        </div>
      </div>
    </section>

    {/* Run section */}
    <section id="run" className="workbench-section" aria-labelledby="run-title">
      <div className="workbench-section-heading">
        <div>
          <h2 id="run-title">Follow the safety check</h2>
          <p>{selected ? `${selected.title} is selected for this workspace.` : 'Choose a scenario before starting a check.'}</p>
        </div>
        <Button disabled={runDisabled} onClick={() => { setCopied(''); void run() }}>
          {busy ? 'Checking…' : active.mode === 'demo' ? 'Run safety check' : 'Run on local test chain'}
          <Icon name="arrow" />
        </Button>
      </div>
      <div className="execution-stage">
        <div>
          <p className="run-note">{active.mode === 'demo'
            ? 'Demo sequence. Each run starts with fresh balances.'
            : 'The service runs the check as one operation. Individual live steps are not observable here.'}</p>
          <ol className="check-sequence">
            {steps.map((step, index) => (
              <li key={step}
                className={active.mode === 'demo' && active.step === index && busy ? 'step-current' : active.mode === 'demo' && active.step > index && (busy || result) ? 'step-complete' : ''}
                aria-current={active.mode === 'demo' && active.step === index && busy ? 'step' : undefined}>
                <span>{index + 1}</span>
                <strong>{step}</strong>
                <p>{['Read the proposal and sources.', 'Lock the approved manifest.', 'Compare submitted action.', 'Allow or stop execution.'][index]}</p>
              </li>
            ))}
          </ol>
        </div>
        <div className="execution-lock">
          <LazyLock engaged={Boolean(result) || (busy && active.mode === 'demo' && active.step >= 1)} />
        </div>
      </div>
      <p role="status" aria-live="polite" className="execution-announcement">
        {busy
          ? (active.operation === 'reset' ? 'Resetting the demo environment…' : active.mode === 'demo' ? `Demo sequence: ${steps[active.step] ?? 'Preparing'}.` : 'Waiting for the local service.')
          : (result ? `${verdictAnnouncement}` : active.notice ?? 'Ready when you are.')}
      </p>
      {livePending && !busy && (
        <p className="run-note">A live operation is still pending or unconfirmed. Check its real record before another live run. You can switch to demo data.</p>
      )}
      {active.error && (
        <div className="run-error" role="alert">
          <h3>The check did not finish</h3>
          <p>{active.error}</p>
          <div className="fallback-actions">
            <Button variant="secondary" disabled={busy} onClick={() => dispatch({ type: 'mode', id: active.id, mode: 'demo' })}>Use demo data</Button>
            <Button variant="quiet" onClick={copyError}>Copy details for the developer</Button>
          </div>
          <p role="status">{copied}</p>
        </div>
      )}
    </section>

    {/* Result section */}
    <section id="result" className="workbench-section" aria-labelledby="result-title">
      <h2 id="result-title">Result</h2>
      {active.resultHistorical && result && (
        <p className="run-note">Historical record: another live run changed the shared environment after this check.</p>
      )}
      {result
        ? <RunResult key={result.id} result={result} />
        : (
          <div className="empty-result">
            <Icon name="result" />
            <div>
              <h3>{busy ? 'The safety check is in progress' : 'No result yet'}</h3>
              <p>{busy ? 'A result appears only after the check has completed.' : 'Run a scenario to see whether the submitted action matches the approved manifest.'}</p>
            </div>
          </div>
        )}
    </section>

    {/* Balances section */}
    <section id="balances" className="workbench-section" aria-labelledby="balances-title">
      <div className="workbench-section-heading">
        <div>
          <h2 id="balances-title">Treasury and recipient balances</h2>
          <p>All amounts are test USDC. {result ? 'Recorded before and after this run.' : 'Current balances for this workspace.'}</p>
        </div>
      </div>
      {result ? (
        <>
          <BalanceComparison before={result.before} after={result.after} />
          {(!result.before || !result.after) && (
            <p className="run-note">Some balance readings are unavailable. Missing readings do not establish that money stayed still.</p>
          )}
        </>
      ) : busy ? (
        <p>Waiting for a completed record.</p>
      ) : loadingBalances || checking ? (
        <p role="status">Reading balances…</p>
      ) : balances ? (
        <div className="balance-overview">
          {([{ key: 'treasury' as const, label: 'Treasury' }, { key: 'recipient' as const, label: 'Honest recipient' }, { key: 'attacker' as const, label: 'Attacker' }]).map(role => (
            <div key={role.key}>
              <h3>{role.label}</h3>
              <p>{balances[role.key]?.amountHuman ?? 'Unavailable'}<span> test USDC</span></p>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-copy">Balances are unavailable. Use demo data to explore the starting balances.</p>
      )}
      {active.mode === 'live' && <p className="run-note">The local service reports these balances; reads are not independently verified. Live workspaces share one chain.</p>}

      {/* Reset control — scenario C is the proper reset */}
      <div className="reset-control">
        <div>
          <h3>Reset demo environment</h3>
          <p>{active.mode === 'demo'
            ? 'Run Scenario C to redeploy contracts and seed PROP-002. This resets the demo — no payment is executed.'
            : 'Reset deploys and seeds a fresh local environment. It affects every live workspace.'}</p>
        </div>
        <Button variant="secondary" disabled={busy || livePending || !canRead || checking} onClick={() => { setCopied(''); void reset() }}>
          {active.mode === 'demo' ? 'Reset demo (Scenario C)' : 'Reset local test environment'}
        </Button>
      </div>
    </section>

    {/* Details / links */}
    <section id="details" className="workbench-section details-section" aria-labelledby="details-title">
      <h2 id="details-title">What this demonstration covers</h2>
      <p>Simulated governance. One trusted verifier key. Supports ERC-20 payout and proxy upgrade actions only. An unknown or unsupported action returns UNSUPPORTED.</p>
      <div className="details-actions">
        <TechnicalDrawer key={`${active.id}:${result?.id ?? 'empty'}`} result={result} />
        <Link className="workspace-text-link" to="/app/coverage">What this does and does not cover <Icon name="arrow" /></Link>
      </div>
    </section>
  </>
}

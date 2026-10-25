import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { getDataService } from '../data/api'
import { formatTokens, getDemoPlan, getScenario } from '../data/fixtures'
import type { Balances } from '../data/types'
import type { useConnection } from '../hooks/useConnection'
import { Button } from '../components/ui/Button'
import { Icon } from '../components/ui/Icon'
import { StatusMark } from '../components/ui/StatusMark'

export function WorkbenchPage() {
  const { active, dispatch } = useWorkspaces()
  const service = getDataService()
  const { connection, checking } = useOutletContext<ReturnType<typeof useConnection>>()
  const canRead = active.mode === 'demo' || connection?.chain === 'online'
  const key = `${active.id}:${active.mode}:${connection?.chain}`
  const [balanceState, setBalanceState] = useState<{ key: string; value: Balances | null } | null>(null)
  const balances = balanceState?.key === key ? balanceState.value : null
  const loadingBalances = canRead && balanceState?.key !== key
  useEffect(() => {
    const abort = new AbortController()
    if (!canRead) return () => abort.abort()
    service.balances(active.mode, active.id, abort.signal).then(value => { if (!abort.signal.aborted) setBalanceState({ key, value }) }).catch(() => { if (!abort.signal.aborted) setBalanceState({ key, value: null }) })
    return () => abort.abort()
  }, [active.id, active.mode, canRead, key, service])
  const selected = active.scenario ? getScenario(active.scenario) : null
  const demoPlan = active.scenario && active.mode === 'demo' ? getDemoPlan(active.scenario) : null
  return <>
    <header className="workbench-intro"><div><h1>Execution workbench</h1><p>Keep the approved plan beside the action you want to send.</p></div><span className="preview-note">Preview only. No payment runs here.</span></header>
    <section id="scenario" className="workbench-section" aria-labelledby="scenario-title"><div className="workbench-section-heading"><div><h2 id="scenario-title">Choose a scenario</h2><p>A valid payment, a changed payment, a clean reset, or a hidden upgrade.</p></div><span className="expected-key">Marks show the expected outcome.</span></div>
      <fieldset className="workbench-scenarios"><legend className="visually-hidden">Choose a scenario for this workspace</legend>{service.catalog().map(scenario => <label key={scenario.id} className={`workbench-scenario ${active.scenario === scenario.id ? 'is-selected' : ''}`}><input type="radio" name={`scenario-${active.id}`} value={scenario.id} checked={active.scenario === scenario.id} disabled={active.phase === 'running'} onChange={() => dispatch({ type: 'select', id: active.id, scenario: scenario.id })} /><div><div className="scenario-row"><h3>{scenario.title}</h3><div className="scenario-outcome"><StatusMark outcome={scenario.expected} />{scenario.kind === 'reset' && <span>Reset</span>}</div></div><p>{scenario.story}</p></div></label>)}</fieldset>
      <div className="approved-preview"><Icon name="lock" /><div><h3>The approved plan</h3><p>{demoPlan?.description ?? (selected ? 'The live plan must be read from the local service before its action can be confirmed.' : 'Choose a scenario to see the plan before a check begins.')}</p></div></div>
    </section>
    <section id="run" className="workbench-section" aria-labelledby="run-title"><div className="workbench-section-heading"><div><h2 id="run-title">Follow the safety check</h2><p>{selected ? `${selected.title} is selected for this workspace.` : 'Choose a scenario before starting a check.'}</p></div><Button disabled aria-describedby="preview-run-note">Run safety check<Icon name="arrow" /></Button></div><ol className="check-sequence">{['Read', 'Lock', 'Check', 'Enforce'].map((step, index) => <li key={step}><span>{index + 1}</span><strong>{step}</strong><p>{['Read the payment request.', 'Hold the approved plan.', 'Compare what was sent.', 'Allow it or stop it.'][index]}</p></li>)}</ol><p id="preview-run-note" className="muted-copy">Payment runs are unavailable in this preview.</p></section>
    <section id="result" className="workbench-section" aria-labelledby="result-title"><h2 id="result-title">Result</h2><div className="empty-result"><Icon name="result" /><div><h3>No result yet</h3><p>A completed check will explain what matched, what changed, and whether the lock held.</p></div></div></section>
    <section id="balances" className="workbench-section" aria-labelledby="balances-title"><div className="workbench-section-heading"><div><h2 id="balances-title">The shared fund and its recipients</h2><p>{active.mode === 'demo' ? 'Starting demo balances. All amounts are test tokens.' : 'Balances reported by the local service. Unavailable values are never shown as zero.'}</p></div></div>{loadingBalances || checking ? <p role="status">Reading balances…</p> : balances ? <div className="balance-overview">{([{ key: 'fund', label: 'The shared fund' }, { key: 'recipient', label: 'Approved recipient' }, { key: 'badActor', label: 'The bad actor' }] as const).map(role => <div key={role.key}><h3>{role.label}</h3><p>{formatTokens(balances[role.key])}<span>test USDC</span></p></div>)}</div> : <p className="empty-copy">Balances are unavailable. Use demo data to explore the starting balances.</p>}</section>
    <section id="details" className="workbench-section details-section" aria-labelledby="details-title"><h2 id="details-title">What this demonstration covers</h2><p>Simulated governance. One trusted verifier. Checks cover defined actions and observed state. An unknown or unsupported action needs review.</p><Link className="workspace-text-link" to="/app/coverage">What this does and does not cover <Icon name="arrow" /></Link></section>
  </>
}

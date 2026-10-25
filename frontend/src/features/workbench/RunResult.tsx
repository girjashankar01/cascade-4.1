import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useRef } from 'react'
import { useTheme } from '../../app/theme'
import { LazyLock } from '../../components/lock/LazyLock'
import { StatusMark } from '../../components/ui/StatusMark'
import { formatTokens } from '../../data/fixtures'
import type { ActionSummary, Balances, RunResult as Result } from '../../data/types'

export function ActionDescription({ action }: { action: ActionSummary }) {
  return <><p>{action.description}</p>{action.kind === 'payment' && <dl className="action-facts"><div><dt>Recipient</dt><dd>{action.recipient ?? 'Unavailable'}</dd></div><div><dt>Amount</dt><dd>{action.amountRaw ? `${formatTokens(action.amountRaw)} test USDC` : 'Unavailable'}</dd></div></dl>}</>
}
export function RunResult({ result }: { result: Result }) {
  const changed = result.approved.kind !== result.submitted.kind || result.approved.recipient !== result.submitted.recipient || result.approved.amountRaw !== result.submitted.amountRaw || result.outcome === 'blocked'
  const incomplete = result.approved.kind === 'unavailable' || result.submitted.kind === 'unavailable'
  return <div className="run-result">
    <div className="result-headline"><div>{result.outcome === 'allowed' || result.outcome === 'blocked' ? <StatusMark outcome={result.outcome} /> : <span className="neutral-outcome">{result.outcome === 'reset' ? 'Reset complete' : 'Needs review'}</span>}<h3>{result.reason}</h3><p className="stopped-answer">Stopped before any money moved: <strong>{{ yes: 'Yes', no: 'No', 'not-applicable': 'Not applicable — this was a reset', unknown: 'Not confirmed' }[result.paymentStopped]}</strong></p></div>{result.outcome === 'blocked' && <div className="result-lock"><LazyLock engaged /></div>}</div>
    {result.startedFromCleanState && <p className="run-note">This replay restored the starting demo balances before the check.</p>}
    <div className="action-comparison"><article><h3>The approved plan</h3><ActionDescription action={result.approved} /></article><article className={changed ? 'action-changed' : ''}><h3>What was actually sent</h3>{(changed || incomplete) && <p className="difference-label">{incomplete ? 'Comparison incomplete' : 'Different from the approved plan'}</p>}<ActionDescription action={result.submitted} /></article></div>
    {result.scenario === 'B3' && result.outcome === 'blocked' && <p className="run-note">This example checks a software upgrade. It does not send a payment. The hidden change was rejected.</p>}
    {result.source === 'live' && <p className="run-note">The local chain is shared across workspaces. This is a record of this run; later runs can change its state.</p>}
  </div>
}

function BalanceValue({ raw, from }: { raw: string | null; from?: string | null }) {
  const { reduceMotion } = useTheme()
  const systemReduced = useReducedMotion()
  const number = useRef<HTMLSpanElement>(null)
  const label = raw === null ? 'Unavailable' : formatTokens(raw)
  useEffect(() => {
    if (!number.current || raw === null || !from || raw === from || reduceMotion || systemReduced) { if (number.current) number.current.textContent = label; return }
    const start = BigInt(from), end = BigInt(raw)
    const duration = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--motion-duration-explain'))
    const control = animate(0, 1000, { duration, onUpdate: value => { if (number.current) number.current.textContent = formatTokens((start + (end - start) * BigInt(Math.floor(value)) / 1000n).toString()) }, onComplete: () => { if (number.current) number.current.textContent = label } })
    return () => control.stop()
  }, [raw, from, reduceMotion, systemReduced, label])
  return <span className="balance-number" aria-label={label}><span aria-hidden="true" className="balance-reserve">{label.length > (from ? formatTokens(from).length : 0) ? label : formatTokens(from!)}</span><span aria-hidden="true" ref={number}>{label}</span></span>
}
export function BalanceComparison({ before, after }: { before: Balances | null; after: Balances | null }) {
  return <div className="balance-table" role="table" aria-label="Test USDC balances before and after"><div className="balance-row balance-table-header" role="row"><span role="columnheader">Account</span><span role="columnheader">Before</span><span role="columnheader">After</span></div>{([{ key: 'fund', label: 'The shared fund' }, { key: 'recipient', label: 'Approved recipient' }, { key: 'badActor', label: 'The bad actor' }] as const).map(role => <div className="balance-row" role="row" key={role.key}><span role="rowheader">{role.label}</span><span role="cell"><BalanceValue raw={before?.[role.key] ?? null} /></span><span role="cell"><BalanceValue raw={after?.[role.key] ?? null} from={before?.[role.key]} />{before && after && <small>{BigInt(after[role.key]) === BigInt(before[role.key]) ? 'Unchanged' : BigInt(after[role.key]) > BigInt(before[role.key]) ? 'Increased' : 'Decreased'}</small>}</span></div>)}</div>
}

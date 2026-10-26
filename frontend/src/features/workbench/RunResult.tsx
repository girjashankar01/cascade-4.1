import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useRef } from 'react'
import { useTheme } from '../../app/theme'
import { LazyLock } from '../../components/lock/LazyLock'
import { VerdictMark } from '../../components/ui/StatusMark'
import { formatTokens } from '../../data/fixtures'
import type { ApprovedAction, FieldDiff, RoleBalance, RuleResult, RunResult as Result, SubmittedAction } from '../../data/types'

// ─── Action description ──────────────────────────────────────────────────────
export function ActionDescription({ action }: { action: ApprovedAction | SubmittedAction }) {
  const showPayout = action.kind === 'erc20_payout'
  return <>
    <p>{action.description}</p>
    {showPayout && <dl className="action-facts">
      <div><dt>Recipient</dt><dd>{action.recipient ?? 'Unavailable'}</dd></div>
      <div>
        <dt>Amount</dt>
        <dd>
          {action.amountRaw ? (
            <>
              <span className="amount-human">{action.amountHuman ?? formatTokens(action.amountRaw)}</span>
              {' '}USDC
              <span className="amount-raw"> ({action.amountRaw} raw units, 6 decimals)</span>
            </>
          ) : 'Unavailable'}
        </dd>
      </div>
    </dl>}
    {action.kind === 'proxy_upgrade' && <p className="action-kind-note">Proxy upgrade — no token transfer.</p>}
    {action.kind === 'reset' && <p className="action-kind-note">Environment reset — no payment executed.</p>}
  </>
}

// ─── Field diff table ────────────────────────────────────────────────────────
function DiffTable({ diffs }: { diffs: FieldDiff[] }) {
  if (!diffs.length) return null
  return (
    <div className="diff-table-wrapper">
      <h4 className="diff-table-heading">Field differences</h4>
      <table className="diff-table" aria-label="Field-level differences between approved and submitted action">
        <thead>
          <tr><th scope="col">Field</th><th scope="col">Approved</th><th scope="col">Submitted</th></tr>
        </thead>
        <tbody>
          {diffs.map((d, i) => (
            <tr key={i} className="diff-row">
              <td className="diff-field">{d.field}</td>
              <td className="diff-approved">{d.approved ?? '—'}</td>
              <td className="diff-submitted diff-changed">{d.submitted ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Rule result row ─────────────────────────────────────────────────────────
function RuleRow({ rule }: { rule: RuleResult }) {
  return (
    <div className={`rule-row rule-row--${rule.status.toLowerCase()}`}>
      <span className="rule-id" aria-label={`Rule ${rule.rule_id}`}>{rule.rule_id}</span>
      <span className="rule-name">{rule.name}</span>
      <span className="rule-status">{rule.status}</span>
      <span className="rule-explanation">{rule.explanation}</span>
    </div>
  )
}

// ─── Attestation badge ───────────────────────────────────────────────────────
function AttestationBadge({ result }: { result: Result }) {
  const { attestation } = result
  if (attestation.present) {
    return (
      <div className="attestation attestation--present">
        <strong>Verifier's signed OK</strong>
        <span>Attestation signed by <em>{attestation.verifierLabel}</em>.</span>
        {attestation.deadline && <span>Valid until: {new Date(attestation.deadline * 1000).toUTCString()}</span>}
      </div>
    )
  }
  return (
    <div className="attestation attestation--absent">
      <strong>No attestation</strong>
      <span>The verifier did not sign this result.</span>
    </div>
  )
}

// ─── Main RunResult component ─────────────────────────────────────────────────
export function RunResult({ result }: { result: Result }) {
  const isReset = result.scenario === 'C'
  const showDiff = result.diffs.length > 0
  const showAllRules = result.allRules.length > 0

  return (
    <div className="run-result">
      {/* Headline */}
      <div className="result-headline">
        <div>
          <VerdictMark verdict={result.verdict} />
          <h3>{result.reason}</h3>
          <p className="stopped-answer">
            Stopped before any money moved:{' '}
            <strong>{{ yes: 'Yes', no: 'No', 'not-applicable': 'Not applicable', unknown: 'Not confirmed' }[result.paymentStopped]}</strong>
          </p>
        </div>
        {result.verdict === 'MISMATCH' && <div className="result-lock"><LazyLock engaged /></div>}
      </div>

      {/* Attestation */}
      <AttestationBadge result={result} />

      {/* Failed rule — plain sentence with rule ID label */}
      {result.failedRule && (
        <div className="failed-rule-banner" role="alert">
          <span className="rule-id-label">{result.failedRule.rule_id}</span>
          <span>{result.failedRule.explanation}</span>
        </div>
      )}

      {/* Note about demo data */}
      {result.source === 'demo' && (
        <p className="run-note demo-note">Demo data · test tokens · not a real transaction</p>
      )}
      {result.startedFromCleanState && (
        <p className="run-note">This replay restored the starting demo balances before the check.</p>
      )}

      {/* Action comparison — side by side */}
      {!isReset && (
        <div className="action-comparison">
          <article>
            <h3>Approved action</h3>
            <ActionDescription action={result.approved} />
          </article>
          <article className={result.verdict === 'MISMATCH' ? 'action-changed' : ''}>
            <h3>Submitted action</h3>
            {result.verdict === 'MISMATCH' && <p className="difference-label">Does not match the approved action</p>}
            <ActionDescription action={result.submitted} />
          </article>
        </div>
      )}

      {/* Field-level diffs */}
      {showDiff && <DiffTable diffs={result.diffs} />}

      {/* All rules (collapsible-style section) */}
      {showAllRules && (
        <details className="rules-section">
          <summary>All rules evaluated ({result.allRules.length})</summary>
          <div className="rules-list">
            {result.allRules.map(r => <RuleRow key={r.rule_id} rule={r} />)}
          </div>
        </details>
      )}

      {/* Live note */}
      {result.source === 'live' && (
        <p className="run-note">The local chain is shared across workspaces. This is a record of this run; later runs can change its state.</p>
      )}
    </div>
  )
}

// ─── Balance comparison table ─────────────────────────────────────────────────
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
  return <span className="balance-number" aria-label={label}><span aria-hidden="true" className="balance-reserve">{label.length > (from ? formatTokens(from).length : 0) ? label : (from ? formatTokens(from) : label)}</span><span aria-hidden="true" ref={number}>{label}</span></span>
}

interface BalanceRow { role: RoleBalance['role']; label: string }
const BALANCE_ROWS: BalanceRow[] = [
  { role: 'Treasury',        label: 'Treasury' },
  { role: 'Honest recipient', label: 'Honest recipient' },
  { role: 'Attacker',        label: 'Attacker' },
]

import type { BalanceSnapshot } from '../../data/types'

export function BalanceComparison({ before, after }: { before: BalanceSnapshot | null; after: BalanceSnapshot | null }) {
  const roleKey: Record<string, keyof BalanceSnapshot> = {
    'Treasury': 'treasury', 'Honest recipient': 'recipient', 'Attacker': 'attacker'
  }
  return (
    <div className="balance-table" role="table" aria-label="Test USDC balances before and after">
      <div className="balance-row balance-table-header" role="row">
        <span role="columnheader">Account</span>
        <span role="columnheader">Before</span>
        <span role="columnheader">After</span>
      </div>
      {BALANCE_ROWS.map(row => {
        const key = roleKey[row.role] as keyof BalanceSnapshot
        const b = before ? before[key] as RoleBalance : null
        const a = after  ? after[key]  as RoleBalance : null
        return (
          <div className="balance-row" role="row" key={row.role}>
            <span role="rowheader">{row.label}</span>
            <span role="cell"><BalanceValue raw={b?.amountRaw ?? null} /></span>
            <span role="cell">
              <BalanceValue raw={a?.amountRaw ?? null} from={b?.amountRaw} />
              {b && a && <small>{BigInt(a.amountRaw) === BigInt(b.amountRaw) ? 'Unchanged' : BigInt(a.amountRaw) > BigInt(b.amountRaw) ? 'Increased' : 'Decreased'}</small>}
            </span>
          </div>
        )
      })}
    </div>
  )
}

import { Icon } from './Icon'
import type { Verdict } from '../../data/types'
import { VERDICT_PLAIN } from '../../data/types'

/** Maps verdict → icon name */
const VERDICT_ICON: Record<Verdict, 'check' | 'stop' | 'details' | 'result'> = {
  VERIFIED:    'check',
  MISMATCH:    'stop',
  UNSUPPORTED: 'details',
  UNCERTAIN:   'result',
}

/** Primary verdict badge — always shows plain language, never raw verdict text alone */
export function VerdictMark({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`status-mark status-mark--${verdict.toLowerCase()}`}>
      <Icon name={VERDICT_ICON[verdict]} />
      {VERDICT_PLAIN[verdict]}
    </span>
  )
}

/** Legacy alias — kept for backward-compat during migration */
export function StatusMark({ outcome }: { outcome: 'allowed' | 'blocked' | Verdict }) {
  // Map old outcome strings to verdicts
  const verdict: Verdict =
    outcome === 'allowed' ? 'VERIFIED'
    : outcome === 'blocked' ? 'MISMATCH'
    : (outcome as Verdict)
  return <VerdictMark verdict={verdict} />
}

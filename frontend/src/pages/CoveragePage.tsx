import { Link, useLocation } from 'react-router-dom'
import { Icon } from '../components/ui/Icon'
import '../features/pages/pages.css'

/**
 * CoveragePage — honest limits per PROJECT-TRUTH.md §9.
 * Uses correct vocabulary: Treasury, Proposal, Manifest.
 */

const GUARANTEES = [
  {
    title: 'Prose-to-calldata binding',
    description: 'The product binds the proposal text to a structured manifest, commits it on-chain, verifies the submitted execution against it, and refuses to execute on mismatch.',
    tag: 'Covered',
  },
  {
    title: 'ERC-20 payout integrity',
    description: 'For payout proposals, the recipient address and token amount in the submitted calldata must match the approved manifest exactly. A mismatch is caught before any token leaves the Treasury.',
    tag: 'Covered',
  },
  {
    title: 'Proxy upgrade integrity',
    description: 'For upgrade proposals, all function selectors in the submitted implementation must be declared in the manifest. An undeclared selector (such as a hidden sweep function) blocks the upgrade.',
    tag: 'Covered',
  },
  {
    title: 'Pre-execution enforcement',
    description: 'All checks happen before tokens leave the Treasury. If verification fails, the transaction reverts and nothing moves.',
    tag: 'Covered',
  },
  {
    title: 'Evidence conflict gate',
    description: 'If sources disagree on a field (for example $5.0M in the PDF vs $5.8M in the forum post), manifest confirmation is blocked until the conflict is resolved.',
    tag: 'Covered',
  },
  {
    title: 'Version chain integrity',
    description: 'Each version hash includes the previous version hash, the proposal text hash, and the evidence root. A text revision with the same action produces a new hash — older approvals stop working.',
    tag: 'Covered',
  },
]

const LIMITATIONS = [
  {
    title: 'One action per proposal version',
    description: 'Each proposal version may contain exactly one executable action. Multi-action proposals are not supported.',
    tag: 'Limit',
  },
  {
    title: 'Only ERC-20 payout and proxy upgrade',
    description: 'Unsupported action kinds return UNSUPPORTED. The system does not attempt to verify what it cannot decode.',
    tag: 'Limit',
  },
  {
    title: 'Simulated governance',
    description: 'Governance approval is simulated in this demonstration. A production deployment would connect to a real on-chain Governor.',
    tag: 'Limit',
  },
  {
    title: 'Single trusted verifier key',
    description: 'Attestations are signed by one trusted verifier key. A production system would use a committee or threshold signature.',
    tag: 'Limit',
  },
  {
    title: 'Heuristic code scan',
    description: 'The code scan checks selectors and known patterns. It is heuristic evidence, not a formal proof of bytecode equivalence.',
    tag: 'Limit',
  },
  {
    title: 'Honest proposal collusion',
    description: 'If voters read the proposal text and knowingly approve a malicious action, the system treats that approval as legitimate DAO intent. It can only close the gap between text and bytes, not audit voter intent.',
    tag: 'Out of scope',
  },
  {
    title: 'Off-chain deliverables',
    description: 'The system verifies that on-chain execution matches what was voted on. It does not verify whether contractors delivered real-world work.',
    tag: 'Out of scope',
  },
]

export function CoveragePage() {
  const location = useLocation()

  return (
    <section className="secondary-page" aria-labelledby="coverage-page-title">
      <header className="secondary-page-header">
        <h1 id="coverage-page-title">What this does and does not cover</h1>
        <p>
          Voters approve text. The chain executes bytes. This product closes the gap between the two — and is honest about where that gap ends.
        </p>
      </header>

      <div className="coverage-sections">
        <div className="coverage-column">
          <h2>
            <Icon name="check" className="status-mark--verified" />
            <span>What this covers</span>
          </h2>
          <p className="coverage-column-lead">
            Hard invariants enforced on-chain before any Treasury money moves.
          </p>
          <div className="coverage-cards">
            {GUARANTEES.map((item, index) => (
              <article key={index} className="coverage-item-card">
                <div className="coverage-item-header">
                  <h3>{item.title}</h3>
                  <span className="coverage-tag coverage-tag--guaranteed">{item.tag}</span>
                </div>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="coverage-column">
          <h2>
            <Icon name="stop" className="status-mark--mismatch" />
            <span>Limits and what this does not cover</span>
          </h2>
          <p className="coverage-column-lead">
            Risks outside the execution boundary that require external diligence.
          </p>
          <div className="coverage-cards">
            {LIMITATIONS.map((item, index) => (
              <article key={index} className="coverage-item-card">
                <div className="coverage-item-header">
                  <h3>{item.title}</h3>
                  <span className="coverage-tag coverage-tag--scope">{item.tag}</span>
                </div>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="trust-notice-card">
        <h3>Honest demonstration limits</h3>
        <p>
          This demonstration runs on an isolated local network or with authored fixture data. All values are denominated in test tokens (<code>test USDC</code>).
          No real funds, real money, or mainnet assets are ever held, risked, or transferred.
          Governance is simulated. The verifier is a single trusted key. The code scan is heuristic evidence, not a proof.
        </p>
      </div>

      <div className="page-actions">
        <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
          Return to workbench to test these invariants in action <Icon name="arrow" />
        </Link>
      </div>
    </section>
  )
}

import { Link, useLocation } from 'react-router-dom'
import { Icon } from '../components/ui/Icon'
import { coverageGuarantees, coverageLimitations } from '../data/secondaryData'
import '../features/pages/pages.css'

export function CoveragePage() {
  const location = useLocation()

  return (
    <section className="secondary-page" aria-labelledby="coverage-page-title">
      <header className="secondary-page-header">
        <h1 id="coverage-page-title">What this does and does not cover</h1>
        <p>A transparent definition of the safety guarantees provided by the DAO Accountability Engine and its explicit non-goals.</p>
      </header>

      <div className="coverage-sections">
        <div className="coverage-column">
          <h2>
            <Icon name="check" className="status-mark--allowed" />
            <span>What this protects against</span>
          </h2>
          <p className="coverage-column-lead">
            Hard invariants enforced on-chain before any treasury money moves.
          </p>

          <div className="coverage-cards">
            {coverageGuarantees.map((item, index) => (
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
            <Icon name="stop" className="status-mark--blocked" />
            <span>What this does not cover</span>
          </h2>
          <p className="coverage-column-lead">
            Risks outside our execution boundary that require external diligence.
          </p>

          <div className="coverage-cards">
            {coverageLimitations.map((item, index) => (
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
        <h3>Honest Demonstration Limits</h3>
        <p>
          This demonstration runs on an isolated local network or with authored fixture data. All values are denominated in test tokens (<code>test USDC</code>). No real funds, real money, or mainnet assets are ever held, risked, or transferred.
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

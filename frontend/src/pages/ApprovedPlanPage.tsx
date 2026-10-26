import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import { approvedPlans } from '../data/secondaryData'
import '../features/pages/pages.css'

export function ApprovedPlanPage() {
  const { active } = useWorkspaces()
  const location = useLocation()
  const plan = active.scenario ? approvedPlans[active.scenario] : null

  return (
    <section className="secondary-page" aria-labelledby="approved-plan-title">
      <header className="secondary-page-header">
        <h1 id="approved-plan-title">Approved plan</h1>
        <p>The locked, canonical governance agreement that the execution engine verifies against.</p>
      </header>

      {!plan ? (
        <div className="page-empty-state">
          <h2>No approved plan selected</h2>
          <p>
            An approved plan defines the exact recipient and token limits authorized by DAO governance. Select a scenario in the workbench to inspect its locked governance plan and invariant rules.
          </p>
          <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
            Return to the workbench to select a scenario <Icon name="arrow" />
          </Link>
        </div>
      ) : (
        <>
          <div className="page-banner">
            <div className="banner-scenario">
              <Icon name="lock" />
              <span>{plan.title} ({plan.proposalId})</span>
            </div>
            <span className="source-label">
              {active.mode === 'demo' ? 'Demo data · test tokens' : 'Local test service'}
            </span>
          </div>

          <div className="page-grid">
            <article className="page-card">
              <h2>Governance authorization</h2>
              <p className="card-lead">Parameters ratified by the DAO community vote.</p>
              <dl className="definition-list">
                <div className="definition-row">
                  <dt>Plan identifier</dt>
                  <dd>{plan.proposalId}</dd>
                </div>
                <div className="definition-row">
                  <dt>Lock status</dt>
                  <dd>{plan.lockStatus}</dd>
                </div>
                <div className="definition-row">
                  <dt>Approved recipient</dt>
                  <dd>{plan.approvedRecipient}</dd>
                </div>
                <div className="definition-row">
                  <dt>Approved amount cap</dt>
                  <dd>{plan.approvedAmount ?? 'None (system action)'}</dd>
                </div>
                <div className="definition-row">
                  <dt>Governance consensus</dt>
                  <dd>{plan.governanceQuorum}</dd>
                </div>
              </dl>
            </article>

            <article className="page-card">
              <h2>Enforced invariants</h2>
              <p className="card-lead">Rules guaranteed by the lock before any transaction executes.</p>
              <ul className="invariants-list" aria-label="Governance invariant rules">
                {plan.invariants.map((invariant, index) => (
                  <li key={index} className="invariant-item">
                    <div>
                      <div className="invariant-name">{invariant.name}</div>
                      <div className="invariant-rule">{invariant.rule}</div>
                    </div>
                    <span className="source-label">{invariant.status}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <div className="trust-notice-card">
            <h3>How the lock protects DAO funds</h3>
            <p>
              Before any money moves from the treasury, the engine reads the submitted transaction payload and compares it against this approved plan. If the recipient or amount differs from what was approved, execution is stopped immediately.
            </p>
          </div>

          <div className="page-actions">
            <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
              Go to workbench to verify this plan <Icon name="arrow" />
            </Link>
            <TechnicalDrawer result={active.result} />
          </div>
        </>
      )}
    </section>
  )
}

import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'
import { StatusMark } from '../components/ui/StatusMark'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import { formatTokens } from '../data/fixtures'
import { getAuditSteps } from '../data/secondaryData'
import '../features/pages/pages.css'

export function RecordPage() {
  const { active } = useWorkspaces()
  const location = useLocation()
  const result = active.result
  const auditSteps = result ? getAuditSteps(result.scenario, result.outcome) : []

  return (
    <section className="secondary-page" aria-labelledby="record-page-title">
      <header className="secondary-page-header">
        <h1 id="record-page-title">Record of what happened</h1>
        <p>An immutable audit trail of verification checks and enforcement actions.</p>
      </header>

      {!result ? (
        <div className="page-empty-state">
          <h2>No completed check recorded yet</h2>
          <p>
            This workspace has not executed a safety run. Select a scenario in the workbench and run the safety check to view the full four-step audit record, comparison details, and balance verification.
          </p>
          <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
            Return to the workbench to run a check <Icon name="arrow" />
          </Link>
        </div>
      ) : (
        <>
          <div className="page-banner">
            <div className="banner-scenario">
              {result.outcome === 'reset' ? (
                <span className="neutral-outcome">Environment reset</span>
              ) : result.outcome === 'allowed' || result.outcome === 'blocked' ? (
                <StatusMark outcome={result.outcome} />
              ) : (
                <span className="neutral-outcome">Needs review</span>
              )}
              <span>Scenario {result.scenario}</span>
            </div>
            <span className="source-label">
              {result.source === 'demo' ? 'Demo data · test tokens' : 'Local test service'}
            </span>
          </div>

          {active.resultHistorical && (
            <div className="banner-notice-warning" role="status">
              <Icon name="details" />
              <span>Historical record: A subsequent check has modified the test chain state since this run.</span>
            </div>
          )}

          <div className="page-card" style={{ marginBottom: 'var(--space-6)' }}>
            <h2>Execution summary</h2>
            <p className="card-lead">{result.reason}</p>
            <p className="stopped-answer">
              Stopped before any money moved:{' '}
              <strong>
                {result.paymentStopped === 'yes'
                  ? 'Yes — the transaction was rejected'
                  : result.paymentStopped === 'no'
                  ? 'No — the payment was allowed'
                  : result.paymentStopped === 'not-applicable'
                  ? 'Not applicable — this was a reset'
                  : 'Unknown'}
              </strong>
            </p>
          </div>

          <h2>Four-step audit sequence</h2>
          <p className="card-lead">Every check strictly executes the four-step verification sequence.</p>
          <ol className="audit-sequence" aria-label="Four-step verification sequence">
            {auditSteps.map((step, index) => (
              <li
                key={step.name}
                className={`audit-step-card is-${step.status}`}
              >
                <div className="audit-step-header">
                  <span className="audit-step-num">Step {index + 1}</span>
                  <span className={`audit-step-status is-${step.status}`}>
                    {step.status === 'passed' ? 'Passed' : step.status === 'blocked' ? 'Blocked' : 'Skipped'}
                  </span>
                </div>
                <div className="audit-step-title">{step.name}: {step.title}</div>
                <div className="audit-step-detail">{step.detail}</div>
              </li>
            ))}
          </ol>

          <div className="page-grid">
            <article className="page-card">
              <h2>Action comparison</h2>
              <p className="card-lead">Comparison of approved plan vs what was actually submitted.</p>
              <dl className="definition-list">
                <div className="definition-row">
                  <dt>Approved plan</dt>
                  <dd>{result.approved.description}</dd>
                </div>
                <div className="definition-row">
                  <dt>What was actually sent</dt>
                  <dd>{result.submitted.description}</dd>
                </div>
              </dl>
            </article>

            <article className="page-card">
              <h2>Balances before & after</h2>
              <p className="card-lead">Verified balance snapshot (test USDC).</p>
              {!result.before || !result.after ? (
                <p className="muted-copy">Balance snapshot unavailable.</p>
              ) : (
                <dl className="definition-list">
                  <div className="definition-row">
                    <dt>The shared fund</dt>
                    <dd>{formatTokens(result.before.fund)} → {formatTokens(result.after.fund)}</dd>
                  </div>
                  <div className="definition-row">
                    <dt>Approved recipient</dt>
                    <dd>{formatTokens(result.before.recipient)} → {formatTokens(result.after.recipient)}</dd>
                  </div>
                  <div className="definition-row">
                    <dt>The bad actor</dt>
                    <dd>{formatTokens(result.before.badActor)} → {formatTokens(result.after.badActor)}</dd>
                  </div>
                </dl>
              )}
            </article>
          </div>

          <div className="page-actions">
            <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
              Return to workbench <Icon name="arrow" />
            </Link>
            <TechnicalDrawer result={result} />
          </div>
        </>
      )}
    </section>
  )
}

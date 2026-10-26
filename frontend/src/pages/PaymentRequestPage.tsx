import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import { paymentRequests } from '../data/secondaryData'
import '../features/pages/pages.css'

export function PaymentRequestPage() {
  const { active } = useWorkspaces()
  const location = useLocation()
  const request = active.scenario ? paymentRequests[active.scenario] : null

  return (
    <section className="secondary-page" aria-labelledby="payment-request-title">
      <header className="secondary-page-header">
        <h1 id="payment-request-title">Payment request</h1>
        <p>The proposed disbursement before it is verified and enforced against the approved plan.</p>
      </header>

      {!request ? (
        <div className="page-empty-state">
          <h2>No payment request selected</h2>
          <p>
            Each scenario demonstrates a different payment request or system action. Start by selecting a scenario in the workbench to inspect its incoming request, claims, and supporting source documents.
          </p>
          <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
            Return to the workbench to select a scenario <Icon name="arrow" />
          </Link>
        </div>
      ) : (
        <>
          <div className="page-banner">
            <div className="banner-scenario">
              <Icon name="scenario" />
              <span>Scenario {request.scenarioId}: {request.title}</span>
            </div>
            <span className="source-label">
              {active.mode === 'demo' ? 'Demo data · test tokens' : 'Local test service'}
            </span>
          </div>

          {request.conflictNotice && (
            <div className="banner-notice-warning" role="alert">
              <Icon name="stop" />
              <span>{request.conflictNotice}</span>
            </div>
          )}

          <div className="page-grid">
            <article className="page-card">
              <h2>Request parameters</h2>
              <p className="card-lead">Values declared in the proposal submitted for execution.</p>
              <dl className="definition-list">
                <div className="definition-row">
                  <dt>Proposal identifier</dt>
                  <dd>{request.proposalId}</dd>
                </div>
                <div className="definition-row">
                  <dt>Requester</dt>
                  <dd>{request.requester}</dd>
                </div>
                <div className="definition-row">
                  <dt>Target recipient</dt>
                  <dd>{request.requestedRecipient}</dd>
                </div>
                <div className="definition-row">
                  <dt>Requested amount</dt>
                  <dd>{request.requestedAmount ?? 'None (system action)'}</dd>
                </div>
                <div className="definition-row">
                  <dt>Purpose</dt>
                  <dd>{request.purpose}</dd>
                </div>
              </dl>
            </article>

            <article className="page-card">
              <h2>Supporting evidence</h2>
              <p className="card-lead">Extracted claims from intake source documents.</p>
              <dl className="definition-list">
                <div className="definition-row">
                  <dt>Source file</dt>
                  <dd>{request.sourceDocument.filename} ({request.sourceDocument.pages} page)</dd>
                </div>
              </dl>

              <div className="claims-table-wrapper">
                <table className="claims-table" aria-label="Extracted proposal claims">
                  <thead>
                    <tr>
                      <th scope="col">Field</th>
                      <th scope="col">Value</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {request.claims.map((claim, index) => (
                      <tr key={index}>
                        <td>
                          <strong>{claim.field}</strong>
                          <span className="claim-quote">"{claim.quote}"</span>
                        </td>
                        <td>{claim.value}</td>
                        <td>
                          <span className={`claim-tag claim-tag--${claim.status.toLowerCase()}`}>
                            {claim.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </div>

          <div className="page-actions">
            <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
              Go to workbench to run safety check <Icon name="arrow" />
            </Link>
            <TechnicalDrawer result={active.result} />
          </div>
        </>
      )}
    </section>
  )
}

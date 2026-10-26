import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import '../features/pages/pages.css'

/**
 * AuditPage — shows input hashes, model/provider, rule-set version, cache status.
 * Real data comes from GET /audit/{pid}. Demo data shown until backend connected.
 * Full values in technical drawer only — primary UI shows shortened values.
 */

interface AuditRecord {
  id: string
  proposal_id: string
  input_hash: string
  prompt_hash: string
  provider: string
  model: string
  rule_set_version: string
  cache_status: 'hit' | 'miss'
  timestamp: string
}

// Demo records — labelled as demo data
const DEMO_AUDIT: AuditRecord[] = [
  {
    id: 'aud-001',
    proposal_id: 'PROP-001',
    input_hash: '5fa4c…(Demo data)',
    prompt_hash: '7bc3d…(Demo data)',
    provider: 'openai',
    model: 'gpt-4o (Demo data)',
    rule_set_version: 'v1.0 (Demo data)',
    cache_status: 'hit',
    timestamp: '2026-10-25T00:00:00Z (Demo data)',
  },
]

function shorten(value: string): string {
  if (value.length <= 20) return value
  return `${value.slice(0, 10)}…${value.slice(-6)}`
}

export function AuditPage() {
  const { active } = useWorkspaces()
  const location = useLocation()

  return (
    <section className="secondary-page" aria-labelledby="audit-page-title">
      <header className="secondary-page-header">
        <h1 id="audit-page-title">Audit record</h1>
        <p>Input hashes, model and provider, rule-set version, and cache status for every AI pipeline invocation.</p>
        <span className="source-label demo-badge">Demo data — backend GET /audit/{'{pid}'} not yet connected</span>
      </header>

      <div className="page-grid">
        {DEMO_AUDIT.map(rec => (
          <article key={rec.id} className="page-card audit-card">
            <div className="audit-card-header">
              <h2>Proposal {rec.proposal_id}</h2>
              <span className={`cache-badge cache-badge--${rec.cache_status}`}>
                {rec.cache_status === 'hit' ? 'Cached — generated before this view' : 'Generated now — new LLM call'}
              </span>
            </div>
            <dl className="definition-list">
              <div className="definition-row">
                <dt>Input hash (SHA-256)</dt>
                <dd><code title={rec.input_hash}>{shorten(rec.input_hash)}</code></dd>
              </div>
              <div className="definition-row">
                <dt>Prompt hash (SHA-256)</dt>
                <dd><code title={rec.prompt_hash}>{shorten(rec.prompt_hash)}</code></dd>
              </div>
              <div className="definition-row">
                <dt>Provider</dt>
                <dd>{rec.provider}</dd>
              </div>
              <div className="definition-row">
                <dt>Model</dt>
                <dd>{rec.model}</dd>
              </div>
              <div className="definition-row">
                <dt>Rule-set version</dt>
                <dd>{rec.rule_set_version}</dd>
              </div>
              <div className="definition-row">
                <dt>Timestamp</dt>
                <dd>{rec.timestamp}</dd>
              </div>
            </dl>
            <p className="audit-notice">
              Full hash values are available in the technical drawer. The AI never decides a verdict — hashes, decoding, simulation and rules decide.
            </p>
          </article>
        ))}
      </div>

      <div className="page-actions">
        <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
          Return to workbench <Icon name="arrow" />
        </Link>
        <TechnicalDrawer result={active.result} />
      </div>
    </section>
  )
}

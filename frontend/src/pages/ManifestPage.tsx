import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer'
import '../features/pages/pages.css'

/**
 * ManifestPage — shows the action sheet (manifest), version hash chain,
 * and approval status. Demo data until backend GET /manifest/{pid} and
 * GET /versions/{pid} are connected.
 */

interface ManifestField { label: string; value: string }
interface VersionEntry {
  version: number
  hash: string
  textRevision: boolean
  approvedBy: string | null
  timestamp: string
}

const MANIFEST_FIELDS_V1: ManifestField[] = [
  { label: 'Proposal',          value: 'PROP-001 (Demo data)' },
  { label: 'Action kind',       value: 'ERC-20 payout' },
  { label: 'Recipient',         value: 'Honest recipient (0x9965507D1a55BCC6475675304Ca994970De97744)' },
  { label: 'Amount (raw)',       value: '5000000 (5,000,000 USDC at 6 decimals — Demo data)' },
  { label: 'Token',             value: 'Mock USDC (6 decimals, mimics USDC)' },
  { label: 'Status',            value: 'BLOCKED — unresolved conflict on field: amount (see Proposal page)' },
]

// Clean proposals — from Stage 3 handoff
const MANIFEST_FIELDS_CLEAN: ManifestField[] = [
  { label: 'Proposal',       value: 'clean_proposal_v1 (Demo data)' },
  { label: 'Action kind',    value: 'ERC-20 payout' },
  { label: 'Recipient',      value: 'Honest recipient (0x9965507D1a55BCC6475675304Ca994970De97744)' },
  { label: 'Amount (raw)',   value: '1000000000000 (1,000,000 USDC at 6 decimals)' },
  { label: 'Token',          value: 'Mock USDC (6 decimals)' },
  { label: 'Status',         value: 'CONFIRMED — approved by simulated governance' },
]

const VERSION_CHAIN: VersionEntry[] = [
  {
    version: 1,
    hash: 'v1hash…(Demo data)',
    textRevision: false,
    approvedBy: 'Simulated governance',
    timestamp: 'v1 — base version',
  },
  {
    version: 2,
    hash: 'v2hash…(Demo data)',
    textRevision: true,
    approvedBy: null,
    timestamp: 'v2 — text revision of same action (older approvals stop working)',
  },
]

export function ManifestPage() {
  const { active } = useWorkspaces()
  const location = useLocation()

  return (
    <section className="secondary-page" aria-labelledby="manifest-page-title">
      <header className="secondary-page-header">
        <h1 id="manifest-page-title">Manifest and versions</h1>
        <p>The action sheet — exactly what will be executed — and the version history that binds each approval to an exact text and evidence root.</p>
        <span className="source-label demo-badge">Demo data</span>
      </header>

      {/* PROP-001 manifest — blocked by conflict */}
      <article className="page-card page-card--alert">
        <h2>PROP-001 — action sheet</h2>
        <p className="card-lead">This manifest cannot be confirmed because an evidence conflict is unresolved (amount: $5.0M vs $5.8M).</p>
        <dl className="definition-list">
          {MANIFEST_FIELDS_V1.map(f => (
            <div className="definition-row" key={f.label}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
      </article>

      {/* Clean grant proposal manifest */}
      <article className="page-card">
        <h2>clean_proposal_v1 — action sheet</h2>
        <p className="card-lead">No evidence conflict. Confirmed and approved by simulated governance.</p>
        <dl className="definition-list">
          {MANIFEST_FIELDS_CLEAN.map(f => (
            <div className="definition-row" key={f.label}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
        <div className="chain-verified-badge">
          <Icon name="lock" />
          <span>Chain-verified — version hash committed on-chain and approved</span>
        </div>
      </article>

      {/* Version chain */}
      <article className="page-card">
        <h2>Version history</h2>
        <p className="card-lead">
          Each version hash includes the previous version hash, the proposal text hash, and the evidence root.
          A new text revision with the same action produces a new version hash — older approvals stop working.
        </p>
        <ol className="version-chain-list">
          {VERSION_CHAIN.map(v => (
            <li key={v.version} className={`version-entry ${v.approvedBy ? 'version-entry--approved' : ''}`}>
              <div className="version-header">
                <strong>Version {v.version}</strong>
                {v.approvedBy && <span className="approval-badge">Approved by simulated governance</span>}
                {v.textRevision && <span className="revision-badge">Text revision — action unchanged</span>}
              </div>
              <p className="version-note">{v.timestamp}</p>
              <code className="version-hash">Version hash: {v.hash}</code>
            </li>
          ))}
        </ol>
      </article>

      <div className="page-actions">
        <Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>
          Go to workbench to run a check <Icon name="arrow" />
        </Link>
        <TechnicalDrawer result={active.result} />
      </div>
    </section>
  )
}

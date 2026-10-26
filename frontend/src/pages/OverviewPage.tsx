import type { BalancesInfo, DeploymentsInfo, Manifest } from '../api/types';
import { LifecycleStrip, type LifecycleStage } from '../components/lifecycle/LifecycleStrip';
import { StatusBadge } from '../components/common/StatusBadge';
import { AddressValue, HashValue } from '../components/common/CopyValue';
import { PlayIcon, CpuIcon, RefreshCwIcon } from '../components/common/Icons';

interface OverviewPageProps {
  proposalId: string;
  manifest: Manifest | null;
  deployments: DeploymentsInfo | null;
  balances?: BalancesInfo | null;
  isBackendHealthy: boolean;
  chainInfo?: { connected: boolean; chainId: number | null; blockNumber: number | null };
  onNavigate: (tab: string) => void;
  onOpenScenario: (scenario: 'A' | 'B1' | 'C') => void;
}

export function OverviewPage({
  proposalId,
  manifest,
  deployments,
  balances,
  isBackendHealthy,
  chainInfo,
  onNavigate,
  onOpenScenario,
}: OverviewPageProps) {
  const action = manifest?.manifest?.action;

  const handleStageSelect = (stage: LifecycleStage) => {
    if (stage === 'evidence' || stage === 'claims') onNavigate('proposals');
    else if (stage === 'manifest' || stage === 'approval') onNavigate('manifest');
    else onNavigate('execution');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Section */}
      <div className="card card-raised" style={{ borderLeft: '3px solid var(--accent-mint)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--accent-mint)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              DAO Accountability Engine · CASCADE '26
            </div>
            <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: '8px 0 6px', color: 'var(--text-primary)' }}>
              Prove that execution matches governance intent.
            </h1>
            <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', maxWidth: '720px', lineHeight: 1.6 }}>
              Decouple governance authorization from arbitrary bytecode. Ingest evidence, ground claims, commit canonical manifests, and enforce single-use EVM payouts through guarded execution.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="env-badge">
                <span className={`status-dot ${isBackendHealthy ? 'online' : 'offline'}`} />
                {isBackendHealthy ? 'API Online' : 'API Offline'}
              </span>
              <span className="env-badge">
                <span className={`status-dot ${chainInfo?.connected ? 'online' : 'offline'}`} />
                {chainInfo?.connected
                  ? `${chainInfo.chainId === 11155111 ? 'Ethereum Sepolia' : chainInfo.chainId === 31337 ? 'Anvil' : `EVM (${chainInfo.chainId})`} (${chainInfo.chainId})`
                  : 'Node Disconnected'}
              </span>
            </div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Chain: {chainInfo?.connected ? `Block #${chainInfo.blockNumber ?? '?'}` : 'Offline'} · Treasury: {deployments?.treasury ? `${deployments.treasury.slice(0, 6)}...` : 'Connected'} · Trust Anchor: GuardedExecutor.sol
            </span>
          </div>
        </div>
      </div>

      {/* Lifecycle Strip */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Governance Chain of Custody</span>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Interactive Lifecycle</span>
        </div>
        <LifecycleStrip
          hasSources={true}
          hasClaims={true}
          hasManifest={Boolean(manifest)}
          isApproved={Boolean(manifest?.confirmed_at)}
          isVerified={Boolean(manifest)}
          hasAttestation={Boolean(manifest)}
          isExecuted={false}
          onSelectStage={handleStageSelect}
        />
      </div>

      {/* Main Grid: Active Proposal Summary & Scenario Launcher Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-6)' }}>
        {/* Active Proposal Card */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Active Governance Intent</span>
            <StatusBadge status={manifest?.status || 'UNKNOWN'} size="sm" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Proposal ID</span>
              <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{proposalId}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Manifest Version</span>
              <span className="mono-val">v{manifest?.version || 1}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Approved Payout</span>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
                {action ? `${(Number(action.amountRaw) / 10**6).toLocaleString()} USDC` : '1,000,000 USDC'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Recipient</span>
              <AddressValue address={action?.recipient || ''} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Action Hash</span>
              <HashValue hash={manifest?.action_hash || ''} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Version Hash</span>
              <HashValue hash={manifest?.version_hash || ''} />
            </div>

            {balances && (
              <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.05em', fontWeight: 600 }}>Live On-Chain Balances</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Treasury (Current):</span>
                  <strong style={{ color: 'var(--accent-mint)' }}>{balances.treasury.token_balance.toLocaleString()} USDC</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', marginTop: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Recipient (Current):</span>
                  <strong style={{ color: '#38bdf8' }}>{balances.recipient.token_balance.toLocaleString()} USDC</strong>
                </div>
              </div>
            )}

            <div style={{ marginTop: 'var(--space-3)' }}>
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => onNavigate('execution')}
              >
                <CpuIcon width={14} height={14} />
                Open in Execution Workbench
              </button>
            </div>
          </div>
        </div>

        {/* Automated Scenario Launcher Cards */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Automated Demo Scenarios</span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent-mint)' }}>One-Click Execution</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {/* Scenario A Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>Scenario A: Valid Payout</strong>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenScenario('A')}>
                  <PlayIcon width={10} height={10} /> Run A
                </button>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                Simulates 1M USDC payout, validates R1–R9, issues EIP-712 attestation, and executes on-chain.
              </p>
            </div>

            {/* Scenario B1 Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>Scenario B1: Substituted Blocked</strong>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenScenario('B1')}>
                  <PlayIcon width={10} height={10} /> Run B1
                </button>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                Adversary substitutes recipient/amount. Rule R2 fails, attestation withheld, execution rejected on-chain.
              </p>
            </div>

            {/* Scenario C Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: '#fca5a5' }}>Scenario C: Clean Reset & Seed</strong>
                <button type="button" className="btn btn-danger btn-sm" onClick={() => onOpenScenario('C')}>
                  <RefreshCwIcon width={10} height={10} /> Reset C
                </button>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                Redeploys core contracts on Anvil, seeds PROP-002, and restores clean state for demonstration.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

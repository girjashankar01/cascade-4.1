import type { BalancesInfo, DeploymentsInfo, Manifest } from '../api/types';
import { LifecycleStrip, type LifecycleStage } from '../components/lifecycle/LifecycleStrip';
import { StatusMark } from '../components/ui/StatusMark';
import { Button } from '../components/ui/Button';
import { Icon } from '../components/ui/Icon';
import { AddressValue, HashValue } from '../components/common/CopyValue';
import { AnimatedBalance } from '../features/workbench/BalanceComparison';

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

  const treasuryBalance = balances?.treasury?.token_balance ?? 10000000;
  const recipientBalance = balances?.recipient?.token_balance ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Section */}
      <div className="card card-raised" style={{ borderLeft: '4px solid var(--color-action)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
          <div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-action)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              DAO Accountability Engine · CASCADE 4.1
            </div>
            <h1 style={{ fontSize: 'var(--text-heading)', fontWeight: 500, margin: '8px 0 6px', color: 'var(--color-text)' }}>
              Prove that execution matches governance intent.
            </h1>
            <p style={{ margin: 0, fontSize: 'var(--text-body)', color: 'var(--color-muted)', maxWidth: '720px', lineHeight: 1.6 }}>
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
                  ? `${chainInfo.chainId === 11155111 ? 'Ethereum Sepolia' : chainInfo.chainId === 31337 ? 'Anvil Local' : `EVM (${chainInfo.chainId})`}`
                  : 'Node Disconnected'}
              </span>
            </div>
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
              Chain: {chainInfo?.connected ? `Block #${chainInfo.blockNumber ?? '?'}` : 'Offline'} · Treasury: {deployments?.treasury ? `${deployments.treasury.slice(0, 6)}...` : 'Connected'} · Trust Anchor: GuardedExecutor.sol
            </span>
          </div>
        </div>
      </div>

      {/* Lifecycle Strip */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Governance Chain of Custody</span>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Interactive Lifecycle</span>
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
            <StatusMark status={manifest?.status || 'UNKNOWN'} compact />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Proposal ID</span>
              <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{proposalId}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Manifest Version</span>
              <span className="mono-val">v{manifest?.version || 1}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Approved Payout</span>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                {action ? `${(Number(action.amountRaw) / 10**6).toLocaleString()} USDC` : '1,000,000 USDC'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Recipient</span>
              <AddressValue address={action?.recipient || ''} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Action Hash</span>
              <HashValue hash={manifest?.action_hash || ''} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Version Hash</span>
              <HashValue hash={manifest?.version_hash || ''} />
            </div>

            {balances && (
              <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-3)', backgroundColor: 'var(--color-canvas)', borderRadius: 'var(--radius-sm)', border: 'var(--border-width) solid var(--color-divider)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.05em', fontWeight: 600 }}>Live On-Chain Balances</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                  <span style={{ color: 'var(--color-muted)' }}>Treasury (Current):</span>
                  <AnimatedBalance start={treasuryBalance} end={treasuryBalance} symbol="USDC" />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)', marginTop: '4px' }}>
                  <span style={{ color: 'var(--color-muted)' }}>Recipient (Current):</span>
                  <AnimatedBalance start={recipientBalance} end={recipientBalance} symbol="USDC" />
                </div>
              </div>
            )}

            <div style={{ marginTop: 'var(--space-3)' }}>
              <Button
                variant="primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => onNavigate('execution')}
              >
                <Icon name="run" />
                <span>Open in Execution Workbench</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Automated Scenario Launcher Cards */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Automated Demo Scenarios</span>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-action)' }}>One-Click Execution</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {/* Scenario A Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-canvas)', borderRadius: 'var(--radius-md)', border: 'var(--border-width) solid var(--color-divider)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>Scenario A: Valid Payout</strong>
                <Button variant="primary" className="btn-sm" onClick={() => onOpenScenario('A')}>
                  <Icon name="run" size={14} /> <span>Run A</span>
                </Button>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-muted)', lineHeight: 1.5 }}>
                Simulates 1M USDC payout, validates R1–R9, issues EIP-712 attestation, and executes on-chain.
              </p>
            </div>

            {/* Scenario B1 Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-canvas)', borderRadius: 'var(--radius-md)', border: 'var(--border-width) solid var(--color-divider)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>Scenario B1: Substituted Blocked</strong>
                <Button variant="secondary" className="btn-sm" onClick={() => onOpenScenario('B1')}>
                  <Icon name="stop" size={14} /> <span>Run B1</span>
                </Button>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-muted)', lineHeight: 1.5 }}>
                Adversary substitutes recipient/amount. Rule R2 fails, attestation withheld, execution rejected on-chain.
              </p>
            </div>

            {/* Scenario C Card */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-canvas)', borderRadius: 'var(--radius-md)', border: 'var(--border-width) solid var(--color-divider)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-blocked)' }}>Scenario C: Clean Reset &amp; Seed</strong>
                <Button variant="secondary" className="btn-sm" onClick={() => onOpenScenario('C')}>
                  <Icon name="reset" size={14} /> <span>Reset C</span>
                </Button>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-muted)', lineHeight: 1.5 }}>
                Redeploys core contracts on Anvil, seeds PROP-002, and restores clean state for demonstration.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewPage;

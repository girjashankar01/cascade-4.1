import { PlayIcon, RefreshCwIcon } from '../common/Icons';
import type { NavTab } from './Sidebar';
import type { BalancesInfo } from '../../api/types';
import { ReadOnlyWalletButton } from './ReadOnlyWalletButton';

interface TopBarProps {
  currentTab: NavTab;
  proposalId: string;
  onSelectProposal: (pid: string) => void;
  onRefresh: () => void;
  onOpenScenarioModal: () => void;
  isRefreshing?: boolean;
  balances?: BalancesInfo | null;
}

export function TopBar({
  currentTab,
  proposalId,
  onSelectProposal,
  onRefresh,
  onOpenScenarioModal,
  isRefreshing = false,
  balances,
}: TopBarProps) {
  const titles: Record<NavTab, string> = {
    overview: 'Overview',
    execution: 'Execution Workbench',
    proposals: 'Proposals & Evidence',
    manifest: 'Manifests & Versions',
    audit: 'Audit Explorer',
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="page-title">{titles[currentTab]}</span>

        {/* Proposal Selector */}
        <div className="proposal-selector-wrap" title="Select Active Proposal">
          <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PID:</span>
          <select
            className="proposal-select"
            value={proposalId}
            onChange={(e) => onSelectProposal(e.target.value)}
          >
            <option value="PROP-002">PROP-002 (Clean 1M USDC)</option>
            <option value="PROP-001">PROP-001 ($5.0M Conflict)</option>
            <option value="PROP-B1">PROP-B1 (Substituted Payout)</option>
          </select>
        </div>
      </div>

      <div className="topbar-right">
        {/* Live Token Balances Pill */}
        {balances?.connected && (
          <div className="env-badge" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', padding: '4px 10px' }}>
            <span>Treasury: <strong style={{ color: 'var(--accent-mint)' }}>{balances.treasury.token_balance.toLocaleString()} USDC</strong></span>
            <span style={{ color: 'var(--border-default)' }}>|</span>
            <span>Recipient: <strong style={{ color: '#38bdf8' }}>{balances.recipient.token_balance.toLocaleString()} USDC</strong></span>
          </div>
        )}

        {/* Read-Only Wallet Button */}
        <ReadOnlyWalletButton />

        {/* Scenario Runner Pill */}
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={onOpenScenarioModal}
          title="Open Scenario Runner"
        >
          <PlayIcon width={12} height={12} />
          <span>Run Scenarios (A / B1 / C)</span>
        </button>

        {/* Refresh Button */}
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh Active State"
        >
          <RefreshCwIcon className={isRefreshing ? 'spin' : ''} width={12} height={12} />
        </button>
      </div>
    </header>
  );
}

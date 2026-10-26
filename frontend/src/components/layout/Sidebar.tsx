import { Icon, type IconName } from '../ui/Icon';

export type NavTab = 'overview' | 'execution' | 'proposals' | 'manifest' | 'audit';

interface SidebarProps {
  currentTab: NavTab;
  isBackendHealthy: boolean;
  chainInfo?: { connected: boolean; chainId: number | null; blockNumber: number | null };
  onSelectTab: (tab: NavTab) => void;
}

function getNetworkLabel(chainId?: number | null): string {
  if (!chainId) return 'Node';
  if (chainId === 11155111) return 'Sepolia';
  if (chainId === 84532) return 'Base Sepolia';
  if (chainId === 80002) return 'Polygon Amoy';
  if (chainId === 31337) return 'Anvil Local';
  return `Chain ${chainId}`;
}

export function Sidebar({
  currentTab,
  isBackendHealthy,
  chainInfo,
  onSelectTab,
}: SidebarProps) {
  const navItems: { id: NavTab; label: string; icon: IconName }[] = [
    { id: 'overview', label: 'Overview', icon: 'workspace' },
    { id: 'execution', label: 'Execution Workbench', icon: 'lock' },
    { id: 'proposals', label: 'Proposals & Evidence', icon: 'edit' },
    { id: 'manifest', label: 'Manifests & Versions', icon: 'result' },
    { id: 'audit', label: 'Audit Explorer', icon: 'balances' },
  ];

  return (
    <aside className="sidebar" aria-label="Main Navigation">
      {/* Branding */}
      <div className="sidebar-brand">
        <div className="brand-symbol" aria-hidden="true">
          <Icon name="lock" />
        </div>
        <div className="brand-text-wrap">
          <span className="brand-title">CASCADE</span>
          <span className="brand-desc">DAO Accountability</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectTab(item.id)}
            >
              <Icon name={item.icon} className="nav-icon" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Footer / Status */}
      <div className="sidebar-footer">
        <div className="env-badge">
          <span className={`status-dot ${isBackendHealthy ? 'online' : 'offline'}`} />
          <span>API: {isBackendHealthy ? 'Online (:8000)' : 'Offline'}</span>
        </div>
        <div className="env-badge">
          <span className={`status-dot ${chainInfo?.connected ? 'online' : 'offline'}`} />
          <span>
            Chain: {chainInfo?.connected
              ? `${getNetworkLabel(chainInfo.chainId)} · #${chainInfo.blockNumber ?? '?'}`
              : 'Disconnected'}
          </span>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', marginTop: '4px', fontFamily: 'var(--font-technical)' }}>
          CASCADE 4.1 · Stage 5
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;

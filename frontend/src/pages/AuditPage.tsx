import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type {
  AuditRecord,
  ChainBalancesResponse,
  ChainStatusResponse,
  ChainTxRecord,
  ProofResponse,
  VerificationReport,
} from '../api/types';
import { AddressValue, HashValue } from '../components/common/CopyValue';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  ActivityIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  CpuIcon,
  LayersIcon,
  PlayIcon,
  RefreshCwIcon,
  ShieldIcon,
} from '../components/common/Icons';

interface AuditPageProps {
  proposalId: string;
}

function getExplorerBase(chainId?: number | null): string {
  switch (chainId) {
    case 11155111:
      return 'https://sepolia.etherscan.io';
    case 84532:
      return 'https://sepolia.basescan.org';
    case 80002:
      return 'https://amoy.polygonscan.com';
    default:
      return '';
  }
}

function getNetworkTitle(chainId?: number | null): string {
  switch (chainId) {
    case 11155111:
      return 'Ethereum Sepolia (11155111)';
    case 84532:
      return 'Base Sepolia (84532)';
    case 80002:
      return 'Polygon Amoy (80002)';
    case 31337:
      return 'Local Anvil (31337)';
    default:
      return chainId ? `Chain ID ${chainId}` : 'Connected EVM Network';
  }
}

function buildExplorerTxUrl(txHash: string, chainId?: number | null, baseOverride?: string): string {
  const base = baseOverride || getExplorerBase(chainId);
  if (!base || base.startsWith('http://127.0.0.1')) return '';
  const clean = txHash.startsWith('0x') ? txHash : `0x${txHash}`;
  return `${base}/tx/${clean}`;
}

function buildExplorerAddrUrl(addr: string, chainId?: number | null, baseOverride?: string): string {
  const base = baseOverride || getExplorerBase(chainId);
  if (!base || base.startsWith('http://127.0.0.1')) return '';
  return `${base}/address/${addr}`;
}

export function AuditPage({ proposalId }: AuditPageProps) {
  const [proof, setProof] = useState<ProofResponse | null>(null);
  const [chainStatus, setChainStatus] = useState<ChainStatusResponse | null>(null);
  const [chainBalances, setChainBalances] = useState<ChainBalancesResponse | null>(null);
  const [chainTxs, setChainTxs] = useState<ChainTxRecord[]>([]);
  const [analyses, setAnalyses] = useState<AuditRecord[]>([]);
  const [verifications, setVerifications] = useState<VerificationReport[]>([]);

  const [activeTab, setActiveTab] = useState<'PUBLIC_PROOF' | 'TX_HISTORY' | 'DRY_RUN' | 'LOCAL_EVENTS'>('PUBLIC_PROOF');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [balancesRefreshing, setBalancesRefreshing] = useState(false);

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      api.getProof().catch(() => null),
      api.getChainStatus().catch(() => null),
      api.getChainBalances().catch(() => null),
      api.getChainTxs(undefined, 50).catch(() => []),
      api.getAuditTrail(proposalId).catch(() => []),
      api.getVerifications(proposalId).catch(() => []),
    ]).then(([proofRes, statusRes, balancesRes, txsRes, aList, vList]) => {
      if (isMounted) {
        setProof(proofRes);
        setChainStatus(statusRes);
        setChainBalances(balancesRes);
        setChainTxs(txsRes);
        setAnalyses(aList);
        setVerifications(vList);
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [proposalId]);

  const handleRefreshBalances = async () => {
    setBalancesRefreshing(true);
    try {
      const b = await api.getChainBalances();
      setChainBalances(b);
      const st = await api.getChainStatus();
      setChainStatus(st);
    } catch (e) {
      console.warn('Failed to refresh live balances:', e);
    } finally {
      setBalancesRefreshing(false);
    }
  };

  const isProofPublished = Boolean(proof && proof.published && proof.transactions && proof.transactions.length > 0);
  const effectiveChainId = chainStatus?.chain_id || proof?.chain_id;
  const explorerBase = chainStatus?.explorer_base || getExplorerBase(effectiveChainId);
  const networkName = getNetworkTitle(effectiveChainId);

  // Check chain mismatch warning
  const isChainMismatch = Boolean(
    proof &&
    !proof.published &&
    proof.proof_chain_id &&
    chainStatus?.chain_id &&
    proof.proof_chain_id !== chainStatus.chain_id
  );

  // Contracts map combining status and proof
  const contractAddresses = chainStatus?.contract_addresses || {};
  const proofContracts = proof?.contracts || {};
  const contractsList = [
    { name: 'MockToken (USDC)', key: 'token', address: contractAddresses.token || proofContracts.token?.address },
    { name: 'GovernanceRegistry', key: 'registry', address: contractAddresses.registry || proofContracts.registry?.address },
    { name: 'Treasury', key: 'treasury', address: contractAddresses.treasury || proofContracts.treasury?.address },
    { name: 'GuardedExecutor', key: 'executor', address: contractAddresses.executor || proofContracts.executor?.address },
  ];

  // Local events unified list
  const localEvents = [
    ...analyses.map((a) => ({
      id: a.id,
      type: 'ANALYSIS',
      title: `LLM Extraction (${a.provider} / ${a.model})`,
      timestamp: a.created_at,
      status: a.status,
      badge: a.cache_status === 'cached' ? 'CACHED' : 'GENERATED',
      details: a,
    })),
    ...verifications.map((v) => ({
      id: (v as any).id || `vrf_${v.proposal_id}_${v.version}`,
      type: 'VERIFICATION',
      title: `EVM Verification & Simulation (v${v.version})`,
      timestamp: (v as any).created_at || 'Recent',
      status: v.verdict,
      badge: v.verdict,
      details: v,
    })),
  ].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* SECTION 1: NETWORK BANNER */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
              On-Chain Accountability & Provenance Engine
            </div>
            <h2 style={{ margin: '4px 0 0', fontSize: 'var(--text-xl)', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>{networkName}</span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontFamily: 'var(--font-mono)',
                  backgroundColor: chainStatus?.chain_mode === 'proof' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.08)',
                  color: chainStatus?.chain_mode === 'proof' ? '#38bdf8' : 'var(--text-secondary)',
                  border: `1px solid ${chainStatus?.chain_mode === 'proof' ? 'rgba(56, 189, 248, 0.4)' : 'var(--border-subtle)'}`,
                }}
              >
                {chainStatus?.chain_mode === 'proof' ? 'PROOF MODE · Real EVM Tx' : 'LOCAL MODE · Anvil Sandbox'}
              </span>
            </h2>
          </div>

          {/* Network Badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            {/* RPC Health */}
            <span
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                borderRadius: '6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: chainStatus?.rpc_health === 'healthy' ? 'rgba(124, 224, 190, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                color: chainStatus?.rpc_health === 'healthy' ? 'var(--accent-mint)' : '#f87171',
                border: `1px solid ${chainStatus?.rpc_health === 'healthy' ? 'rgba(124, 224, 190, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: chainStatus?.rpc_health === 'healthy' ? 'var(--accent-mint)' : '#f87171',
                }}
              />
              RPC: {chainStatus?.rpc_health || (chainStatus?.rpc_connected ? 'healthy' : 'disconnected')}
            </span>

            {/* Block Number */}
            <span
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                borderRadius: '6px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              Block #{chainStatus?.latest_block ?? '—'}
            </span>

            {/* Contracts Deployed Status */}
            <span
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                borderRadius: '6px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: chainStatus?.contracts_deployed ? 'rgba(124, 224, 190, 0.12)' : 'rgba(234, 179, 8, 0.12)',
                color: chainStatus?.contracts_deployed ? 'var(--accent-mint)' : '#facc15',
                border: `1px solid ${chainStatus?.contracts_deployed ? 'rgba(124, 224, 190, 0.3)' : 'rgba(234, 179, 8, 0.3)'}`,
              }}
            >
              {chainStatus?.contracts_deployed ? '✓ Contracts Deployed' : '⚠ Contracts Not Deployed'}
            </span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
          {[
            { id: 'PUBLIC_PROOF', label: 'Public Proof Explorer' },
            { id: 'TX_HISTORY', label: `Chain Tx History (${chainTxs.length})` },
            { id: 'DRY_RUN', label: 'Dry-Run Preview' },
            { id: 'LOCAL_EVENTS', label: `Local Log (${localEvents.length})` },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              className={`btn btn-sm ${activeTab === t.id ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab(t.id as any)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* SECTION 9: ALERT / EMPTY STATES */}
      {isChainMismatch && (
        <div
          style={{
            padding: 'var(--space-4)',
            backgroundColor: 'rgba(234, 179, 8, 0.12)',
            border: '1px solid rgba(234, 179, 8, 0.35)',
            borderRadius: 'var(--radius-md)',
            color: '#facc15',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertTriangleIcon width={20} height={20} />
          <div>
            <strong>Proof Chain Mismatch:</strong> {proof?.message}
          </div>
        </div>
      )}

      {!chainStatus?.contracts_deployed && (
        <div
          style={{
            padding: 'var(--space-4)',
            backgroundColor: 'rgba(244, 63, 94, 0.1)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: 'var(--radius-md)',
            color: '#f43f5e',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
          }}
        >
          <AlertTriangleIcon width={20} height={20} style={{ marginTop: '2px' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <strong>Contracts Not Deployed on Target Network ({networkName}):</strong>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              Deploy contracts to Ethereum Sepolia and parse deployment addresses:
            </span>
            <code style={{ fontSize: '11px', background: 'var(--bg-app)', padding: '6px 10px', borderRadius: '4px', color: '#38bdf8' }}>
              cd contracts && forge script script/DeployProof.s.sol --rpc-url proof --account sepolia-deployer --broadcast && cd .. && uv run --project backend python scripts/write_proof_deployments.py
            </code>
          </div>
        </div>
      )}

      {/* TAB 1: PUBLIC PROOF EXPLORER */}
      {activeTab === 'PUBLIC_PROOF' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          {/* SECTION 2: CORE CONTRACTS WITH ETHERSCAN LINKS */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LayersIcon style={{ color: '#38bdf8' }} />
                Core Contracts &amp; Verified Addresses
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Target: {networkName}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
              {contractsList.map((c) => {
                const addr = c.address;
                const explorerUrl = addr ? buildExplorerAddrUrl(addr, effectiveChainId, explorerBase) : '';
                return (
                  <div
                    key={c.key}
                    style={{
                      background: 'var(--bg-surface-raised)',
                      padding: '12px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {c.name}
                      </span>
                      {explorerUrl && (
                        <a
                          href={explorerUrl}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: '11px', color: '#38bdf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '2px' }}
                        >
                          Etherscan &rarr;
                        </a>
                      )}
                    </div>
                    {addr ? (
                      <AddressValue address={addr} />
                    ) : (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Not deployed yet
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* SECTION 3: LIVE BALANCES WITH REFRESH BUTTON */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ActivityIcon style={{ color: 'var(--accent-mint)' }} />
                Live On-Chain Balances
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleRefreshBalances}
                disabled={balancesRefreshing}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <RefreshCwIcon className={balancesRefreshing ? 'spin' : ''} width={13} height={13} />
                {balancesRefreshing ? 'Refreshing...' : 'Refresh Balances'}
              </button>
            </div>

            {/* Balances Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px' }}>
              {/* Treasury */}
              <div
                style={{
                  background: 'rgba(56, 189, 248, 0.05)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  padding: '12px',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ fontSize: '11px', color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase' }}>
                  Treasury Vault
                </div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {chainBalances?.treasury?.token_balance_display || '0.00 USDC'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  Native: {chainBalances?.treasury?.balance_eth?.toFixed(4) || '0.0000'} ETH
                </div>
                {chainBalances?.treasury?.address && (
                  <div style={{ marginTop: '4px' }}>
                    <AddressValue address={chainBalances.treasury.address} />
                  </div>
                )}
              </div>

              {/* Roles: Proposer, Governance, Verifier, Deployer, Attacker */}
              {chainBalances?.roles && Object.entries(chainBalances.roles).map(([role, rinfo]) => {
                const isVerifier = role.toLowerCase() === 'verifier';
                return (
                  <div
                    key={role}
                    style={{
                      background: 'var(--bg-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      padding: '12px',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'capitalize' }}>
                        {role} {isVerifier && <span style={{ color: '#a78bfa' }}>(Signer)</span>}
                      </span>
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      {typeof rinfo?.balance_eth === 'number' ? `${rinfo.balance_eth.toFixed(4)} ETH` : '—'}
                    </div>
                    {rinfo?.address && (
                      <div style={{ marginTop: '2px' }}>
                        <AddressValue address={rinfo.address} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Published Proof Content vs Clean Empty State */}
          {!isProofPublished ? (
            /* Clean Empty State */
            <div className="card" style={{ padding: 'var(--space-8)', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid var(--border-default)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-muted)',
                }}
              >
                <ShieldIcon width={24} height={24} />
              </div>

              <div>
                <h3 style={{ margin: '0 0 6px 0', fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>
                  No Public Proof Published Yet on {networkName}
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', maxWidth: '560px', lineHeight: 1.6 }}>
                  No on-chain verification proof artifact is recorded in <code style={{ color: 'var(--accent-mint)' }}>docs/proof.json</code> for this network.
                  Run the proof script to publish transactions (commit, approve, B1 substitution revert, execute, and replay):
                </p>
              </div>

              <div
                style={{
                  background: 'var(--bg-app)',
                  padding: '12px 18px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  textAlign: 'left',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  maxWidth: '640px',
                  width: '100%',
                }}
              >
                <div style={{ color: 'var(--text-muted)' }}># Dry-run preview (generates docs/dryrun.json, 0 txs broadcast):</div>
                <div style={{ color: '#38bdf8' }}>uv run --project backend python scripts/publish_proof.py --dry-run</div>
                <div style={{ color: 'var(--text-muted)', marginTop: '4px' }}># Broadcast full proof to Sepolia with replay check:</div>
                <div style={{ color: 'var(--accent-mint)' }}>uv run --project backend python scripts/publish_proof.py --with-replay</div>
              </div>
            </div>
          ) : (
            /* SECTION 5, 6, 7: PUBLISHED PROOF SECTIONS */
            <>
              {/* SECTION 7: BEFORE / AFTER PROOF DELTA */}
              {proof?.balances_before && proof?.balances_after && (
                <div className="card">
                  <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircleIcon style={{ color: 'var(--accent-mint)' }} />
                      Guarded Execution Balance Deltas
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Proposal: {proof?.pid}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
                    {/* Treasury Delta */}
                    <div
                      style={{
                        padding: '12px 14px',
                        background: 'var(--bg-surface-raised)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Treasury Balance Delta
                      </div>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '6px' }}>
                        <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                          {(((proof.balances_before.treasury_token_balance ?? 0)) / 1e6).toLocaleString()} USDC
                        </span>
                        <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                        <span style={{ fontSize: '16px', fontWeight: 700, color: '#f43f5e' }}>
                          {(((proof.balances_after.treasury_token_balance ?? 0)) / 1e6).toLocaleString()} USDC
                        </span>
                        <span style={{ fontSize: '12px', color: '#f43f5e', fontWeight: 600 }}>
                          (-1,000,000 USDC)
                        </span>
                      </div>
                    </div>

                    {/* Recipient Delta */}
                    <div
                      style={{
                        padding: '12px 14px',
                        background: 'var(--bg-surface-raised)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Designated Recipient Delta
                      </div>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '6px' }}>
                        <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                          {(((proof.balances_before.recipient_token_balance ?? 0)) / 1e6).toLocaleString()} USDC
                        </span>
                        <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                        <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-mint)' }}>
                          {(((proof.balances_after.recipient_token_balance ?? 0)) / 1e6).toLocaleString()} USDC
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--accent-mint)', fontWeight: 600 }}>
                          (+1,000,000 USDC)
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SECTION 6: COMMITMENTS PANEL WITH COPY BUTTONS */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldIcon style={{ color: '#a78bfa' }} />
                    Cryptographic Commitments &amp; EIP-712 Hashes
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    SHA-256 &amp; Keccak-256 Commitments
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>versionHash</div>
                    <HashValue hash={proof?.versionHash || proof?.commitments?.versionHash || ''} />
                  </div>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>actionHash</div>
                    <HashValue hash={proof?.actionHash || proof?.commitments?.actionHash || ''} />
                  </div>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>evidenceRoot</div>
                    <HashValue hash={proof?.evidenceRoot || proof?.commitments?.evidenceRoot || ''} />
                  </div>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>proposalTextHash</div>
                    <HashValue hash={proof?.proposalTextHash || proof?.commitments?.proposalTextHash || ''} />
                  </div>
                  {proof?.pid_b32 && (
                    <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>pid_b32 (Keccak-256)</div>
                      <HashValue hash={proof.pid_b32} />
                    </div>
                  )}
                </div>
              </div>

              {/* SECTION 5: RUN TIMELINE & TRANSACTIONS */}
              <div className="card">
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <PlayIcon style={{ color: 'var(--accent-mint)' }} />
                    On-Chain Verification Lifecycle Timeline
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {proof?.transactions?.length || 0} Transactions Mined
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {proof?.transactions?.map((tx, idx) => {
                    const isSuccess = tx.status === 1;
                    const txUrl = buildExplorerTxUrl(tx.tx_hash, effectiveChainId, explorerBase);

                    return (
                      <div
                        key={tx.tx_hash || idx}
                        style={{
                          padding: '12px 14px',
                          background: 'var(--bg-surface-raised)',
                          borderRadius: 'var(--radius-sm)',
                          border: `1px solid ${isSuccess ? 'var(--border-subtle)' : 'rgba(244, 63, 94, 0.25)'}`,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                              #{idx + 1}
                            </span>
                            <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                              {tx.label}
                            </strong>
                            <span
                              style={{
                                fontSize: '10px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontFamily: 'var(--font-mono)',
                                backgroundColor: isSuccess ? 'rgba(124, 224, 190, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                                color: isSuccess ? 'var(--accent-mint)' : '#f43f5e',
                                border: `1px solid ${isSuccess ? 'rgba(124, 224, 190, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
                              }}
                            >
                              {isSuccess ? 'SUCCESS (status 1)' : 'BLOCKED (status 0)'}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            {tx.block_number && (
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                Block #{tx.block_number}
                              </span>
                            )}
                            {txUrl && (
                              <a
                                href={txUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="btn btn-ghost btn-sm"
                                style={{ color: '#38bdf8', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px' }}
                              >
                                View on Etherscan &rarr;
                              </a>
                            )}
                          </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)', flexWrap: 'wrap', gap: '8px' }}>
                          <div>
                            <span>Tx: </span>
                            <HashValue hash={tx.tx_hash} />
                          </div>
                          <div>
                            {tx.revert_reason ? (
                              <span style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                                Revert reason: <code>{tx.revert_reason}</code>
                              </span>
                            ) : (
                              <span style={{ color: 'var(--accent-mint)' }}>
                                Expected: {tx.expected}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 2: SECTION 4 — CHAIN TRANSACTION HISTORY TABLE */}
      {activeTab === 'TX_HISTORY' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CpuIcon style={{ color: '#38bdf8' }} />
              SQLite Recorded Chain Transactions (chain_txs)
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {chainTxs.length} Record(s) Mined
            </span>
          </div>

          {chainTxs.length === 0 ? (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              No transactions recorded in the chain_txs database table yet. Run scripts/publish_proof.py to broadcast transactions.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '8px 10px' }}>Step / Role</th>
                    <th style={{ padding: '8px 10px' }}>From &rarr; To</th>
                    <th style={{ padding: '8px 10px' }}>Status</th>
                    <th style={{ padding: '8px 10px' }}>Gas / Fee</th>
                    <th style={{ padding: '8px 10px' }}>Block</th>
                    <th style={{ padding: '8px 10px' }}>Tx Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {chainTxs.map((t, idx) => {
                    const isSuccess = t.status === 'success';
                    const txUrl = buildExplorerTxUrl(t.tx_hash, effectiveChainId, explorerBase);
                    return (
                      <tr
                        key={t.tx_hash || idx}
                        style={{
                          borderBottom: '1px solid var(--border-subtle)',
                          backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.02)',
                        }}
                      >
                        <td style={{ padding: '8px 10px' }}>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.step}</div>
                          <div style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>{t.role}</div>
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                          <div>From: {t.from ? `${t.from.slice(0, 8)}...` : '—'}</div>
                          <div>To: {t.to ? `${t.to.slice(0, 8)}...` : '—'}</div>
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <span
                            style={{
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '10px',
                              fontWeight: 600,
                              fontFamily: 'var(--font-mono)',
                              backgroundColor: isSuccess ? 'rgba(124, 224, 190, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                              color: isSuccess ? 'var(--accent-mint)' : '#f43f5e',
                            }}
                          >
                            {isSuccess ? 'SUCCESS' : 'REVERTED'}
                          </span>
                          {t.revert_reason && (
                            <div style={{ color: '#f43f5e', fontSize: '10px', marginTop: '2px' }}>
                              {t.revert_reason}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                          <div>{t.gas_used ? `${t.gas_used.toLocaleString()} gas` : '—'}</div>
                          <div style={{ color: 'var(--text-muted)' }}>{t.fee_eth ? `${t.fee_eth.toFixed(5)} ETH` : '—'}</div>
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                          #{t.block_number ?? '—'}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <AddressValue address={t.tx_hash} />
                            {txUrl && (
                              <a href={txUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none' }}>
                                &rarr;
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SECTION 8 — DRY RUN PREVIEW PANEL */}
      {activeTab === 'DRY_RUN' && (
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldIcon style={{ color: '#38bdf8' }} />
              Dry-Run Simulation Artifact (docs/dryrun.json)
            </span>
            <span
              style={{
                fontSize: '10px',
                padding: '2px 8px',
                borderRadius: '4px',
                backgroundColor: proof?.dryrun ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                color: proof?.dryrun ? '#38bdf8' : 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {proof?.dryrun ? 'DRY-RUN RECORDED' : 'NO DRY-RUN AVAILABLE'}
            </span>
          </div>

          {!proof?.dryrun ? (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              No dry-run artifact found at <code style={{ color: 'var(--accent-mint)' }}>docs/dryrun.json</code>.
              Run <code style={{ color: '#38bdf8' }}>uv run --project backend python scripts/publish_proof.py --dry-run</code> to generate it.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '10px',
                  padding: '12px',
                  background: 'var(--bg-surface-raised)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Proposal ID</div>
                  <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--accent-mint)' }}>{proof.dryrun.pid}</div>
                </div>
                <div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Chain ID</div>
                  <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{proof.dryrun.chain_id}</div>
                </div>
                <div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Attestation Signer</div>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                    {proof.dryrun.attestation?.recovered_signer ? `${proof.dryrun.attestation.recovered_signer.slice(0, 10)}...` : '—'}
                  </div>
                </div>
              </div>

              {/* Calldata Payloads */}
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Simulated Calldata Payloads
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--accent-mint)', fontWeight: 600 }}>Legitimate Payout Calldata (1M USDC)</div>
                    <code style={{ fontSize: '11px', color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
                      {proof.dryrun.calldata?.legitimate}
                    </code>
                  </div>
                  <div style={{ background: 'var(--bg-app)', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10px', color: '#f43f5e', fontWeight: 600 }}>Substituted Adversarial B1 Calldata (2M USDC to attacker)</div>
                    <code style={{ fontSize: '11px', color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
                      {proof.dryrun.calldata?.substituted_b1}
                    </code>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: LOCAL LOG EVENTS */}
      {activeTab === 'LOCAL_EVENTS' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ActivityIcon style={{ color: 'var(--accent-mint)' }} />
              Local Verification &amp; Execution Log
            </span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              {localEvents.length} Event(s) Recorded
            </span>
          </div>

          {isLoading ? (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              Loading audit records...
            </div>
          ) : localEvents.length === 0 ? (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              No local audit records found for proposal '{proposalId}'. Ingest evidence or run Scenario A to record events.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {localEvents.map((evt) => {
                const isExpanded = expandedId === evt.id;
                return (
                  <div
                    key={evt.id}
                    style={{
                      padding: 'var(--space-3) var(--space-4)',
                      backgroundColor: 'var(--bg-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span className="mono-val" style={{ fontSize: '10px' }}>{evt.type}</span>
                        <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{evt.title}</strong>
                        <StatusBadge status={evt.badge} size="sm" />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {evt.timestamp}
                        </span>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setExpandedId(isExpanded ? null : evt.id)}
                        >
                          {isExpanded ? 'Hide JSON' : 'Inspect Details'}
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <pre
                        style={{
                          margin: 'var(--space-3) 0 0',
                          padding: 'var(--space-3)',
                          backgroundColor: 'var(--bg-app)',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          lineHeight: 1.5,
                          color: 'var(--text-secondary)',
                          overflowX: 'auto',
                        }}
                      >
                        {JSON.stringify(evt.details, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

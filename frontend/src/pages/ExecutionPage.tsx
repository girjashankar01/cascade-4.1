import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { BalancesInfo, DeploymentsInfo, Manifest, VerificationReport } from '../api/types';
import { AddressValue, CopyValue, HashValue } from '../components/common/CopyValue';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { EmptyState } from '../components/common/EmptyState';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  CheckCircleIcon,
  XCircleIcon,
  ShieldIcon,
  RefreshCwIcon,
  CpuIcon,
  LockIcon,
  AlertTriangleIcon,
} from '../components/common/Icons';

interface ExecutionPageProps {
  proposalId: string;
  manifest: Manifest | null;
  deployments: DeploymentsInfo | null;
  balances?: BalancesInfo | null;
  onRefresh: () => void;
}

export function ExecutionPage({
  proposalId,
  manifest,
  deployments,
  balances,
  onRefresh,
}: ExecutionPageProps) {
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [executionReceipt, setExecutionReceipt] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedRule, setExpandedRule] = useState<string | null>(null);
  const [showCustomTester, setShowCustomTester] = useState(false);
  const [customTarget, setCustomTarget] = useState('');
  const [customValue, setCustomValue] = useState(0);
  const [customCalldata, setCustomCalldata] = useState('');

  // Load existing verification history for this proposal
  useEffect(() => {
    let isMounted = true;

    const fetchLatestVerification = async () => {
      if (!proposalId) {
        if (isMounted) {
          setReport(null);
          setExecutionReceipt(null);
          setExpandedRule(null);
        }
        return;
      }
      setIsLoading(true);
      setError(null);
      setReport(null);
      setExecutionReceipt(null);
      setExpandedRule(null);
      setShowCustomTester(false);
      setCustomCalldata('');
      try {
        const history = await api.getVerifications(proposalId);
        if (isMounted) {
          if (history.length > 0) {
            const latest = history[0];
            setReport(latest);
            if (latest.executed && latest.tx_hash) {
              setExecutionReceipt({
                tx_hash: latest.tx_hash,
                block_number: latest.block_number,
                status: 1,
              });
            } else {
              setExecutionReceipt(null);
            }
          } else {
            setReport(null);
            setExecutionReceipt(null);
          }
        }
      } catch (err: any) {
        if (isMounted) setError(err?.message || 'Failed to load verification record');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchLatestVerification();
    return () => { isMounted = false; };
  }, [proposalId]);

  // Run on-demand verification
  const handleRunVerification = async () => {
    if (!manifest || !deployments?.registry || !deployments?.treasury || !deployments?.executor) {
      setError('Cannot verify: Manifest or deployment addresses are missing. Please deploy/seed first.');
      return;
    }

    setIsVerifying(true);
    setError(null);

    const action = manifest.manifest.action;
    let target = '';
    let calldata = '';

    if (action.kind === 'proxy_upgrade') {
      target = action.proxy || '';
      const cleanImpl = (action.newImpl || '').replace(/^0x/i, '').padStart(64, '0');
      const offset = (64).toString(16).padStart(64, '0');
      const length = (0).toString(16).padStart(64, '0');
      calldata = '0x4f1ef286' + cleanImpl + offset + length;
    } else {
      target = action.token || '';
      const cleanAddr = (action.recipient || '').replace(/^0x/i, '').padStart(64, '0');
      const hexAmount = BigInt(action.amountRaw || '0').toString(16).padStart(64, '0');
      calldata = '0xa9059cbb' + cleanAddr + hexAmount;
    }

    try {
      const result = await api.verifyTransaction({
        proposal_id: proposalId,
        target,
        value: 0,
        data: calldata,
        registry_address: deployments.registry,
        treasury_address: deployments.treasury,
        executor_address: deployments.executor,
      });

      setReport(result);
    } catch (err: any) {
      setError(err?.message || 'Verification pipeline failed');
    } finally {
      setIsVerifying(false);
    }
  };

  // Run custom calldata verification
  const handleRunCustomVerification = async () => {
    if (!proposalId || !deployments?.registry || !deployments?.treasury || !deployments?.executor) {
      setError('Cannot verify: Deployment addresses are missing.');
      return;
    }

    setIsVerifying(true);
    setError(null);
    try {
      const target = (customTarget || manifest?.manifest?.action?.token || manifest?.manifest?.action?.proxy || deployments?.token || '') as string;
      const result = await api.verifyTransaction({
        proposal_id: proposalId,
        target,
        value: customValue,
        data: customCalldata,
        registry_address: deployments.registry,
        treasury_address: deployments.treasury,
        executor_address: deployments.executor,
      });
      setReport(result);
    } catch (err: any) {
      setError(err?.message || 'Custom verification failed');
    } finally {
      setIsVerifying(false);
    }
  };

  // Execute transaction via GuardedExecutor
  const handleExecute = async () => {
    if (!report || !deployments?.executor) return;

    setIsExecuting(true);
    setError(null);

    try {
      let calldata = report.decoded_tx?.calldata || (report as any).calldata || '';
      if (!calldata && manifest) {
        const action = manifest.manifest.action;
        if (action.kind === 'proxy_upgrade') {
          const cleanImpl = (action.newImpl || '').replace(/^0x/i, '').padStart(64, '0');
          const offset = (64).toString(16).padStart(64, '0');
          const length = (0).toString(16).padStart(64, '0');
          calldata = '0x4f1ef286' + cleanImpl + offset + length;
        } else {
          const cleanAddr = (action.recipient || '').replace(/^0x/i, '').padStart(64, '0');
          const hexAmount = BigInt(action.amountRaw || '0').toString(16).padStart(64, '0');
          calldata = '0xa9059cbb' + cleanAddr + hexAmount;
        }
      }

      const res = await api.executeTransaction({
        proposal_id: proposalId,
        target: report.decoded_tx.target,
        value: report.decoded_tx.value,
        data: calldata,
        executor_address: deployments.executor,
        registry_address: deployments.registry || undefined,
      });

      setExecutionReceipt(res);
      setShowConfirmModal(false);
      onRefresh();
    } catch (err: any) {
      setError(err?.message || 'On-chain execution reverted');
    } finally {
      setIsExecuting(false);
    }
  };

  const action = manifest?.manifest.action;
  const envelope = manifest?.manifest.envelope;
  const decoded = report?.decoded_tx;
  const sim = report?.simulation;
  const diff = report?.diff || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Workbench Header */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: '4px' }}>
            <CpuIcon style={{ color: 'var(--accent-mint)' }} />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Execution Workbench
            </span>
          </div>
          <h2 style={{ margin: 0, fontSize: 'var(--text-xl)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            {proposalId}
            {manifest && (
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', fontWeight: 400 }}>
                (Version {manifest.version})
              </span>
            )}
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {isLoading && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Syncing...</span>
          )}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Verification Verdict</div>
            <StatusBadge status={executionReceipt ? 'EXECUTED' : report?.verdict || 'AWAITING VERIFICATION'} />
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleRunVerification}
            disabled={isVerifying || !manifest || Boolean(executionReceipt)}
            title={executionReceipt ? `Proposal ${proposalId} has already been executed on-chain (Block #${executionReceipt.block_number}).` : 'Run EVM simulation in Anvil sandbox'}
          >
            <RefreshCwIcon className={isVerifying ? 'spin' : ''} width={14} height={14} />
            {isVerifying ? 'Simulating...' : executionReceipt ? 'Execution Completed' : 'Run EVM Verification'}
          </button>
        </div>
      </div>

      {executionReceipt && (
        <div style={{
          padding: 'var(--space-4)',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6ee7b7', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
            <CheckCircleIcon />
            Proposal {proposalId} Successfully Executed on Chain (Mined in Block #{executionReceipt.block_number})
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            GuardedExecutor single-use replay protection is permanently recorded on-chain (<code>executed[pid] = true</code>).
            Re-verifying an executed proposal would simulate against an already-depleted treasury balance. To execute a fresh demonstration payout cycle, use <strong>Scenario A</strong> or <strong>Scenario C (Reset &amp; Seed)</strong> from the Scenario Runner.
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: 'var(--space-3) var(--space-4)', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangleIcon style={{ color: '#f87171' }} />
          <span style={{ fontSize: 'var(--text-xs)', color: '#fca5a5' }}>{error}</span>
        </div>
      )}

      {/* Governance Architecture Notice */}
      <div style={{ padding: 'var(--space-2) var(--space-4)', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <strong>Governance Model:</strong> Simulated governance approval active (<code>governance.approve(pid, versionHash)</code>). The registry strictly guarantees version integrity. Production path: OpenZeppelin Governor + TimelockController.
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ fontSize: '11px' }}
          onClick={() => setShowCustomTester(!showCustomTester)}
        >
          {showCustomTester ? 'Hide Custom Calldata Tester' : 'Adversarial Custom Calldata Tester'}
        </button>
      </div>

      {/* Expandable Custom Calldata Tester */}
      {showCustomTester && (
        <div className="card" style={{ border: '1px dashed var(--accent-mint)' }}>
          <div className="card-header">
            <span className="card-title" style={{ fontSize: 'var(--text-sm)' }}>
              Adversarial Calldata Simulation Workbench
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              Test arbitrary calldata payloads against live Anvil EVM &amp; deterministic rules
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--space-3)' }}>
            <div>
              <label style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Target Contract Address</label>
              <input
                type="text"
                placeholder="0x..."
                value={customTarget}
                onChange={(e) => setCustomTarget(e.target.value)}
                style={{ width: '100%', padding: '6px', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '10px', color: 'var(--text-muted)' }}>ETH Value (wei)</label>
              <input
                type="number"
                value={customValue}
                onChange={(e) => setCustomValue(parseInt(e.target.value, 10) || 0)}
                style={{ width: '100%', padding: '6px', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}
              />
            </div>
          </div>
          <div style={{ marginTop: 'var(--space-3)' }}>
            <label style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Hex Calldata (e.g. 0xa9059cbb...)</label>
            <input
              type="text"
              placeholder="0x..."
              value={customCalldata}
              onChange={(e) => setCustomCalldata(e.target.value)}
              style={{ width: '100%', padding: '6px', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}
            />
          </div>
          <div style={{ marginTop: 'var(--space-3)', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleRunCustomVerification}
              disabled={isVerifying || !customCalldata.trim()}
            >
              {isVerifying ? 'Simulating...' : 'Simulate & Evaluate Rules'}
            </button>
          </div>
        </div>
      )}

      {!manifest ? (
        <EmptyState
          title="No Confirmed Manifest Found"
          message={`Proposal '${proposalId}' does not have a confirmed manifest. Ingest evidence or run Scenario A to initialize.`}
        />
      ) : (
        <>
          {/* Side-by-Side Action Comparison (Centrepiece) */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Approved Intent vs Submitted Transaction</span>
              {decoded && (
                <StatusBadge status={decoded.matches_manifest ? 'MATCH' : 'MISMATCH'} size="sm" />
              )}
            </div>

            <div className="comparison-grid">
              {/* Left Column: Approved Manifest Action */}
              <div className="comparison-col">
                <div className="comparison-header">
                  <span>Approved Manifest Action</span>
                  <span style={{ color: 'var(--accent-mint)' }}>Governance Record</span>
                </div>

                <div className="field-row">
                  <span className="field-label">Action Kind</span>
                  <span className="field-value mono-val">{action?.kind || 'erc20_payout'}</span>
                </div>
                <div className="field-row">
                  <span className="field-label">Token Contract</span>
                  <span className="field-value"><AddressValue address={action?.token || ''} /></span>
                </div>
                <div className="field-row">
                  <span className="field-label">Approved Recipient</span>
                  <span className="field-value"><AddressValue address={action?.recipient || ''} /></span>
                </div>
                <div className="field-row">
                  <span className="field-label">Approved Amount</span>
                  <span className="field-value">
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {(Number(action?.amountRaw || 0) / 10 ** (action?.decimals || 6)).toLocaleString()} USDC
                    </span>{' '}
                    <span style={{ color: 'var(--text-muted)' }}>({action?.amountRaw})</span>
                  </span>
                </div>
                <div className="field-row">
                  <span className="field-label">Outflow Envelope</span>
                  <span className="field-value mono-val">
                    Max: {envelope?.maxTokenOutflow?.[action?.token?.toLowerCase() || ''] || action?.amountRaw}
                  </span>
                </div>
                <div className="field-row">
                  <span className="field-label">Version Hash</span>
                  <span className="field-value"><HashValue hash={manifest.version_hash} /></span>
                </div>
                <div className="field-row">
                  <span className="field-label">Action Hash</span>
                  <span className="field-value"><HashValue hash={manifest.action_hash} /></span>
                </div>
              </div>

              {/* Right Column: Submitted Transaction Calldata */}
              <div className="comparison-col">
                <div className="comparison-header">
                  <span>Submitted Transaction</span>
                  <span style={{ color: decoded?.is_supported ? 'var(--text-secondary)' : '#f87171' }}>
                    {decoded?.method_name || 'transfer(address,uint256)'}
                  </span>
                </div>

                {decoded ? (
                  <>
                    <div className="field-row">
                      <span className="field-label">Selector</span>
                      <span className="field-value mono-val">{decoded.selector}</span>
                    </div>
                    <div className="field-row">
                      <span className="field-label">Target Contract</span>
                      <span className="field-value"><AddressValue address={decoded.target} /></span>
                    </div>
                    <div className={`field-row ${diff.recipient ? 'field-diff-alert' : ''}`}>
                      <span className="field-label">Submitted Recipient</span>
                      <span className="field-value">
                        <AddressValue address={decoded.recipient || ''} />
                        {diff.recipient && <span style={{ color: '#f87171', marginLeft: '6px', fontSize: '10px' }}>[MISMATCH]</span>}
                      </span>
                    </div>
                    <div className={`field-row ${diff.amountRaw ? 'field-diff-alert' : ''}`}>
                      <span className="field-label">Submitted Amount</span>
                      <span className="field-value">
                        <span style={{ fontWeight: 600 }}>
                          {(Number(decoded.amount_raw || 0) / 10 ** (action?.decimals || 6)).toLocaleString()} USDC
                        </span>{' '}
                        <span style={{ color: 'var(--text-muted)' }}>({decoded.amount_raw})</span>
                        {diff.amountRaw && <span style={{ color: '#f87171', marginLeft: '6px', fontSize: '10px' }}>[MISMATCH]</span>}
                      </span>
                    </div>
                    <div className="field-row">
                      <span className="field-label">ETH Value</span>
                      <span className="field-value mono-val">{decoded.value} wei</span>
                    </div>
                    <div className="field-row">
                      <span className="field-label">Calldata Hash</span>
                      <span className="field-value"><HashValue hash={decoded.calldata_hash} /></span>
                    </div>
                    <div className={`field-row ${diff.actionHash ? 'field-diff-alert' : ''}`}>
                      <span className="field-label">Computed Action Hash</span>
                      <span className="field-value">
                        <HashValue hash={decoded.action_hash} />
                        {diff.actionHash && <span style={{ color: '#f87171', marginLeft: '6px', fontSize: '10px' }}>[MISMATCH]</span>}
                      </span>
                    </div>
                  </>
                ) : (
                  <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                    Run EVM Verification to simulate and compare transaction calldata.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* EVM Simulation State Deltas */}
          <div className="card">
            <div className="card-header">
              <div>
                <span className="card-title">EVM Simulation Observed State Deltas (Anvil Sandbox)</span>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Isolated prediction via Anvil snapshot revert (nonces &amp; watchlist restored). Actual on-chain status is confirmed below.
                </div>
              </div>
              {sim && (
                <span className={`badge ${sim.restoration_verified ? 'badge-verified' : 'badge-mismatch'}`} style={{ fontSize: '10px' }}>
                  Snapshot Revert: {sim.restoration_verified ? 'VERIFIED' : 'FAILED'}
                </span>
              )}
            </div>

            {sim ? (
              <div className="delta-grid">
                {/* Treasury Outflow Card */}
                {(() => {
                  const treasuryLower = deployments?.treasury?.toLowerCase() || '';
                  const tBase = sim.baseline_state?.[treasuryLower]?.token_balance;
                  const tPost = sim.post_state?.[treasuryLower]?.token_balance;
                  const displayBase = tBase != null ? `${(tBase / 10**6).toLocaleString()} USDC` : (sim.treasury_outflow > 0 ? `${(sim.treasury_outflow / 10**6).toLocaleString()} USDC` : '—');
                  const displayPost = tPost != null ? `${(tPost / 10**6).toLocaleString()} USDC` : (sim.treasury_outflow > 0 ? '0 USDC' : '—');
                  return (
                    <div className="delta-card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Treasury Token Balance</div>
                        {balances && (
                          <span style={{ fontSize: '10px', color: 'var(--accent-mint)', fontWeight: 600 }}>
                            Live: {balances.treasury.token_balance.toLocaleString()} USDC
                          </span>
                        )}
                      </div>
                      <div className="delta-flow" style={{ marginTop: '4px' }}>
                        <span className="delta-val-before">
                          {displayBase}
                        </span>
                        <span>→</span>
                        <span className="delta-val-after">
                          {displayPost}
                        </span>
                      </div>
                      <span className="delta-pill outflow">
                        -{(sim.treasury_outflow / 10**6).toLocaleString()} USDC Outflow
                      </span>
                    </div>
                  );
                })()}

                {/* Recipient Inflow Card */}
                {(() => {
                  const recipientLower = action?.recipient?.toLowerCase() || '';
                  const rBase = sim.baseline_state?.[recipientLower]?.token_balance;
                  const rPost = sim.post_state?.[recipientLower]?.token_balance;
                  const displayBase = rBase != null ? `${(rBase / 10**6).toLocaleString()} USDC` : (sim.recipient_inflow > 0 ? '0 USDC' : '—');
                  const displayPost = rPost != null ? `${(rPost / 10**6).toLocaleString()} USDC` : (sim.recipient_inflow > 0 ? `${(sim.recipient_inflow / 10**6).toLocaleString()} USDC` : '—');
                  return (
                    <div className="delta-card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Recipient Token Balance</div>
                        {balances && (
                          <span style={{ fontSize: '10px', color: '#38bdf8', fontWeight: 600 }}>
                            Live: {balances.recipient.token_balance.toLocaleString()} USDC
                          </span>
                        )}
                      </div>
                      <div className="delta-flow" style={{ marginTop: '4px' }}>
                        <span className="delta-val-before">
                          {displayBase}
                        </span>
                        <span>→</span>
                        <span className="delta-val-after">
                          {displayPost}
                        </span>
                      </div>
                      <span className="delta-pill inflow">
                        +{(sim.recipient_inflow / 10**6).toLocaleString()} USDC Inflow
                      </span>
                    </div>
                  );
                })()}

                {/* Invariants & Slot Card */}
                <div className="delta-card">
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Watched State Invariants</div>
                  <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div>Unexpected Gains: <strong style={{ color: Object.keys(sim.unexpected_gains || {}).length === 0 ? '#34d399' : '#f87171' }}>{Object.keys(sim.unexpected_gains || {}).length}</strong></div>
                    <div>Allowances Changed: <strong style={{ color: Object.keys(sim.allowance_changes || {}).length === 0 ? '#34d399' : '#f87171' }}>{Object.keys(sim.allowance_changes || {}).length}</strong></div>
                    <div>
                      Implementation Slot:{' '}
                      <span className="mono-val" style={{ fontSize: '10px', color: Object.keys(sim.slot_changes || {}).length === 0 ? 'var(--text-secondary)' : 'var(--accent-mint)' }}>
                        {Object.keys(sim.slot_changes || {}).length === 0 ? '0x3608... Unchanged' : `0x3608... Updated (${Object.keys(sim.slot_changes || {}).length} change)`}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                Simulation deltas will appear after running EVM verification.
              </div>
            )}
          </div>

          {/* Deterministic Rule Inspector */}
          <div className="card">
            <div className="card-header">
              <div>
                <span className="card-title">Deterministic Rule Evaluation</span>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Evaluates 8 deterministic rules (R1–R7, R9). Note: Rule R8 is unassigned in the CASCADE specification; R7 evaluates selector scope and R9 evaluates ownership/role immutability.
                </div>
              </div>
              {report && <StatusBadge status={report.verdict} size="sm" />}
            </div>

            {report?.rules ? (
              <div className="rule-list">
                {report.rules.map((r) => {
                  const isFail = r.status === 'FAIL';
                  const isExpanded = expandedRule === r.rule_id;

                  return (
                    <div key={r.rule_id} className={`rule-row ${isFail ? 'fail' : ''}`}>
                      <div className="rule-header">
                        <div className="rule-id-name">
                          <span className="rule-id">{r.rule_id}</span>
                          <span className="rule-name">{r.name}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <StatusBadge status={r.status} size="sm" />
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => setExpandedRule(isExpanded ? null : r.rule_id)}
                          >
                            {isExpanded ? 'Hide' : 'Details'}
                          </button>
                        </div>
                      </div>
                      <div className="rule-expl">{r.explanation}</div>

                      {/* Expandable Evidence Details */}
                      {isExpanded && (
                        <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                          <div style={{ color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>Diagnostic Evidence:</div>
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>
                            {JSON.stringify(r.evidence, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                Rule checklist evaluates deterministically during verification.
              </div>
            )}
          </div>

          {/* Cryptographic Attestation & Guarded Execution */}
          <div className="card card-raised">
            <div className="card-header">
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LockIcon style={{ color: 'var(--accent-mint)' }} />
                EIP-712 Attestation & Guarded Execution
              </span>
              {executionReceipt ? (
                <StatusBadge status="EXECUTED" />
              ) : report?.attestation_sig ? (
                <StatusBadge status="ATTESTED" />
              ) : report?.verdict === 'MISMATCH' ? (
                <StatusBadge status="BLOCKED" />
              ) : (
                <span className="badge badge-neutral">Execution Gated</span>
              )}
            </div>

            {report?.attestation_sig ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-3)' }}>
                  <div>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Verifier Address:</span>
                    <div><AddressValue address={report.verifier_address || deployments?.verifier || ''} /></div>
                  </div>
                  <div>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Attestation Deadline:</span>
                    <div className="mono-val">{report.deadline} (Chain Block Time)</div>
                  </div>
                  <div>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>EIP-712 Domain:</span>
                    <div className="mono-val">GuardedExecutor (v1)</div>
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Cryptographic Signature (65-byte):</span>
                  <div><CopyValue value={report.attestation_sig} truncate={false} /></div>
                </div>

                {executionReceipt ? (
                  <div style={{ padding: 'var(--space-4)', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6ee7b7', fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: '8px' }}>
                      <CheckCircleIcon />
                      Guarded Execution Confirmed On-Chain
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                      <div>Transaction Hash: <CopyValue value={executionReceipt.tx_hash} /></div>
                      <div>Block Number: <strong>{executionReceipt.block_number}</strong></div>
                      <div>GuardedExecutor: Single-use replay protection recorded (executed[pid] = true)</div>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-2)' }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => setShowConfirmModal(true)}
                      disabled={isExecuting}
                    >
                      <ShieldIcon width={14} height={14} />
                      {isExecuting ? 'Broadcasting...' : 'Execute Transaction on Chain'}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>
                {report?.verdict === 'MISMATCH' ? (
                  <span style={{ color: '#fca5a5' }}>
                    <XCircleIcon width={14} height={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '6px' }} />
                    Execution strictly prohibited: Attestation withheld due to {(() => {
                      const failed = report?.rules?.find(r => r.status === 'FAIL');
                      return failed ? `Rule ${failed.rule_id} (${failed.name}) failure.` : 'verification mismatch.';
                    })()}
                  </span>
                ) : (
                  'EIP-712 attestation signature is only issued when all 8 verification rules pass.'
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Confirmation Modal */}
      <ConfirmModal
        isOpen={showConfirmModal}
        title="Confirm On-Chain Guarded Execution"
        description={`You are about to execute an authorized transaction transferring ${Number(action?.amountRaw || 0) / 10**6} USDC to recipient ${action?.recipient} through GuardedExecutor on the local EVM chain. The contract will verify the approved version hash, action hash, and verifier signature before invoking Treasury.exec.`}
        confirmLabel="Execute via GuardedExecutor"
        isLoading={isExecuting}
        onConfirm={handleExecute}
        onClose={() => setShowConfirmModal(false)}
      />
    </div>
  );
}

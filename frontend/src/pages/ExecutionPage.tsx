import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { BalancesInfo, DeploymentsInfo, Manifest, VerificationReport } from '../api/types';
import { AddressValue, CopyValue } from '../components/common/CopyValue';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { EmptyState } from '../components/common/EmptyState';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  CheckCircleIcon,
  XCircleIcon,
  RefreshCwIcon,
  CpuIcon,
  AlertTriangleIcon,
} from '../components/common/Icons';
import { Button } from '../components/ui/Button';
import { Icon } from '../components/ui/Icon';
import { StatusMark } from '../components/ui/StatusMark';
import { LazyLock } from '../components/lock/LazyLock';
import { TechnicalDrawer } from '../features/workbench/TechnicalDrawer';
import { BalanceComparison } from '../features/workbench/BalanceComparison';
import { ActionComparison } from '../features/workbench/ActionComparison';

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
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

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
  const sim = report?.simulation;
  const isEngaged = Boolean(executionReceipt || report?.attestation_sig);

  // Compute token numbers for animated comparison
  const treasuryBase = balances?.treasury?.token_balance ?? 10000000;
  const recipientBase = balances?.recipient?.token_balance ?? 0;
  const outflow = sim?.treasury_outflow ? sim.treasury_outflow / 10**6 : (action?.amountRaw ? Number(action.amountRaw) / 10**6 : 0);
  const treasuryPredicted = executionReceipt ? treasuryBase : Math.max(0, treasuryBase - (report?.verdict === 'VERIFIED' ? outflow : 0));
  const recipientPredicted = executionReceipt ? recipientBase : recipientBase + (report?.verdict === 'VERIFIED' ? outflow : 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Workbench Header */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: '4px' }}>
            <CpuIcon style={{ color: 'var(--color-action)' }} />
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
              Execution Workbench · Safety Verification
            </span>
          </div>
          <h2 style={{ margin: 0, fontSize: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            {proposalId}
            {manifest && (
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', fontWeight: 400 }}>
                (Version {manifest.version})
              </span>
            )}
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          {isLoading && (
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Syncing...</span>
          )}

          <div style={{ textAlign: 'right' }}>
            <StatusMark verdict={executionReceipt ? 'EXECUTED' : report?.verdict || 'UNCERTAIN'} />
          </div>

          <Button
            variant="secondary"
            onClick={handleRunVerification}
            disabled={isVerifying || !manifest || Boolean(executionReceipt)}
            title={executionReceipt ? `Proposal ${proposalId} has already been executed on-chain (Block #${executionReceipt.block_number}).` : 'Run EVM simulation in Anvil sandbox'}
          >
            <RefreshCwIcon className={isVerifying ? 'spin' : ''} width={16} height={16} />
            <span>{isVerifying ? 'Simulating EVM...' : executionReceipt ? 'Execution Completed' : 'Run EVM Verification'}</span>
          </Button>

          {report && (
            <Button
              variant="quiet"
              onClick={() => setIsDrawerOpen(true)}
              title="Open Technical Inspection Drawer"
            >
              <Icon name="details" />
              <span>Diagnostic Drawer</span>
            </Button>
          )}
        </div>
      </div>

      {/* Hero Visualizer with Interactive Mechanical Lock Artwork */}
      <div className="card card-raised" style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 320px) 1fr', gap: 'var(--space-6)', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-3)' }}>
          <LazyLock engaged={isEngaged} />
          <div style={{ marginTop: 'var(--space-3)', textAlign: 'center' }}>
            <span style={{
              fontSize: '0.8125rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: isEngaged ? 'var(--color-allowed)' : 'var(--color-attention)'
            }}>
              {isEngaged ? 'Lock Engaged · Vault Gated' : 'Lock Disengaged · Pre-Verification'}
            </span>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', marginTop: '2px' }}>
              {isEngaged
                ? 'Single-use EIP-712 cryptographic seal closed'
                : 'Awaiting deterministic rule verification & seal'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-action)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
            Guarded Execution Safety Anchor
          </span>
          <h3 style={{ margin: 0, fontSize: 'var(--text-title)' }}>
            EVM Bytecode Pre-Execution Firewall
          </h3>
          <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--color-muted)', lineHeight: 1.6 }}>
            The CASCADE engine isolates transaction execution in an ephemeral EVM sandbox before any live funds can move.
            If bytecode mismatches the DAO's approved human intent, the shackle remains open and cryptographic attestation is strictly withheld.
          </p>

          {/* Quick Check Sequence Progression */}
          <ol className="check-sequence" style={{ marginTop: 'var(--space-2)' }}>
            <li className={`check-step ${manifest ? 'complete' : 'current'}`}>
              <Icon name={manifest ? 'check' : 'edit'} />
              <span>1. Manifest Committed</span>
            </li>
            <li className={`check-step ${report?.verdict === 'VERIFIED' ? 'complete' : report?.verdict === 'MISMATCH' ? 'current' : ''}`}>
              <Icon name={report?.verdict === 'VERIFIED' ? 'check' : report?.verdict === 'MISMATCH' ? 'stop' : 'run'} />
              <span>2. EVM Simulated</span>
            </li>
            <li className={`check-step ${report?.attestation_sig ? 'complete' : ''}`}>
              <Icon name={report?.attestation_sig ? 'lock' : 'unlock'} />
              <span>3. Attested</span>
            </li>
            <li className={`check-step ${executionReceipt ? 'complete' : ''}`}>
              <Icon name={executionReceipt ? 'check' : 'arrow'} />
              <span>4. Executed</span>
            </li>
          </ol>
        </div>
      </div>

      {executionReceipt && (
        <div style={{
          padding: 'var(--space-4)',
          backgroundColor: 'var(--color-allowed-surface)',
          border: '1px solid var(--color-allowed)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-allowed)', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
            <CheckCircleIcon />
            Proposal {proposalId} Successfully Executed on Chain (Mined in Block #{executionReceipt.block_number})
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', lineHeight: 1.5 }}>
            GuardedExecutor single-use replay protection is permanently recorded on-chain (<code>executed[pid] = true</code>).
            Re-verifying an executed proposal simulates against an already-depleted treasury balance. To run a fresh demonstration payout cycle, use <strong>Scenario A</strong> or <strong>Scenario C (Reset &amp; Seed)</strong> from the Scenario Runner.
          </div>
        </div>
      )}

      {error && (
        <div style={{
          padding: 'var(--space-3) var(--space-4)',
          backgroundColor: 'var(--color-blocked-surface)',
          border: '1px solid var(--color-blocked)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangleIcon style={{ color: 'var(--color-blocked)' }} />
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-blocked)' }}>{error}</span>
        </div>
      )}

      {/* Governance Architecture Notice */}
      <div style={{
        padding: 'var(--space-3) var(--space-4)',
        backgroundColor: 'var(--color-surface)',
        border: 'var(--border-width) solid var(--color-divider)',
        borderRadius: 'var(--radius-md)',
        fontSize: '0.875rem',
        color: 'var(--color-muted)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 'var(--space-3)'
      }}>
        <span>
          <strong>Governance Model:</strong> Simulated governance approval active (<code>governance.approve(pid, versionHash)</code>). The registry guarantees version integrity. Production path: OpenZeppelin Governor + TimelockController.
        </span>
        <Button
          variant="quiet"
          className="btn-sm"
          onClick={() => setShowCustomTester(!showCustomTester)}
        >
          {showCustomTester ? 'Hide Adversarial Tester' : 'Adversarial Custom Calldata Tester'}
        </Button>
      </div>

      {/* Expandable Custom Calldata Tester */}
      {showCustomTester && (
        <div className="card" style={{ border: '1px dashed var(--color-action)' }}>
          <div className="card-header">
            <span className="card-title">Adversarial Calldata Simulation Workbench</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
              Test arbitrary calldata payloads against live Anvil EVM &amp; deterministic rules
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--space-3)' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--color-muted)', display: 'block', marginBottom: '4px' }}>Target Contract Address</label>
              <input
                type="text"
                placeholder="0x..."
                value={customTarget}
                onChange={(e) => setCustomTarget(e.target.value)}
                style={{ width: '100%', fontFamily: 'var(--font-technical)' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--color-muted)', display: 'block', marginBottom: '4px' }}>ETH Value (wei)</label>
              <input
                type="number"
                value={customValue}
                onChange={(e) => setCustomValue(parseInt(e.target.value, 10) || 0)}
                style={{ width: '100%', fontFamily: 'var(--font-technical)' }}
              />
            </div>
          </div>
          <div style={{ marginTop: 'var(--space-3)' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--color-muted)', display: 'block', marginBottom: '4px' }}>Hex Calldata (e.g. 0xa9059cbb...)</label>
            <input
              type="text"
              placeholder="0x..."
              value={customCalldata}
              onChange={(e) => setCustomCalldata(e.target.value)}
              style={{ width: '100%', fontFamily: 'var(--font-technical)' }}
            />
          </div>
          <div style={{ marginTop: 'var(--space-3)', display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="primary"
              className="btn-sm"
              onClick={handleRunCustomVerification}
              disabled={isVerifying || !customCalldata.trim()}
            >
              {isVerifying ? 'Simulating...' : 'Simulate & Evaluate Rules'}
            </Button>
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
          {/* Side-by-Side Action Comparison (Centrepiece from design-extract) */}
          <ActionComparison manifest={manifest} report={report} />

          {/* Balance Comparison with Smooth Motion Counter */}
          <div className="card">
            <div className="card-header">
              <div>
                <span className="card-title">Token Balance Delta Verification</span>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', marginTop: '2px' }}>
                  Animated state transition matching sandbox execution predictions
                </div>
              </div>
              <span className="badge" style={{ backgroundColor: 'var(--color-canvas)', color: 'var(--color-text)', border: 'var(--border-width) solid var(--color-divider)' }}>
                Asset: USDC (6 Decimals)
              </span>
            </div>

            <BalanceComparison
              treasuryBefore={treasuryBase}
              treasuryAfter={treasuryPredicted}
              recipientBefore={recipientBase}
              recipientAfter={recipientPredicted}
              tokenSymbol="USDC"
            />
          </div>

          {/* EVM Simulation State Deltas */}
          <div className="card">
            <div className="card-header">
              <div>
                <span className="card-title">EVM Simulation Observed State Deltas (Anvil Sandbox)</span>
                <div style={{ fontSize: '0.875rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                  Isolated prediction via Anvil snapshot revert (nonces &amp; watchlist restored).
                </div>
              </div>
              {sim && (
                <StatusMark
                  status={sim.restoration_verified ? 'VERIFIED' : 'MISMATCH'}
                  compact
                />
              )}
            </div>

            {sim ? (
              <div className="delta-grid">
                {/* Treasury Outflow Card */}
                <div className="delta-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Treasury Token Balance</div>
                    {balances && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-action)', fontWeight: 600 }}>
                        Live: {balances.treasury.token_balance.toLocaleString()} USDC
                      </span>
                    )}
                  </div>
                  <div className="delta-flow" style={{ marginTop: '4px' }}>
                    <span className="delta-val-before">
                      {(treasuryBase).toLocaleString()} USDC
                    </span>
                    <span>→</span>
                    <span className="delta-val-after">
                      {(treasuryPredicted).toLocaleString()} USDC
                    </span>
                  </div>
                  <span className="delta-pill outflow">
                    -{(sim.treasury_outflow / 10**6).toLocaleString()} USDC Outflow
                  </span>
                </div>

                {/* Recipient Inflow Card */}
                <div className="delta-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Recipient Token Balance</div>
                    {balances && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-text)', fontWeight: 600 }}>
                        Live: {balances.recipient.token_balance.toLocaleString()} USDC
                      </span>
                    )}
                  </div>
                  <div className="delta-flow" style={{ marginTop: '4px' }}>
                    <span className="delta-val-before">
                      {(recipientBase).toLocaleString()} USDC
                    </span>
                    <span>→</span>
                    <span className="delta-val-after">
                      {(recipientPredicted).toLocaleString()} USDC
                    </span>
                  </div>
                  <span className="delta-pill inflow">
                    +{(sim.recipient_inflow / 10**6).toLocaleString()} USDC Inflow
                  </span>
                </div>

                {/* Invariants & Slot Card */}
                <div className="delta-card">
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>Watched State Invariants</div>
                  <div style={{ marginTop: 'var(--space-2)', fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div>
                      Unexpected Gains:{' '}
                      <strong style={{ color: Object.keys(sim.unexpected_gains || {}).length === 0 ? 'var(--color-allowed)' : 'var(--color-blocked)' }}>
                        {Object.keys(sim.unexpected_gains || {}).length}
                      </strong>
                    </div>
                    <div>
                      Allowances Changed:{' '}
                      <strong style={{ color: Object.keys(sim.allowance_changes || {}).length === 0 ? 'var(--color-allowed)' : 'var(--color-blocked)' }}>
                        {Object.keys(sim.allowance_changes || {}).length}
                      </strong>
                    </div>
                    <div>
                      Implementation Slot:{' '}
                      <span className="mono-val" style={{ fontSize: '0.75rem', color: Object.keys(sim.slot_changes || {}).length === 0 ? 'var(--color-muted)' : 'var(--color-action)' }}>
                        {Object.keys(sim.slot_changes || {}).length === 0 ? '0x3608... Unchanged' : `0x3608... Updated (${Object.keys(sim.slot_changes || {}).length} change)`}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
                Simulation deltas will appear after running EVM verification.
              </div>
            )}
          </div>

          {/* Deterministic Rule Inspector */}
          <div className="card">
            <div className="card-header">
              <div>
                <span className="card-title">Deterministic Rule Evaluation</span>
                <div style={{ fontSize: '0.875rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                  Evaluates 8 deterministic rules (R1–R7, R9) guaranteeing invariant bounds.
                </div>
              </div>
              {report && <StatusMark verdict={report.verdict} compact />}
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
                          <Button
                            variant="quiet"
                            className="btn-sm"
                            onClick={() => setExpandedRule(isExpanded ? null : r.rule_id)}
                          >
                            {isExpanded ? 'Hide' : 'Details'}
                          </Button>
                        </div>
                      </div>
                      <div className="rule-expl">{r.explanation}</div>

                      {/* Expandable Evidence Details */}
                      {isExpanded && (
                        <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', backgroundColor: 'var(--color-canvas)', border: 'var(--border-width) solid var(--color-divider)', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem', fontFamily: 'var(--font-technical)' }}>
                          <div style={{ color: 'var(--color-muted)', marginBottom: '4px', fontWeight: 600 }}>Diagnostic Evidence:</div>
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--color-text)' }}>
                            {JSON.stringify(r.evidence, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
                Rule checklist evaluates deterministically during verification.
              </div>
            )}
          </div>

          {/* Cryptographic Attestation & Guarded Execution */}
          <div className="card card-raised">
            <div className="card-header">
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon name="lock" style={{ color: 'var(--color-action)' }} />
                EIP-712 Attestation &amp; Guarded Execution
              </span>
              {executionReceipt ? (
                <StatusMark verdict="EXECUTED" compact />
              ) : report?.attestation_sig ? (
                <StatusMark verdict="ATTESTED" compact />
              ) : report?.verdict === 'MISMATCH' ? (
                <StatusMark verdict="BLOCKED" compact />
              ) : (
                <span className="badge badge-neutral">Execution Gated</span>
              )}
            </div>

            {report?.attestation_sig ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-3)' }}>
                  <div>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>Verifier Address:</span>
                    <div><AddressValue address={report.verifier_address || deployments?.verifier || ''} /></div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>Attestation Deadline:</span>
                    <div className="mono-val">{report.deadline} (Chain Block Time)</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>EIP-712 Domain:</span>
                    <div className="mono-val">GuardedExecutor (v1)</div>
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>Cryptographic Signature (65-byte):</span>
                  <div><CopyValue value={report.attestation_sig} truncate={false} /></div>
                </div>

                {executionReceipt ? (
                  <div style={{ padding: 'var(--space-4)', backgroundColor: 'var(--color-allowed-surface)', border: '1px solid var(--color-allowed)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-allowed)', fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: '8px' }}>
                      <CheckCircleIcon />
                      Guarded Execution Confirmed On-Chain
                    </div>
                    <div style={{ fontSize: '0.8125rem', fontFamily: 'var(--font-technical)' }}>
                      <div>Transaction Hash: <CopyValue value={executionReceipt.tx_hash} /></div>
                      <div>Block Number: <strong>{executionReceipt.block_number}</strong></div>
                      <div>GuardedExecutor: Single-use replay protection recorded (executed[pid] = true)</div>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-2)' }}>
                    <Button
                      variant="primary"
                      onClick={() => setShowConfirmModal(true)}
                      disabled={isExecuting}
                    >
                      <Icon name="lock" />
                      <span>{isExecuting ? 'Broadcasting...' : 'Execute Transaction on Chain'}</span>
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
                {report?.verdict === 'MISMATCH' ? (
                  <span style={{ color: 'var(--color-blocked)' }}>
                    <XCircleIcon width={16} height={16} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '6px' }} />
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

      {/* Technical Inspection Drawer */}
      <TechnicalDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        report={report}
        proposalId={proposalId}
      />

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

export default ExecutionPage;

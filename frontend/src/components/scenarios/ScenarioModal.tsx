import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import type { ScenarioResult } from '../../api/types';
import { CheckCircleIcon, XCircleIcon, AlertTriangleIcon, PlayIcon, RefreshCwIcon } from '../common/Icons';
import { StatusBadge } from '../common/StatusBadge';

interface ScenarioModalProps {
  isOpen: boolean;
  initialScenario?: 'A' | 'B1' | 'B2' | 'B3' | 'C';
  onClose: () => void;
  onScenarioComplete?: (result: ScenarioResult) => void;
}

export function ScenarioModal({
  isOpen,
  initialScenario = 'A',
  onClose,
  onScenarioComplete,
}: ScenarioModalProps) {
  const [selectedScenario, setSelectedScenario] = useState<'A' | 'B1' | 'B2' | 'B3' | 'C'>(initialScenario);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chainMode, setChainMode] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      api.getChainStatus()
        .then((st) => setChainMode(st.chain_mode))
        .catch(() => setChainMode('local'));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const isProofMode = chainMode === 'proof';

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.runScenario(selectedScenario);
      setResult(res);
      if (onScenarioComplete) {
        onScenarioComplete(res);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to execute scenario');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '680px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <PlayIcon style={{ color: 'var(--accent-mint)' }} />
            <h3 className="modal-title">Scenario Runner</h3>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Scenario Selection Tabs */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: 'var(--space-4)' }}>
          <button
            type="button"
            className={`btn ${selectedScenario === 'A' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => { setSelectedScenario('A'); setResult(null); setError(null); }}
            disabled={isRunning}
          >
            Scenario A (Valid Payout)
          </button>
          <button
            type="button"
            className={`btn ${selectedScenario === 'B1' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => { setSelectedScenario('B1'); setResult(null); setError(null); }}
            disabled={isRunning}
          >
            Scenario B1 (Substituted Payout)
          </button>
          <button
            type="button"
            className={`btn ${selectedScenario === 'B3' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => { setSelectedScenario('B3'); setResult(null); setError(null); }}
            disabled={isRunning}
          >
            Scenario B3 (Evil Upgrade Blocked)
          </button>
          <button
            type="button"
            className={`btn ${selectedScenario === 'B2' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => { setSelectedScenario('B2'); setResult(null); setError(null); }}
            disabled={isRunning}
          >
            Scenario B2 (Benign Upgrade)
          </button>
          <button
            type="button"
            className={`btn ${selectedScenario === 'C' ? 'btn-danger' : 'btn-secondary'} btn-sm`}
            onClick={() => { setSelectedScenario('C'); setResult(null); setError(null); }}
            disabled={isRunning}
          >
            Scenario C (Reset &amp; Seed)
          </button>
        </div>

        {/* Scenario Description */}
        <div style={{ backgroundColor: 'var(--bg-surface)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-4)' }}>
          {selectedScenario === 'A' && (
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <strong>Scenario A:</strong> Demonstrates the intended governance lifecycle. Simulates an approved 1,000,000 USDC payout against Anvil EVM, validates all 8 deterministic rules, issues an EIP-712 attestation, and performs guarded on-chain execution through GuardedExecutor.
            </p>
          )}
          {selectedScenario === 'B1' && (
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <strong>Scenario B1:</strong> Demonstrates defense against calldata substitution. An attacker submits altered calldata redirecting funds to their address. Rule R2 identifies the mismatch against the approved manifest, strictly withholds the attestation, and execution is refused.
            </p>
          )}
          {selectedScenario === 'B3' && (
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <strong>Scenario B3 (Contested Upgrade Blocked):</strong> Voters approved a manifest declaring BoxEvil based on misleading prose. Static bytecode analysis scans runtime opcodes and discovers undeclared backdoor function selector <code>0x35faa416</code> (<code>sweep()</code>). Rule R7 triggers a MISMATCH verdict, the attestation is withheld, on-chain execution reverts, and the proxy implementation slot remains securely unchanged.
            </p>
          )}
          {selectedScenario === 'B2' && (
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              <strong>Scenario B2 (Benign Protocol Upgrade):</strong> Simulates an authorized UUPS proxy upgrade to BoxV2. Validates that all candidate selectors are declared in governance, Rule R7 passes, attestation is granted, GuardedExecutor executes the upgrade on-chain, and the proxy version advances to 2.0.0.
            </p>
          )}
          {selectedScenario === 'C' && (
            <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: '#fca5a5' }}>
              <strong>Scenario C (Reset):</strong> Clears local proposal database tables, redeploys MockToken, GovernanceRegistry, Treasury, GuardedExecutor, BoxUUPS, BoxV2, and BoxEvil to Anvil, funds Treasury with 1,000,000 USDC, and seeds proposals PROP-002 and PROP-001 clean.
            </p>
          )}
        </div>

        {/* Proof Mode Notice */}
        {isProofMode && (
          <div
            style={{
              padding: 'var(--space-3)',
              backgroundColor: 'rgba(234, 179, 8, 0.1)',
              border: '1px solid rgba(234, 179, 8, 0.3)',
              borderRadius: 'var(--radius-md)',
              marginBottom: 'var(--space-4)',
              fontSize: 'var(--text-xs)',
              color: '#facc15',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <AlertTriangleIcon width={16} height={16} />
            <span>Scenarios run locally on Anvil. Public proof runs via publish_proof.py.</span>
          </div>
        )}

        {/* Run Button */}
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={handleRun}
            disabled={isRunning || isProofMode}
          >
            {isRunning ? (
              <>
                <RefreshCwIcon className="spin" width={14} height={14} />
                Executing Scenario {selectedScenario}...
              </>
            ) : isProofMode ? (
              <>Scenario Runner Disabled in Proof Mode</>
            ) : (
              <>
                <PlayIcon width={14} height={14} />
                Run Scenario {selectedScenario}
              </>
            )}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div style={{ padding: 'var(--space-3)', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fca5a5', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
              <AlertTriangleIcon width={14} height={14} />
              Scenario Execution Error
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        )}

        {/* Execution Output */}
        {result && (
          <div style={{ backgroundColor: 'var(--bg-surface)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
              <div>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {result.name}
                </span>
                {result.outcome_classification && (
                  <div style={{ fontSize: '10px', color: result.blocked_as_expected ? '#f87171' : '#34d399', fontWeight: 600, marginTop: '2px' }}>
                    Outcome: {result.outcome_classification}
                  </div>
                )}
              </div>
              <StatusBadge status={result.verdict || (result.success ? 'VERIFIED' : 'MISMATCH')} size="sm" />
            </div>

            {/* Trace Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {result.steps.map((st, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: 'var(--text-xs)' }}>
                  {st.status === 'COMPLETED' ? (
                    <CheckCircleIcon width={14} height={14} style={{ color: '#34d399', flexShrink: 0, marginTop: 2 }} />
                  ) : (
                    <XCircleIcon width={14} height={14} style={{ color: '#f87171', flexShrink: 0, marginTop: 2 }} />
                  )}
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{st.step}: </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{st.details}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* State Deltas or Block Details */}
            {result.state_deltas && (
              <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                <div>Recipient Balance: +{result.state_deltas.human_amount || '1,000,000 USDC'}</div>
                <div>Treasury Balance: -{result.state_deltas.human_amount || '1,000,000 USDC'}</div>
                {result.execution_result && (
                  <div style={{ color: 'var(--accent-mint)', marginTop: '4px' }}>
                    Tx Hash: {result.execution_result.tx_hash.slice(0, 18)}... (Block {result.execution_result.block_number})
                  </div>
                )}
              </div>
            )}

            {/* Implementation Slot Details for Upgrade Scenarios (B2, B3) */}
            {result.slot_verified && (
              <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-2) var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                {result.slot_verified.slot_protected ? (
                  <>
                    <div style={{ color: '#34d399', fontWeight: 600 }}>EIP-1967 Slot Immutability: PROTECTED</div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Current Implementation: {result.slot_verified.current_implementation?.slice(0, 10)}... (BoxEvil rejected)
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ color: 'var(--accent-mint)', fontWeight: 600 }}>EIP-1967 Slot Upgrade: EXECUTED</div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                      New Implementation: {result.slot_verified.current_implementation?.slice(0, 10) || 'BoxV2'} · Version: {result.slot_verified.version || '2.0.0'}
                    </div>
                  </>
                )}
                {result.execution_result && (
                  <div style={{ color: 'var(--accent-mint)', marginTop: '4px' }}>
                    Tx Hash: {result.execution_result.tx_hash.slice(0, 18)}... (Block {result.execution_result.block_number})
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="modal-footer" style={{ marginTop: 'var(--space-4)' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

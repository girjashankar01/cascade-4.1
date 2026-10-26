import { useEffect, useRef } from 'react';
import type { VerificationReport } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../components/ui/Icon';
import { StatusMark } from '../../components/ui/StatusMark';

export interface TechnicalDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  report: VerificationReport | null;
  proposalId?: string;
}

export function TechnicalDrawer({ isOpen, onClose, report, proposalId }: TechnicalDrawerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      if (!dialog.open) {
        dialog.showModal();
      }
    } else {
      if (dialog.open) {
        dialog.close();
      }
    }
  }, [isOpen]);

  // Handle native cancel (Escape key)
  const handleCancel = (e: React.SyntheticEvent) => {
    e.preventDefault();
    onClose();
  };

  // Close when clicking directly on backdrop
  const handleClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      onClose();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      className="technical-drawer"
      onCancel={handleCancel}
      onClick={handleClick}
      aria-label="Technical Inspection Drawer"
    >
      <div className="drawer-header">
        <div>
          <h2 className="drawer-title">Technical Inspection</h2>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', marginTop: '2px' }}>
            Proposal {proposalId || report?.proposal_id || '—'} · Deep EVM Trace & Diagnostic Evidence
          </div>
        </div>
        <Button variant="quiet" onClick={onClose} aria-label="Close drawer">
          <Icon name="close" />
        </Button>
      </div>

      <div className="drawer-body">
        {report ? (
          <>
            {/* Verdict Overview */}
            <div className="drawer-section">
              <span className="drawer-section-title">Evaluation Verdict</span>
              <div>
                <StatusMark verdict={report.verdict} />
              </div>
            </div>

            {/* Decoded Transaction Calldata */}
            {report.decoded_tx && (
              <div className="drawer-section">
                <span className="drawer-section-title">Decoded Calldata Specification</span>
                <pre className="drawer-code-block">
                  {JSON.stringify(
                    {
                      target: report.decoded_tx.target,
                      method_name: report.decoded_tx.method_name,
                      selector: report.decoded_tx.selector,
                      value_wei: report.decoded_tx.value,
                      recipient: report.decoded_tx.recipient,
                      amount_raw: report.decoded_tx.amount_raw,
                      calldata_hash: report.decoded_tx.calldata_hash,
                      action_hash: report.decoded_tx.action_hash,
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            )}

            {/* Cryptographic Attestation */}
            <div className="drawer-section">
              <span className="drawer-section-title">EIP-712 Attestation Cryptography</span>
              <pre className="drawer-code-block">
                {JSON.stringify(
                  {
                    verifier_address: report.verifier_address,
                    deadline: report.deadline,
                    attestation_sig: report.attestation_sig || 'NOT ISSUED (BLOCKED)',
                    attested: Boolean(report.attestation_sig),
                  },
                  null,
                  2
                )}
              </pre>
            </div>

            {/* Simulation & State Deltas */}
            {report.simulation && (
              <div className="drawer-section">
                <span className="drawer-section-title">Anvil Sandbox EVM Deltas</span>
                <pre className="drawer-code-block">
                  {JSON.stringify(
                    {
                      restoration_verified: report.simulation.restoration_verified,
                      treasury_outflow: report.simulation.treasury_outflow,
                      recipient_inflow: report.simulation.recipient_inflow,
                      unexpected_gains: report.simulation.unexpected_gains,
                      allowance_changes: report.simulation.allowance_changes,
                      slot_changes: report.simulation.slot_changes,
                      logs_count: report.simulation.logs_count ?? ((report.simulation as any).logs?.length || 0),
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            )}

            {/* Complete Diagnostic Evidence Payload */}
            <div className="drawer-section">
              <span className="drawer-section-title">Raw Diagnostic Evidence</span>
              <pre className="drawer-code-block">
                {JSON.stringify(report.rules || [], null, 2)}
              </pre>
            </div>
          </>
        ) : (
          <div style={{ color: 'var(--color-muted)', padding: 'var(--space-6)', textAlign: 'center' }}>
            No verification report available for inspection. Run EVM verification first.
          </div>
        )}
      </div>

      <div style={{ marginTop: 'var(--space-6)', display: 'flex', justifyContent: 'flex-end' }}>
        <Button variant="secondary" onClick={onClose}>
          Close Inspection
        </Button>
      </div>
    </dialog>
  );
}

export default TechnicalDrawer;

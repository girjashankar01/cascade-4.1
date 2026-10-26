import type { Manifest, VerificationReport } from '../../api/types';
import { AddressValue, HashValue } from '../../components/common/CopyValue';
import { StatusMark } from '../../components/ui/StatusMark';

export interface ActionComparisonProps {
  manifest: Manifest | null;
  report: VerificationReport | null;
}

export function ActionComparison({ manifest, report }: ActionComparisonProps) {
  const action = manifest?.manifest?.action;
  const envelope = manifest?.manifest?.envelope;
  const decoded = report?.decoded_tx;
  const diff = report?.diff || {};

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="card-title">Approved Intent vs Submitted Transaction</span>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', marginTop: '2px' }}>
            Side-by-side verification of governance manifest action against live transaction bytecode
          </div>
        </div>
        {decoded && (
          <StatusMark
            status={decoded.matches_manifest ? 'VERIFIED' : 'MISMATCH'}
            compact
          />
        )}
      </div>

      <div className="comparison-grid">
        {/* Left Column: Approved Manifest Action */}
        <div className="comparison-col">
          <div className="comparison-header">
            <span>Approved Manifest Action</span>
            <span style={{ color: 'var(--color-allowed)' }}>Governance Record</span>
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
              <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                {(Number(action?.amountRaw || 0) / 10 ** (action?.decimals || 6)).toLocaleString()} USDC
              </span>{' '}
              <span style={{ color: 'var(--color-muted)' }}>({action?.amountRaw || '0'})</span>
            </span>
          </div>
          <div className="field-row">
            <span className="field-label">Outflow Envelope</span>
            <span className="field-value mono-val">
              Max: {envelope?.maxTokenOutflow?.[action?.token?.toLowerCase() || ''] || action?.amountRaw || '—'}
            </span>
          </div>
          <div className="field-row">
            <span className="field-label">Version Hash</span>
            <span className="field-value"><HashValue hash={manifest?.version_hash || ''} /></span>
          </div>
          <div className="field-row">
            <span className="field-label">Action Hash</span>
            <span className="field-value"><HashValue hash={manifest?.action_hash || ''} /></span>
          </div>
        </div>

        {/* Right Column: Submitted Transaction Calldata */}
        <div className="comparison-col">
          <div className="comparison-header">
            <span>Submitted Transaction</span>
            <span style={{ color: decoded?.is_supported ? 'var(--color-muted)' : 'var(--color-blocked)' }}>
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
                  {diff.recipient && (
                    <span style={{ color: 'var(--color-blocked)', marginLeft: '6px', fontSize: '0.75rem' }}>
                      [MISMATCH]
                    </span>
                  )}
                </span>
              </div>
              <div className={`field-row ${diff.amountRaw ? 'field-diff-alert' : ''}`}>
                <span className="field-label">Submitted Amount</span>
                <span className="field-value">
                  <span style={{ fontWeight: 600 }}>
                    {(Number(decoded.amount_raw || 0) / 10 ** (action?.decimals || 6)).toLocaleString()} USDC
                  </span>{' '}
                  <span style={{ color: 'var(--color-muted)' }}>({decoded.amount_raw})</span>
                  {diff.amountRaw && (
                    <span style={{ color: 'var(--color-blocked)', marginLeft: '6px', fontSize: '0.75rem' }}>
                      [MISMATCH]
                    </span>
                  )}
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
                  {diff.actionHash && (
                    <span style={{ color: 'var(--color-blocked)', marginLeft: '6px', fontSize: '0.75rem' }}>
                      [MISMATCH]
                    </span>
                  )}
                </span>
              </div>
            </>
          ) : (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--text-sm)' }}>
              Run EVM Verification to simulate and compare transaction calldata.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ActionComparison;

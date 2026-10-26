import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { DeploymentsInfo, Manifest, VersionRecord } from '../api/types';
import { CopyValue, HashValue, AddressValue } from '../components/common/CopyValue';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState } from '../components/common/EmptyState';
import { CheckCircleIcon, XCircleIcon, LayersIcon, ShieldIcon, RefreshCwIcon } from '../components/common/Icons';

interface ManifestPageProps {
  proposalId: string;
  manifest: Manifest | null;
  deployments: DeploymentsInfo | null;
  onRefresh: () => void;
}

export function ManifestPage({
  proposalId,
  manifest,
  deployments,
  onRefresh,
}: ManifestPageProps) {
  const [versions, setVersions] = useState<VersionRecord[]>([]);
  const [integrityReport, setIntegrityReport] = useState<any>(null);
  const [isVerifyingIntegrity, setIsVerifyingIntegrity] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchVersions = async () => {
      try {
        const vList = await api.getVersions(proposalId);
        if (isMounted) setVersions(vList);
      } catch {
        // Ignore
      }
    };
    fetchVersions();
    return () => { isMounted = false; };
  }, [proposalId]);

  const handleVerifyIntegrity = async () => {
    setIsVerifyingIntegrity(true);
    setIntegrityReport(null);
    setError(null);
    try {
      const res = await api.verifyVersionIntegrity(proposalId, {
        registry_address: deployments?.registry || undefined,
        version: manifest?.version || 1,
      });
      setIntegrityReport(res);
    } catch (err: any) {
      setError(err?.message || 'Integrity verification failed');
    } finally {
      setIsVerifyingIntegrity(false);
    }
  };

  const handleApproveOnChain = async () => {
    if (!deployments?.registry || !manifest) return;
    setIsApproving(true);
    setError(null);
    try {
      await api.approveVersion(proposalId, {
        registry_address: deployments.registry,
        version: manifest.version,
      });
      onRefresh();
      const updatedVersions = await api.getVersions(proposalId);
      setVersions(updatedVersions);
    } catch (err: any) {
      setError(err?.message || 'On-chain approve reverted');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Header */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Canonical Manifest & Governance Chain
          </div>
          <h2 style={{ margin: '4px 0 0', fontSize: 'var(--text-xl)' }}>
            Proposal {proposalId} Manifest
          </h2>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleVerifyIntegrity}
            disabled={isVerifyingIntegrity || !manifest}
          >
            <ShieldIcon width={14} height={14} />
            {isVerifyingIntegrity ? 'Checking...' : 'Verify Cryptographic Integrity'}
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleApproveOnChain}
            disabled={isApproving || !manifest || Boolean(manifest?.confirmed_at)}
          >
            <RefreshCwIcon className={isApproving ? 'spin' : ''} width={14} height={14} />
            {isApproving ? 'Approving...' : manifest?.confirmed_at ? 'Approved on Chain' : 'Approve Latest Version'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: 'var(--space-3) var(--space-4)', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', color: '#fca5a5', fontSize: 'var(--text-xs)' }}>
          {error}
        </div>
      )}

      {integrityReport && (
        <div style={{ padding: 'var(--space-4)', backgroundColor: integrityReport.verified ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', border: `1px solid ${integrityReport.verified ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`, borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: integrityReport.verified ? '#6ee7b7' : '#fca5a5', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
            {integrityReport.verified ? <CheckCircleIcon /> : <XCircleIcon />}
            {integrityReport.verified ? 'Tamper Check Passed: All commitments match stored and on-chain records.' : `Tamper Detected: ${integrityReport.error}`}
          </div>
        </div>
      )}

      {!manifest ? (
        <EmptyState
          title="No Manifest Generated"
          message={`Proposal '${proposalId}' has not yet generated a canonical manifest. Run Scenario A or confirm a manifest draft.`}
        />
      ) : (
        <>
          {/* Cryptographic Commitments Grid */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Cryptographic Hash Commitments</span>
              <StatusBadge status={manifest.status} size="sm" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 'var(--space-4)' }}>
              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>versionHash</div>
                <div style={{ marginTop: '4px' }}><HashValue hash={manifest.version_hash} /></div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>keccak256(canonical(manifest) || prevVersionHash)</div>
              </div>

              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>actionHash</div>
                <div style={{ marginTop: '4px' }}><HashValue hash={manifest.action_hash} /></div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>keccak256(abi.encode(target, value, keccak(data)))</div>
              </div>

              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>proposalTextHash</div>
                <div style={{ marginTop: '4px' }}><HashValue hash={manifest.proposal_text_hash} /></div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>keccak256(exact proposal text seen by voters)</div>
              </div>

              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>evidenceRoot</div>
                <div style={{ marginTop: '4px' }}><HashValue hash={manifest.evidence_root} /></div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>keccak256(sorted SHA-256 evidence digests)</div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)', fontSize: 'var(--text-xs)' }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Proposer Signature: </span>
                <span className="mono-val">{manifest.proposer_signature ? `${manifest.proposer_signature.slice(0, 16)}...` : 'Unsigned'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Proposer Address: </span>
                <AddressValue address={manifest.proposer_address} />
              </div>
            </div>
          </div>

          {/* Canonical Manifest JSON Inspector */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Canonical Manifest JSON (Deterministic UTF-8)</span>
              <CopyValue value={manifest.canonical_json} displayValue="Copy JSON" />
            </div>

            <pre
              style={{
                margin: 0,
                padding: 'var(--space-4)',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                lineHeight: 1.6,
                color: 'var(--text-secondary)',
                overflowX: 'auto',
              }}
            >
              {JSON.stringify(manifest.manifest, null, 2)}
            </pre>
          </div>

          {/* On-Chain Version History Chain */}
          <div className="card">
            <div className="card-header">
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LayersIcon style={{ color: 'var(--accent-mint)' }} />
                On-Chain Version Hash Chain (GovernanceRegistry)
              </span>
            </div>

            {versions.length === 0 ? (
              <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                No committed versions recorded on GovernanceRegistry for this proposal.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {versions.map((ver) => (
                  <div
                    key={ver.id}
                    style={{
                      padding: 'var(--space-3) var(--space-4)',
                      backgroundColor: 'var(--bg-surface-raised)',
                      border: `1px solid ${ver.is_approved ? 'var(--status-verified-border)' : 'var(--border-subtle)'}`,
                      borderRadius: 'var(--radius-md)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: 'var(--space-3)',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                          Version {ver.version}
                        </span>
                        {ver.is_approved ? (
                          <span className="badge badge-verified" style={{ fontSize: '10px' }}>Active Approval</span>
                        ) : (
                          <span className="badge badge-neutral" style={{ fontSize: '10px' }}>Committed Only</span>
                        )}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        versionHash: <HashValue hash={ver.version_hash} /> · prevVersionHash: <HashValue hash={ver.prev_version_hash} />
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: 'var(--text-xs)' }}>
                      {ver.commit_tx_hash && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Commit Tx: </span>
                          <CopyValue value={ver.commit_tx_hash} />
                        </div>
                      )}
                      {ver.approve_tx_hash && (
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Approve Tx: </span>
                          <CopyValue value={ver.approve_tx_hash} />
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

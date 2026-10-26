import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { Claim, Conflict, COIReport, SourceDetail, SourceMeta } from '../api/types';
import { StatusBadge } from '../components/common/StatusBadge';
import { HashValue } from '../components/common/CopyValue';
import { FileTextIcon, AlertTriangleIcon, RefreshCwIcon } from '../components/common/Icons';

interface ProposalsPageProps {
  proposalId: string;
}

export function ProposalsPage({ proposalId }: ProposalsPageProps) {
  const [sources, setSources] = useState<SourceMeta[]>([]);
  const [selectedSource, setSelectedSource] = useState<SourceDetail | null>(null);
  const [selectedPage, setSelectedPage] = useState<number>(1);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [cacheStatus, setCacheStatus] = useState<string | null>(null);
  const [coiReport, setCoiReport] = useState<COIReport | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pasteContent, setPasteContent] = useState('');
  const [pasteFilename, setPasteFilename] = useState('forum_post.txt');
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [srcList, claimsData, coiData] = await Promise.all([
        api.listSources(),
        api.getClaims(proposalId).catch(() => ({ proposal_id: proposalId, claims: [], conflicts: [], cache_status: undefined })),
        api.getCOI(proposalId).catch(() => null),
      ]);

      setSources(srcList);
      setClaims(claimsData.claims || []);
      setConflicts(claimsData.conflicts || []);
      setCacheStatus(claimsData.cache_status || null);
      setCoiReport(coiData);

      if (srcList.length > 0 && !selectedSource) {
        const detail = await api.getSourceDetail(srcList[0].id);
        setSelectedSource(detail);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load proposal evidence and claims');
    } finally {
      setIsLoading(false);
    }
  }, [proposalId, selectedSource]);

  useEffect(() => {
    let isMounted = true;

    const fetchAsync = async () => {
      if (isMounted) {
        setCoiReport(null);
        setClaims([]);
        setConflicts([]);
        setCacheStatus(null);
      }
      try {
        const [srcList, claimsData, coiData] = await Promise.all([
          api.listSources(),
          api.getClaims(proposalId).catch(() => ({ proposal_id: proposalId, claims: [], conflicts: [], cache_status: undefined })),
          api.getCOI(proposalId).catch(() => null),
        ]);
        if (!isMounted) return;
        setSources(srcList);
        setClaims(claimsData.claims || []);
        setConflicts(claimsData.conflicts || []);
        setCacheStatus(claimsData.cache_status || null);
        setCoiReport(coiData);
        if (srcList.length > 0) {
          const detail = await api.getSourceDetail(srcList[0].id);
          if (isMounted) setSelectedSource(detail);
        }
      } catch (err: any) {
        if (isMounted) setError(err?.message || 'Failed to load proposal evidence and claims');
      }
    };
    fetchAsync();
    return () => { isMounted = false; };
  }, [proposalId]);

  const handleSelectSource = async (srcId: string) => {
    try {
      const detail = await api.getSourceDetail(srcId);
      setSelectedSource(detail);
      setSelectedPage(1);
    } catch (err: any) {
      setError(err?.message || 'Failed to load source details');
    }
  };

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setError(null);
    try {
      await api.analyzeProposal(proposalId);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handlePasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pasteContent.trim()) return;
    try {
      await api.pasteSourceText(pasteContent, pasteFilename);
      setPasteContent('');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to ingest pasted source');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await api.uploadSourceFile(file);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to upload source file');
    }
  };

  const filteredClaims = filterStatus === 'ALL'
    ? claims
    : claims.filter((c) => c.status === filterStatus);

  // Active page text
  const pageText = selectedSource?.extracted_pages?.[String(selectedPage)] || '';

  // Get quotes on active page for highlighting
  const activePageQuotes = claims
    .filter((c) => c.page === selectedPage && c.status === 'GROUNDED')
    .map((c) => c.quote.toLowerCase());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Top Header */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Evidence & Claim Grounding
          </div>
          <h2 style={{ margin: '4px 0 0', fontSize: 'var(--text-xl)' }}>
            Proposal {proposalId} Evidence
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isLoading && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Loading...</span>}
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={isAnalyzing || sources.length === 0}
          >
            <RefreshCwIcon className={isAnalyzing ? 'spin' : ''} width={14} height={14} />
            {isAnalyzing ? 'Extracting Claims...' : 'Run Extraction & Grounding'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: 'var(--space-3) var(--space-4)', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', color: '#fca5a5', fontSize: 'var(--text-xs)' }}>
          {error}
        </div>
      )}

      {/* Cross-Source Conflict Banner (Crucial Requirement) */}
      {conflicts.length > 0 && (
        <div style={{ padding: 'var(--space-4)', backgroundColor: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.4)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fcd34d', fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: '8px' }}>
            <AlertTriangleIcon width={16} height={16} />
            Deterministic Conflict Detected Across Sources (Confirmation Blocked)
          </div>
          <p style={{ margin: '0 0 12px', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Contradictory evidence exists between sources. By design, the engine strictly forbids manifest confirmation when mandatory financial fields have unresolved conflicts.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {conflicts.map((conf) => (
              <div key={conf.id} style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(245, 158, 11, 0.25)', fontSize: 'var(--text-xs)' }}>
                <div style={{ fontWeight: 600, color: '#fcd34d', marginBottom: '6px' }}>
                  Field Contradiction: <code>{conf.field}</code> ({conf.display_value_a} vs {conf.display_value_b})
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Source A (Page {conf.page_a}):</span>
                    <div style={{ fontStyle: 'italic', color: 'var(--text-primary)', marginTop: '2px' }}>"{conf.quote_a}"</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Source B (Page {conf.page_b}):</span>
                    <div style={{ fontStyle: 'italic', color: 'var(--text-primary)', marginTop: '2px' }}>"{conf.quote_b}"</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Grid: Sources List & Evidence Reader */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 'var(--space-6)' }}>
        {/* Left Column: Ingested Sources & Ingest Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Evidence Sources</span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{sources.length} Total</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {sources.map((src) => {
                const isSelected = selectedSource?.id === src.id;
                return (
                  <button
                    key={src.id}
                    type="button"
                    onClick={() => handleSelectSource(src.id)}
                    style={{
                      padding: 'var(--space-3)',
                      textAlign: 'left',
                      backgroundColor: isSelected ? 'var(--bg-surface-active)' : 'var(--bg-surface-raised)',
                      border: `1px solid ${isSelected ? 'var(--accent-mint)' : 'var(--border-subtle)'}`,
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 'var(--text-xs)', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileTextIcon width={12} height={12} style={{ color: isSelected ? 'var(--accent-mint)' : 'var(--text-muted)' }} />
                      {src.filename}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Pages: {src.page_count} · {src.ocr_used ? 'OCR Fallback' : 'Native Text'}
                    </div>
                    <div style={{ marginTop: '4px' }}>
                      <HashValue hash={src.sha256} />
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Ingestion Area */}
            <div style={{ marginTop: 'var(--space-4)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-4)' }}>
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>Ingest New Evidence</span>
              <div style={{ marginTop: '8px' }}>
                <label className="btn btn-secondary btn-sm" style={{ width: '100%', justifyContent: 'center', cursor: 'pointer' }}>
                  Upload PDF / Text
                  <input type="file" accept=".pdf,.txt" style={{ display: 'none' }} onChange={handleFileUpload} />
                </label>
              </div>

              {/* Paste Text Form */}
              <form onSubmit={handlePasteSubmit} style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <input
                  type="text"
                  placeholder="Filename (e.g. forum_post.txt)"
                  value={pasteFilename}
                  onChange={(e) => setPasteFilename(e.target.value)}
                  style={{
                    backgroundColor: 'var(--bg-app)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontSize: '11px',
                    padding: '4px 6px',
                  }}
                />
                <textarea
                  placeholder="Or paste forum post / discourse discussion..."
                  value={pasteContent}
                  onChange={(e) => setPasteContent(e.target.value)}
                  style={{
                    width: '100%',
                    height: '60px',
                    backgroundColor: 'var(--bg-app)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontSize: '11px',
                    padding: '6px',
                    resize: 'none',
                    fontFamily: 'var(--font-sans)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" style={{ width: '100%' }} disabled={!pasteContent.trim()}>
                  Save Pasted Evidence
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* Right Column: Evidence Reader */}
        <div className="card">
          <div className="card-header">
            <div>
              <span className="card-title">Extracted Text Reader</span>
              {selectedSource && (
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginLeft: '12px' }}>
                  {selectedSource.filename} (Page {selectedPage} of {selectedSource.page_count})
                </span>
              )}
            </div>

            {selectedSource && selectedSource.page_count > 1 && (
              <div style={{ display: 'flex', gap: '6px' }}>
                {Array.from({ length: selectedSource.page_count }, (_, i) => i + 1).map((pg) => (
                  <button
                    key={pg}
                    type="button"
                    className={`btn btn-sm ${selectedPage === pg ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setSelectedPage(pg)}
                  >
                    Pg {pg}
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedSource ? (
            <div>
              {activePageQuotes.length > 0 && (
                <div style={{ marginBottom: '8px', fontSize: '11px', color: 'var(--accent-mint)' }}>
                  ✓ {activePageQuotes.length} Grounded claim quote(s) detected on this page.
                </div>
              )}
              <div
                style={{
                  backgroundColor: 'var(--bg-app)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: 'var(--space-4)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-xs)',
                  lineHeight: 1.7,
                  whiteSpace: 'pre-wrap',
                  color: 'var(--text-secondary)',
                  maxHeight: '400px',
                  overflowY: 'auto',
                }}
              >
                {pageText || <span style={{ color: 'var(--text-muted)' }}>No text extracted on page {selectedPage}.</span>}
              </div>
            </div>
          ) : (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
              Select a source from the left panel to inspect extracted text.
            </div>
          )}
        </div>
      </div>

      {/* Grounded Claims Table */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="card-title">Grounded Claims Checklist</span>
            {cacheStatus && (
              <span className={`badge ${cacheStatus === 'cached' ? 'badge-neutral' : 'badge-verified'}`} style={{ fontSize: '10px' }}>
                Extraction: {cacheStatus === 'cached' ? 'Cached Result' : 'Generated Now'}
              </span>
            )}
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {['ALL', 'GROUNDED', 'UNCERTAIN', 'REJECTED'].map((st) => (
              <button
                key={st}
                type="button"
                className={`btn btn-sm ${filterStatus === st ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setFilterStatus(st)}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {filteredClaims.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
            No claims matching filter '{filterStatus}'. Click 'Run Extraction & Grounding' to analyze evidence.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 'var(--text-xs)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-default)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: 'var(--space-3)' }}>Field</th>
                  <th style={{ padding: 'var(--space-3)' }}>Extracted Value</th>
                  <th style={{ padding: 'var(--space-3)' }}>Status</th>
                  <th style={{ padding: 'var(--space-3)' }}>Confidence</th>
                  <th style={{ padding: 'var(--space-3)' }}>Page</th>
                  <th style={{ padding: 'var(--space-3)' }}>Verbatim Quote</th>
                </tr>
              </thead>
              <tbody>
                {filteredClaims.map((claim) => (
                  <tr key={claim.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: 'var(--space-3)', fontWeight: 600, color: 'var(--text-primary)' }}>
                      <code>{claim.field}</code>
                    </td>
                    <td style={{ padding: 'var(--space-3)', color: 'var(--text-primary)' }}>
                      {claim.display_value}
                    </td>
                    <td style={{ padding: 'var(--space-3)' }}>
                      <StatusBadge status={claim.status} size="sm" />
                    </td>
                    <td style={{ padding: 'var(--space-3)', fontFamily: 'var(--font-mono)' }}>
                      {(claim.confidence * 100).toFixed(0)}%
                    </td>
                    <td style={{ padding: 'var(--space-3)', fontFamily: 'var(--font-mono)' }}>
                      Pg {claim.page}
                    </td>
                    <td style={{ padding: 'var(--space-3)', fontStyle: 'italic', color: 'var(--text-secondary)', maxWidth: '380px' }}>
                      "{claim.quote}"
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Conflict of Interest (COI) & Provenance Graph */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="card-title">Conflict of Interest (COI) &amp; Wallet Provenance</span>
            {coiReport?.has_linkage ? (
              <span className="badge badge-mismatch" style={{ fontSize: '10px' }}>
                Linkage Evidence Detected
              </span>
            ) : (
              <span className="badge badge-verified" style={{ fontSize: '10px' }}>
                No Direct Linkage
              </span>
            )}
          </div>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            EVM Transfer Graph &amp; Signed Disclosures <span className="badge badge-neutral" style={{ fontSize: '10px', marginLeft: '6px' }}>Seeded Demo Graph</span>
          </span>
        </div>

        {coiReport ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{
              padding: 'var(--space-2) var(--space-3)',
              backgroundColor: 'rgba(59, 130, 246, 0.08)',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11px',
              color: 'var(--text-secondary)',
              lineHeight: 1.4
            }}>
              <strong>Provenance Disclosure:</strong> This graph displays seeded demo funding fixtures illustrating on-chain transfer proximity and undisclosed funding bridges. It serves as an illustrative demonstration of proximity detection without requiring an external multi-block transaction indexer.
            </div>

            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
              {coiReport.summary}
            </div>

            {/* Path visualization */}
            {coiReport.shortest_path.length > 0 && (
              <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--bg-surface-raised)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
                  Provenance Funding Trail:
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
                  {coiReport.shortest_path.map((addr, idx) => (
                    <div key={addr} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="badge badge-neutral" style={{ padding: '4px 8px' }}>
                        {idx === 0 ? 'Proposer' : idx === coiReport.shortest_path.length - 1 ? 'Beneficiary' : 'Intermediary'}: {addr.slice(0, 8)}...{addr.slice(-6)}
                      </span>
                      {idx < coiReport.shortest_path.length - 1 && (
                        <span style={{ color: 'var(--accent-mint)', fontWeight: 'bold' }}>➔</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Undisclosed Connections List */}
            {coiReport.undisclosed_connections.length > 0 && (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Undisclosed Counterparties &amp; Associated Entities:
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                  {coiReport.undisclosed_connections.map((u, i) => (
                    <div
                      key={i}
                      style={{
                        padding: 'var(--space-3)',
                        backgroundColor: 'var(--bg-surface-raised)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: 'var(--text-xs)',
                      }}
                    >
                      <div>
                        <strong>{u.label}</strong> ({u.address.slice(0, 8)}...{u.address.slice(-6)})
                        <div style={{ color: 'var(--text-muted)', marginTop: '2px', fontSize: '11px' }}>
                          Evidence: {u.evidence}
                        </div>
                      </div>
                      <span className="badge badge-neutral" style={{ color: '#f59e0b', borderColor: '#f59e0b' }}>
                        Risk: {u.risk_score}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
            {isLoading ? 'Loading provenance graph...' : `No conflict-of-interest or undisclosed funding linkages detected for proposal ${proposalId}.`}
          </div>
        )}
      </div>
    </div>
  );
}

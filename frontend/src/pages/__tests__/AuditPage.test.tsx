import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuditPage } from '../AuditPage';
import { api } from '../../api/client';
import {
  mockPublishedProof,
  mockChainStatusHealthy,
  mockChainBalances,
} from './mockAuditFixture';

vi.mock('../../api/client', () => ({
  api: {
    getProof: vi.fn(),
    getChainStatus: vi.fn(),
    getChainBalances: vi.fn(),
    getChainTxs: vi.fn(),
    getAuditTrail: vi.fn(),
    getVerifications: vi.fn(),
  },
}));

describe('AuditPage Component Tests (Mocked Fixture)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getChainTxs).mockResolvedValue([]);
    vi.mocked(api.getAuditTrail).mockResolvedValue([]);
    vi.mocked(api.getVerifications).mockResolvedValue([]);
  });

  it('renders published proof lifecycle with 3 successes and 2 blocked transactions', async () => {
    vi.mocked(api.getProof).mockResolvedValue(mockPublishedProof);
    vi.mocked(api.getChainStatus).mockResolvedValue(mockChainStatusHealthy);
    vi.mocked(api.getChainBalances).mockResolvedValue(mockChainBalances);

    render(<AuditPage proposalId="PROP-PROOF-testrun01" />);

    // Wait for content to load
    await waitFor(() => {
      expect(screen.getByText(/On-Chain Verification Lifecycle Timeline/i)).toBeDefined();
    });

    // Check transaction steps
    expect(screen.getByText(/Proposer commits version on GovernanceRegistry/i)).toBeDefined();
    expect(screen.getByText(/Governance approves latest version on GovernanceRegistry/i)).toBeDefined();
    expect(screen.getByText(/B1 Adversarial Substitution Blocked/i)).toBeDefined();
    expect(screen.getByText(/Valid Guarded Execution/i)).toBeDefined();
    expect(screen.getByText(/Replay Attempt Blocked/i)).toBeDefined();

    // Check revert reasons
    expect(screen.getAllByText(/action mismatch/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/already executed/i).length).toBeGreaterThanOrEqual(1);

    // Check balances before and after
    expect(screen.getByText(/-1,000,000 USDC/i)).toBeDefined();
    expect(screen.getByText(/\+1,000,000 USDC/i)).toBeDefined();

    // Check export and download buttons
    expect(screen.getByText(/Download Proof Bundle/i)).toBeDefined();
    expect(screen.getByText(/Export CSV/i)).toBeDefined();

    // Check bytecode badges
    const codeBadges = screen.getAllByText(/has code/i);
    expect(codeBadges.length).toBeGreaterThanOrEqual(4);

    // Check R1 to R9 coverage table
    expect(screen.getByText(/Verification Rules Coverage Matrix \(R1 – R9\)/i)).toBeDefined();
    expect(screen.getByText(/Implementation Slot Immutability/i)).toBeDefined();
  });

  it('renders clean empty state when no proof is published yet', async () => {
    vi.mocked(api.getProof).mockResolvedValue({
      published: false,
      message: 'No proof published yet on this network.',
    });
    vi.mocked(api.getChainStatus).mockResolvedValue(mockChainStatusHealthy);
    vi.mocked(api.getChainBalances).mockResolvedValue(mockChainBalances);

    render(<AuditPage proposalId="PROP-EMPTY" />);

    await waitFor(() => {
      expect(screen.getByText(/No Public Proof Published Yet/i)).toBeDefined();
    });
    expect(screen.getAllByText(/publish_proof\.py/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/--dry-run/i)).toBeDefined();
  });

  it('renders warning alert when contracts are not deployed on target chain', async () => {
    vi.mocked(api.getProof).mockResolvedValue({ published: false });
    vi.mocked(api.getChainStatus).mockResolvedValue({
      ...mockChainStatusHealthy,
      contracts_deployed: false,
    });
    vi.mocked(api.getChainBalances).mockResolvedValue(mockChainBalances);

    render(<AuditPage proposalId="PROP-NOT-DEPLOYED" />);

    await waitFor(() => {
      expect(screen.getByText(/Contracts Not Deployed on Target Network/i)).toBeDefined();
    });
  });

  it('renders warning banner when proof chain ID mismatches connected node', async () => {
    vi.mocked(api.getProof).mockResolvedValue({
      published: false,
      proof_chain_id: 84532,
      message: 'Proof manifest was published on Base Sepolia (84532), but connected node is Sepolia (11155111).',
    });
    vi.mocked(api.getChainStatus).mockResolvedValue({
      ...mockChainStatusHealthy,
      chain_id: 11155111,
    });
    vi.mocked(api.getChainBalances).mockResolvedValue(mockChainBalances);

    render(<AuditPage proposalId="PROP-MISMATCH" />);

    await waitFor(() => {
      expect(screen.getByText(/Proof Chain Mismatch/i)).toBeDefined();
    });
    expect(screen.getByText(/Base Sepolia \(84532\)/i)).toBeDefined();
  });
});

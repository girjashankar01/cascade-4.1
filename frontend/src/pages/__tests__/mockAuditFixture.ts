/**
 * Test-only mock fixtures for AuditPage component tests.
 * STRICT ISOLATION: This fixture is test-only. It is never imported by application code,
 * never served via API, and never written to docs/proof.json or chain_txs database.
 */

import type { ChainBalancesResponse, ChainStatusResponse, ProofResponse } from '../../api/types';

export const mockPublishedProof: ProofResponse = {
  published: true,
  chain_id: 11155111,
  run_id: 'testrun01',
  pid: 'PROP-PROOF-testrun01',
  pid_b32: '0x50524f502d50524f4f462d7465737472756e3031000000000000000000000000',
  versionHash: '0x1111111111111111111111111111111111111111111111111111111111111111',
  actionHash: '0x2222222222222222222222222222222222222222222222222222222222222222',
  evidenceRoot: '0x3333333333333333333333333333333333333333333333333333333333333333',
  proposalTextHash: '0x4444444444444444444444444444444444444444444444444444444444444444',
  contracts: {
    token: { address: '0x1000000000000000000000000000000000000001', has_code: true },
    registry: { address: '0x2000000000000000000000000000000000000002', has_code: true },
    treasury: { address: '0x3000000000000000000000000000000000000003', has_code: true },
    executor: { address: '0x4000000000000000000000000000000000000004', has_code: true },
  },
  transactions: [
    {
      step: 'commit_version',
      label: 'Proposer commits version on GovernanceRegistry',
      tx_hash: '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      block_number: 6543210,
      status: 1,
      explorer_url: 'https://sepolia.etherscan.io/tx/0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      expected: 'success (status 1)',
    },
    {
      step: 'approve',
      label: 'Governance approves latest version on GovernanceRegistry',
      tx_hash: '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      block_number: 6543211,
      status: 1,
      explorer_url: 'https://sepolia.etherscan.io/tx/0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      expected: 'success (status 1)',
    },
    {
      step: 'b1_adversarial_execute',
      label: 'B1 Adversarial Substitution Blocked (action mismatch)',
      tx_hash: '0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      block_number: 6543212,
      status: 0,
      revert_reason: 'Execution reverted: action mismatch',
      explorer_url: 'https://sepolia.etherscan.io/tx/0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      expected: 'revert (action mismatch)',
    },
    {
      step: 'valid_execute',
      label: 'Valid Guarded Execution (1,000,000 USDC Payout)',
      tx_hash: '0xdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
      block_number: 6543213,
      status: 1,
      explorer_url: 'https://sepolia.etherscan.io/tx/0xdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
      expected: 'success (status 1)',
    },
    {
      step: 'replay_execute',
      label: 'Replay Attempt Blocked (already executed)',
      tx_hash: '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      block_number: 6543214,
      status: 0,
      revert_reason: 'Execution reverted: already executed',
      explorer_url: 'https://sepolia.etherscan.io/tx/0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      expected: 'revert (already executed)',
    },
  ],
  balances_before: {
    treasury_token_balance: 1_000_000 * 10**6,
    recipient_token_balance: 0,
    roles: {
      proposer: { address: '0x90F79bf6EB2c4f870365E785982E1f101E93b906', eth: 0.15 },
      governance: { address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', eth: 0.2 },
      verifier: { address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC', eth: 0.05 },
      attacker: { address: '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', eth: 0.1, token: 0 },
    },
  },
  balances_after: {
    treasury_token_balance: 0,
    recipient_token_balance: 1_000_000 * 10**6,
    roles: {
      proposer: { address: '0x90F79bf6EB2c4f870365E785982E1f101E93b906', eth: 0.148 },
      governance: { address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', eth: 0.198 },
      verifier: { address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC', eth: 0.05 },
      attacker: { address: '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', eth: 0.099, token: 0 },
    },
  },
  dryrun: {
    mode: 'dry-run, no transactions broadcast',
    pid: 'PROP-PROOF-dryrun01',
    versionHash: '0x1111111111111111111111111111111111111111111111111111111111111111',
    actionHash: '0x2222222222222222222222222222222222222222222222222222222222222222',
  },
};

export const mockChainStatusHealthy: ChainStatusResponse = {
  chain_id: 11155111,
  chain_mode: 'proof',
  rpc_connected: true,
  rpc_health: 'healthy',
  latest_block: 6543220,
  contracts_deployed: true,
  explorer_base: 'https://sepolia.etherscan.io',
  contract_addresses: {
    token: '0x1000000000000000000000000000000000000001',
    registry: '0x2000000000000000000000000000000000000002',
    treasury: '0x3000000000000000000000000000000000000003',
    executor: '0x4000000000000000000000000000000000000004',
  },
  contracts: {
    token: { address: '0x1000000000000000000000000000000000000001', has_code: true },
    registry: { address: '0x2000000000000000000000000000000000000002', has_code: true },
    treasury: { address: '0x3000000000000000000000000000000000000003', has_code: true },
    executor: { address: '0x4000000000000000000000000000000000000004', has_code: true },
  },
};

export const mockChainBalances: ChainBalancesResponse = {
  chain_id: 11155111,
  chain_mode: 'proof',
  treasury: {
    address: '0x3000000000000000000000000000000000000003',
    balance_eth: 1.5,
    token_balance_display: '1,000,000.00 USDC',
    token_balance: 1_000_000 * 10**6,
  },
  roles: {
    proposer: { address: '0x90F79bf6EB2c4f870365E785982E1f101E93b906', balance_eth: 0.15, balance_wei: 150000000000000000 },
    governance: { address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', balance_eth: 0.2, balance_wei: 200000000000000000 },
    verifier: { address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC', balance_eth: 0.05, balance_wei: 50000000000000000 },
    attacker: { address: '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', balance_eth: 0.1, balance_wei: 100000000000000000 },
  },
};

/* TypeScript domain models for DAO Accountability Engine */

export type Verdict = 'VERIFIED' | 'MISMATCH' | 'UNSUPPORTED' | 'UNCERTAIN' | 'AWAITING VERIFICATION' | 'ALREADY_EXECUTED';
export type ClaimStatus = 'GROUNDED' | 'UNCERTAIN' | 'REJECTED';
export type RuleStatus = 'PASS' | 'FAIL' | 'UNCERTAIN' | 'NOT_APPLICABLE' | 'NOT_RUN';

export interface HealthResponse {
  status: string;
  rpc_connected?: boolean;
  chain_id?: number | null;
  block_number?: number | null;
  rpc_url?: string;
}

export interface SourceMeta {
  id: string;
  sha256: string;
  filename: string;
  content_type: string;
  storage_path: string;
  page_count: number;
  ocr_used: boolean;
  created_at: string;
}

export interface SourceDetail extends SourceMeta {
  extracted_pages: Record<string, string>;
}

export interface Claim {
  id: string;
  proposal_id: string;
  field: string;
  value: string;
  display_value: string;
  quote: string;
  source_id: string;
  page: number;
  confidence: number;
  status: ClaimStatus;
  validation_details: string[];
}

export interface Conflict {
  id: string;
  proposal_id: string;
  field: string;
  value_a: string;
  display_value_a: string;
  source_id_a: string;
  quote_a: string;
  page_a: number;
  value_b: string;
  display_value_b: string;
  source_id_b: string;
  quote_b: string;
  page_b: number;
  status: string;
}

export interface ClaimsResponse {
  proposal_id: string;
  claims: Claim[];
  conflicts: Conflict[];
  cache_status?: string;
}

export interface AuditRecord {
  id: string;
  proposal_id: string;
  status: string;
  source_ids: string[];
  source_hashes: string[];
  provider: string;
  model: string;
  prompt_hash: string;
  input_hash: string;
  latency_ms: number;
  cache_status: string;
  fallback_used: boolean;
  error_code: string | null;
  error_message: string | null;
  rule_set_version: string;
  created_at: string;
}

export interface Manifest {
  manifest_id: string;
  proposal_id: string;
  version: number;
  version_hash: string;
  action_hash: string;
  proposal_text_hash: string;
  evidence_root: string;
  prev_version_hash: string;
  proposer_address: string;
  proposer_signature: string;
  canonical_json: string;
  manifest: {
    proposalId: string;
    version: number;
    action: {
      kind: string;
      token?: string;
      decimals?: number;
      recipient?: string;
      amountRaw?: string;
      proxy?: string;
      newImpl?: string;
      declaredSelectors?: string[];
      expectedImplCodeHash?: string;
    };
    envelope: {
      maxTokenOutflow: Record<string, string>;
      allowApprovals: boolean;
      allowRoleChanges: boolean;
      allowImplChange: boolean;
      allowNewContracts: boolean;
    };
    proposalTextHash: string;
    evidenceRoot: string;
    prevVersionHash: string;
  };
  status: string;
  confirmed_at: string;
}

export interface VersionRecord {
  id: string;
  proposal_id: string;
  version: number;
  version_hash: string;
  action_hash: string;
  evidence_root: string;
  prev_version_hash: string;
  commit_tx_hash: string | null;
  commit_block_number: number | null;
  committed_at: string | null;
  approve_tx_hash: string | null;
  approve_block_number: number | null;
  approved_at: string | null;
  onchain_verified: boolean;
  is_approved: boolean;
}

export interface RuleOutcome {
  rule_id: string;
  name: string;
  status: RuleStatus;
  explanation: string;
  evidence: Record<string, any>;
}

export interface DecodedTx {
  target: string;
  value: number;
  calldata?: string;
  selector: string;
  method_name: string;
  is_supported: boolean;
  token?: string;
  recipient?: string;
  spender?: string;
  amount_raw?: string;
  calldata_hash: string;
  action_hash: string;
  decoding_error?: string;
  diff: Record<string, any>;
  matches_manifest: boolean;
}

export interface SimulationResult {
  success: boolean;
  tx_status: number;
  revert_reason?: string;
  restoration_verified: boolean;
  treasury_outflow: number;
  recipient_inflow: number;
  unexpected_gains: Record<string, number>;
  allowance_changes: Record<string, any>;
  slot_changes: Record<string, any>;
  owner_changes: Record<string, any>;
  dynamic_addresses: string[];
  discovery_cap_reached: boolean;
  logs_count: number;
  baseline_state: Record<string, any>;
  post_state: Record<string, any>;
}

export interface VerificationReport {
  proposal_id: string;
  version: number;
  verdict: Verdict;
  status?: string;
  all_passed: boolean;
  rules: RuleOutcome[];
  decoded_tx: DecodedTx;
  diff: Record<string, any>;
  simulation: SimulationResult;
  attestation_sig?: string | null;
  deadline?: number | null;
  verifier_address?: string | null;
  error?: string | null;
  executed?: boolean;
  tx_hash?: string | null;
  block_number?: number | null;
}

export interface ExecutionResult {
  success: boolean;
  proposal_id: string;
  tx_hash: string;
  block_number: number;
  status: string;
}

export interface ScenarioStep {
  step: string;
  status: 'COMPLETED' | 'FAILED' | 'PENDING';
  details: string;
}

export interface ScenarioResult {
  scenario: string;
  name: string;
  proposal_id: string;
  success: boolean;
  blocked_as_expected?: boolean;
  outcome_classification?: string;
  defense_layers?: Record<string, string>;
  balances_verified?: Record<string, any>;
  verdict?: Verdict;
  steps: ScenarioStep[];
  verification_report?: VerificationReport;
  execution_result?: {
    tx_hash: string;
    block_number: number;
    status: number;
    gas_used?: number;
  } | null;
  state_deltas?: {
    token: string;
    recipient: string;
    treasury: string;
    amount_raw: string;
    human_amount: string;
    recipient_balance_before: string;
    recipient_balance_after: string;
    treasury_balance_before: string;
    treasury_balance_after: string;
  };
  slot_verified?: {
    slot_protected?: boolean;
    current_implementation?: string;
    rejected_implementation?: string;
    version?: string;
  };
  diff?: Record<string, any>;
  deployments?: Record<string, any>;
  error?: string;
}

export interface BalanceAccount {
  address: string | null;
  token_balance_raw: string;
  token_balance: number;
}

export interface BalancesInfo {
  connected: boolean;
  token_address: string | null;
  treasury: BalanceAccount;
  recipient: BalanceAccount;
  attacker: BalanceAccount;
}

export interface DeploymentsInfo {
  rpc_url: string;
  token: string | null;
  registry: string | null;
  treasury: string | null;
  executor: string | null;
  box_impl?: string | null;
  box_proxy?: string | null;
  box_v2?: string | null;
  box_evil?: string | null;
  deployer: string;
  governance: string;
  verifier: string;
  proposer: string;
  seeded_proposal_id?: string;
}

export interface WalletNode {
  address: string;
  label: string;
  category: string;
  is_declared: boolean;
}

export interface LinkEdge {
  source: string;
  target: string;
  edge_type: string;
  evidence_strength: string;
  details: string;
  amount_usd?: number | null;
  tx_hash?: string | null;
}

export interface UndisclosedConnection {
  address: string;
  label: string;
  linkage_type: string;
  evidence: string;
  risk_score: string;
}

export interface COIReport {
  proposal_id: string;
  proposer_address: string;
  recipient_address: string;
  has_linkage: boolean;
  shortest_path: string[];
  nodes: WalletNode[];
  edges: LinkEdge[];
  undisclosed_connections: UndisclosedConnection[];
  summary: string;
  is_demo_data?: boolean;
}

export interface ProofTransaction {
  step: string;
  label: string;
  tx_hash: string;
  block_number: number;
  status: number;
  explorer_url: string;
  revert_reason?: string | null;
  expected: string;
}

export interface ProofContract {
  address: string;
  explorer_url?: string;
  has_code?: boolean;
}

export interface DryRunResponse {
  mode: string;
  dry_run: boolean;
  chain_id: number;
  pid: string;
  pid_b32: string;
  versionHash: string;
  actionHash: string;
  evidenceRoot: string;
  proposalTextHash: string;
  commitments: {
    proposalTextHash: string;
    evidenceRoot: string;
    versionHash: string;
    actionHash: string;
  };
  attestation: {
    domain: Record<string, any>;
    verdict: number;
    deadline: number;
    signature: string;
    recovered_signer: string;
    expected_verifier: string;
  };
  calldata: {
    legitimate: string;
    substituted_b1: string;
  };
  balances: {
    roles: Record<string, { address: string; balance_eth: number }>;
    treasury_token_balance: number;
    recipient_token_balance: number;
  };
  timestamp: string;
}

export interface ChainStatusResponse {
  chain_id: number | null;
  latest_block: number | null;
  rpc_connected: boolean;
  rpc_health: 'healthy' | 'degraded' | 'disconnected';
  chain_mode: 'proof' | 'local';
  contracts_deployed: boolean;
  contract_addresses: {
    token?: string;
    registry?: string;
    treasury?: string;
    executor?: string;
  };
  contracts?: Record<string, {
    address: string;
    has_code: boolean;
  }>;
  explorer_base: string;
}

export interface RoleBalance {
  address: string;
  balance_wei: number | string;
  balance_eth: number;
}

export interface ChainBalancesResponse {
  chain_id: number | null;
  chain_mode: 'proof' | 'local';
  roles: {
    deployer?: RoleBalance;
    proposer?: RoleBalance;
    governance?: RoleBalance;
    verifier?: RoleBalance;
    attacker?: RoleBalance;
  };
  treasury: {
    address: string;
    balance_eth: number;
    token_balance: number;
    token_balance_display: string;
  };
}

export interface ChainTxRecord {
  id?: number;
  run_id?: string;
  step: string;
  role: string;
  from: string;
  to: string;
  tx_hash: string;
  status: 'success' | 'reverted';
  revert_reason?: string | null;
  block_number?: number | null;
  gas_used?: number | null;
  effective_gas_price?: number | null;
  fee_eth?: number | null;
  timestamp: string;
  explorer_url: string;
}

export interface ProofResponse {
  published: boolean;
  chain_id?: number | null;
  proof_chain_id?: number | null;
  run_id?: string | null;
  pid?: string | null;
  pid_b32?: string | null;
  versionHash?: string | null;
  actionHash?: string | null;
  evidenceRoot?: string | null;
  proposalTextHash?: string | null;
  commitments?: {
    proposalTextHash?: string;
    evidenceRoot?: string;
    versionHash?: string;
    actionHash?: string;
  };
  contracts?: Record<string, ProofContract>;
  transactions?: ProofTransaction[];
  balances_before?: {
    roles?: Record<string, { address: string; balance_eth?: number; eth?: number; token?: number }>;
    treasury_token_balance?: number;
    recipient_token_balance?: number;
  };
  balances_after?: {
    roles?: Record<string, { address: string; balance_eth?: number; eth?: number; token?: number }>;
    treasury_token_balance?: number;
    recipient_token_balance?: number;
  };
  dryrun?: Partial<DryRunResponse> | null;
  message?: string;
}

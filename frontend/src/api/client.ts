/* Typed API client for DAO Accountability Engine */

import type {
  AuditRecord,
  BalancesInfo,
  ClaimsResponse,
  COIReport,
  DeploymentsInfo,
  ExecutionResult,
  HealthResponse,
  Manifest,
  ScenarioResult,
  SourceDetail,
  SourceMeta,
  VerificationReport,
  VersionRecord,
  ProofResponse,
  ChainStatusResponse,
  ChainBalancesResponse,
  ChainTxRecord,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});
  
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // Use status text
    }
    throw new Error(errDetail);
  }

  return response.json();
}

export const api = {
  // Health
  getHealth: () => request<HealthResponse>('/health'),

  // Deployments & Balances
  getDeployments: () => request<DeploymentsInfo>('/deployments'),
  getBalances: (recipient?: string) => {
    const q = recipient ? `?recipient=${encodeURIComponent(recipient)}` : '';
    return request<BalancesInfo>(`/balances${q}`);
  },

  // Sources
  listSources: () => request<SourceMeta[]>('/sources'),
  getSourceDetail: (sourceId: string) => request<SourceDetail>(`/sources/${sourceId}`),
  uploadSourceFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<SourceMeta>('/sources', {
      method: 'POST',
      body: formData,
    });
  },
  pasteSourceText: (content: string, filename: string = 'pasted_source.txt') => {
    return request<SourceMeta>('/sources', {
      method: 'POST',
      body: JSON.stringify({ content, filename }),
    });
  },

  // Analysis & Claims
  analyzeProposal: (pid: string, prompt?: string, sourceIds?: string[]) => {
    return request<{ proposal_id: string; status: string }>(`/analyze/${pid}`, {
      method: 'POST',
      body: JSON.stringify({ prompt, source_ids: sourceIds }),
    });
  },
  getClaims: (pid: string) => request<ClaimsResponse>(`/claims/${pid}`),
  getCOI: (pid: string) => request<COIReport>(`/proposals/${pid}/coi`),
  getAuditTrail: (pid: string) => request<AuditRecord[]>(`/audit/${pid}`),

  // Manifests & Versions
  getManifest: (pid: string, version?: number) => {
    const query = version ? `?version=${version}` : '';
    return request<Manifest>(`/manifest/${pid}${query}`);
  },
  confirmManifest: (pid: string, payload: { token_address: string; token_decimals?: number; version?: number }) => {
    return request<Record<string, any>>(`/manifest/${pid}/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  commitVersion: (pid: string, payload: { registry_address: string; version?: number }) => {
    return request<Record<string, any>>(`/commit/${pid}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  approveVersion: (pid: string, payload: { registry_address: string; version?: number }) => {
    return request<Record<string, any>>(`/approve/${pid}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getVersions: (pid: string) => request<VersionRecord[]>(`/versions/${pid}`),
  verifyVersionIntegrity: (pid: string, payload?: { registry_address?: string; version?: number }) => {
    return request<Record<string, any>>(`/verify-version/${pid}`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  },

  // Verification & Execution
  verifyTransaction: (payload: {
    proposal_id: string;
    target: string;
    value?: number;
    data: string;
    registry_address: string;
    treasury_address: string;
    executor_address: string;
    ttl_seconds?: number;
  }) => {
    return request<VerificationReport>('/verify', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getVerifications: (pid: string) => request<VerificationReport[]>(`/verifications/${pid}`),
  executeTransaction: (payload: {
    proposal_id: string;
    target: string;
    value?: number;
    data: string;
    executor_address: string;
    registry_address?: string;
  }) => {
    return request<ExecutionResult>('/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Scenarios
  runScenario: (name: 'A' | 'B1' | 'C' | string, payload?: { rpc_url?: string }) => {
    return request<ScenarioResult>(`/scenarios/${name}/run`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  },

  // Public On-Chain Proof & Live Chain Status
  getProof: () => request<ProofResponse>('/proof'),
  getChainStatus: () => request<ChainStatusResponse>('/chain/status'),
  getChainBalances: () => request<ChainBalancesResponse>('/chain/balances'),
  getChainTxs: (runId?: string, limit: number = 50) => {
    const q = runId ? `&run_id=${encodeURIComponent(runId)}` : '';
    return request<ChainTxRecord[]>(`/chain/txs?limit=${limit}${q}`);
  },
  getChainTx: (hash: string) => request<Record<string, any>>(`/chain/tx/${encodeURIComponent(hash)}`),
};

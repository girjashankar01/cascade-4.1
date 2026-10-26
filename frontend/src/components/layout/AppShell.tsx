import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import type { BalancesInfo, DeploymentsInfo, Manifest, ScenarioResult } from '../../api/types';
import { Sidebar, type NavTab } from './Sidebar';
import { TopBar } from './TopBar';
import { OverviewPage } from '../../pages/OverviewPage';
import { ExecutionPage } from '../../pages/ExecutionPage';
import { ProposalsPage } from '../../pages/ProposalsPage';
import { ManifestPage } from '../../pages/ManifestPage';
import { AuditPage } from '../../pages/AuditPage';
import { ScenarioModal } from '../scenarios/ScenarioModal';

export function AppShell() {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [proposalId, setProposalId] = useState<string>('PROP-002');
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [deployments, setDeployments] = useState<DeploymentsInfo | null>(null);
  const [balances, setBalances] = useState<BalancesInfo | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [scenarioModalOpen, setScenarioModalOpen] = useState<boolean>(false);
  const [activeScenarioName, setActiveScenarioName] = useState<'A' | 'B1' | 'C'>('A');
  const [chainInfo, setChainInfo] = useState<{ connected: boolean; chainId: number | null; blockNumber: number | null }>({
    connected: false,
    chainId: null,
    blockNumber: null,
  });

  // Load backend health, deployments, and proposal manifest
  const refreshState = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [healthRes, depRes, balRes] = await Promise.all([
        api.getHealth().catch(() => ({ status: 'error', rpc_connected: false, chain_id: null, block_number: null })),
        api.getDeployments().catch(() => null),
        api.getBalances().catch(() => null),
      ]);

      setIsBackendHealthy(healthRes.status === 'ok');
      setChainInfo({
        connected: Boolean(healthRes.rpc_connected),
        chainId: healthRes.chain_id ?? null,
        blockNumber: healthRes.block_number ?? null,
      });
      setDeployments(depRes);
      setBalances(balRes);

      try {
        const m = await api.getManifest(proposalId);
        setManifest(m);
      } catch {
        setManifest(null);
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [proposalId]);

  useEffect(() => {
    let isCancelled = false;
    const fetchInitial = async () => {
      try {
        const [healthRes, depRes, balRes] = await Promise.all([
          api.getHealth().catch(() => ({ status: 'error', rpc_connected: false, chain_id: null, block_number: null })),
          api.getDeployments().catch(() => null),
          api.getBalances().catch(() => null),
        ]);
        if (isCancelled) return;
        setIsBackendHealthy(healthRes.status === 'ok');
        setChainInfo({
          connected: Boolean(healthRes.rpc_connected),
          chainId: healthRes.chain_id ?? null,
          blockNumber: healthRes.block_number ?? null,
        });
        setDeployments(depRes);
        setBalances(balRes);

        try {
          const m = await api.getManifest(proposalId);
          if (!isCancelled) setManifest(m);
        } catch {
          if (!isCancelled) setManifest(null);
        }
      } catch {
        // Ignore
      }
    };
    fetchInitial();
    return () => { isCancelled = true; };
  }, [proposalId]);

  const handleOpenScenario = (scenario: 'A' | 'B1' | 'C') => {
    setActiveScenarioName(scenario);
    setScenarioModalOpen(true);
  };

  const handleScenarioComplete = (result: ScenarioResult) => {
    if (result.proposal_id) {
      setProposalId(result.proposal_id);
    }
    refreshState();
    // After running Scenario A or B1, automatically switch to Execution Workbench!
    if (result.scenario === 'A' || result.scenario === 'B1') {
      setCurrentTab('execution');
    }
  };

  return (
    <div className="app-container">
      {/* Signature Animated Technical Background */}
      <div className="technical-background" aria-hidden="true">
        <div className="technical-grid" />
        <div className="technical-radial-glow" />
        <div className="technical-mask" />
        <div className="travelling-lines">
          <div className="travelling-line-h line-h1" />
          <div className="travelling-line-h line-h2" />
          <div className="travelling-line-h line-h3" />
          <div className="travelling-line-v line-v1" />
          <div className="travelling-line-v line-v2" />
        </div>
      </div>

      {/* Persistent Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        isBackendHealthy={isBackendHealthy}
        chainInfo={chainInfo}
        onSelectTab={setCurrentTab}
      />

      {/* Main Layout Area */}
      <div className="main-layout">
        <TopBar
          currentTab={currentTab}
          proposalId={proposalId}
          onSelectProposal={setProposalId}
          onRefresh={refreshState}
          onOpenScenarioModal={() => setScenarioModalOpen(true)}
          isRefreshing={isRefreshing}
          balances={balances}
        />

        <main className="content-area">
          {currentTab === 'overview' && (
            <OverviewPage
              proposalId={proposalId}
              manifest={manifest}
              deployments={deployments}
              balances={balances}
              isBackendHealthy={isBackendHealthy}
              chainInfo={chainInfo}
              onNavigate={(tab) => setCurrentTab(tab as NavTab)}
              onOpenScenario={handleOpenScenario}
            />
          )}

          {currentTab === 'execution' && (
            <ExecutionPage
              proposalId={proposalId}
              manifest={manifest}
              deployments={deployments}
              balances={balances}
              onRefresh={refreshState}
            />
          )}

          {currentTab === 'proposals' && (
            <ProposalsPage
              proposalId={proposalId}
            />
          )}

          {currentTab === 'manifest' && (
            <ManifestPage
              proposalId={proposalId}
              manifest={manifest}
              deployments={deployments}
              onRefresh={refreshState}
            />
          )}

          {currentTab === 'audit' && (
            <AuditPage
              proposalId={proposalId}
            />
          )}
        </main>
      </div>

      {/* Scenario Runner Modal */}
      <ScenarioModal
        isOpen={scenarioModalOpen}
        initialScenario={activeScenarioName}
        onClose={() => setScenarioModalOpen(false)}
        onScenarioComplete={handleScenarioComplete}
      />
    </div>
  );
}

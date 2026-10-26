import { useState, useEffect, useCallback } from 'react';
import { AddressValue } from '../common/CopyValue';

// Extend Window interface for Web3 provider detection
declare global {
  interface Window {
    ethereum?: {
      isMetaMask?: boolean;
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on?: (event: string, callback: (...args: unknown[]) => void) => void;
      removeListener?: (event: string, callback: (...args: unknown[]) => void) => void;
    };
  }
}

function getNetworkInfo(chainIdNum: number | null): { name: string; symbol: string; explorer: string } {
  switch (chainIdNum) {
    case 11155111:
      return { name: 'Ethereum Sepolia', symbol: 'ETH', explorer: 'https://sepolia.etherscan.io' };
    case 84532:
      return { name: 'Base Sepolia', symbol: 'ETH', explorer: 'https://sepolia.basescan.org' };
    case 80002:
      return { name: 'Polygon Amoy', symbol: 'POL', explorer: 'https://amoy.polygonscan.com' };
    case 31337:
      return { name: 'Local Anvil', symbol: 'ETH', explorer: '' };
    default:
      return {
        name: chainIdNum ? `Chain ${chainIdNum}` : 'Unknown Network',
        symbol: 'ETH',
        explorer: 'https://sepolia.etherscan.io',
      };
  }
}

export function ReadOnlyWalletButton() {
  const [address, setAddress] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [balance, setBalance] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [noWalletModal, setNoWalletModal] = useState(false);

  const fetchBalanceAndChain = useCallback(async (addr: string) => {
    if (!window.ethereum) return;
    try {
      const [chainIdHex, balHex] = await Promise.all([
        window.ethereum.request({ method: 'eth_chainId' }) as Promise<string>,
        window.ethereum.request({ method: 'eth_getBalance', params: [addr, 'latest'] }) as Promise<string>,
      ]);

      const cid = parseInt(chainIdHex, 16);
      setChainId(cid);

      const balWei = BigInt(balHex || '0x0');
      // Format to 4 decimal places
      const balEth = Number(balWei / BigInt(1e14)) / 10000;
      setBalance(balEth.toFixed(4));
    } catch (e) {
      console.warn('Failed to fetch wallet balance or chain ID:', e);
    }
  }, []);

  const connectWallet = async () => {
    if (!window.ethereum) {
      setNoWalletModal(true);
      return;
    }

    setIsConnecting(true);
    try {
      const accounts = (await window.ethereum.request({ method: 'eth_requestAccounts' })) as string[];
      if (accounts && accounts.length > 0) {
        const primary = accounts[0];
        setAddress(primary);
        await fetchBalanceAndChain(primary);
      }
    } catch (err: unknown) {
      console.warn('User rejected read-only wallet connection or error occurred:', err);
    } finally {
      setIsConnecting(false);
    }
  };

  const disconnectWallet = () => {
    setAddress(null);
    setChainId(null);
    setBalance(null);
    setShowModal(false);
  };

  useEffect(() => {
    if (!window.ethereum) return;

    const handleAccountsChanged = (accs: unknown) => {
      const accounts = accs as string[];
      if (accounts && accounts.length > 0) {
        setAddress(accounts[0]);
        fetchBalanceAndChain(accounts[0]);
      } else {
        disconnectWallet();
      }
    };

    const handleChainChanged = () => {
      if (address) {
        fetchBalanceAndChain(address);
      }
    };

    window.ethereum.on?.('accountsChanged', handleAccountsChanged);
    window.ethereum.on?.('chainChanged', handleChainChanged);

    return () => {
      window.ethereum?.removeListener?.('accountsChanged', handleAccountsChanged);
      window.ethereum?.removeListener?.('chainChanged', handleChainChanged);
    };
  }, [address, fetchBalanceAndChain]);

  const network = getNetworkInfo(chainId);
  const truncatedAddr = address ? `${address.slice(0, 6)}...${address.slice(-4)}` : '';

  return (
    <div style={{ position: 'relative' }}>
      {!address ? (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={connectWallet}
          disabled={isConnecting}
          title="Connect browser wallet in strictly read-only mode (no signing or transactions permitted)"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4" />
            <path d="M4 6v12c0 1.1.9 2 2 2h14v-4" />
            <path d="M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4h-4z" />
          </svg>
          <span>{isConnecting ? 'Connecting...' : 'Connect Wallet (Read-Only)'}</span>
        </button>
      ) : (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setShowModal(!showModal)}
          title="Click to view read-only wallet details"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderColor: 'var(--border-subtle)',
            background: 'rgba(124, 224, 190, 0.06)',
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: 'var(--accent-mint)',
              boxShadow: '0 0 6px var(--accent-mint)',
            }}
          />
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{network.name}</span>
          <span style={{ color: 'var(--border-default)' }}>|</span>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {balance !== null ? `${balance} ${network.symbol}` : '...'}
          </span>
          <span style={{ color: 'var(--border-default)' }}>|</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--accent-mint)' }}>
            {truncatedAddr}
          </span>
        </button>
      )}

      {/* Read-Only Details Popover Card */}
      {showModal && address && (
        <div
          className="card"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '320px',
            zIndex: 1000,
            boxShadow: '0 12px 32px rgba(0,0,0,0.6)',
            border: '1px solid var(--border-default)',
            background: '#11161d',
            padding: 'var(--space-4)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
              Read-Only Wallet Viewer
            </span>
            <span
              style={{
                fontSize: '10px',
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(56, 189, 248, 0.12)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.25)',
              }}
            >
              STRICTLY READ-ONLY
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
            <div>
              <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase' }}>Address</div>
              <AddressValue address={address} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase' }}>Network</div>
                <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{network.name}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase' }}>Balance</div>
                <div style={{ fontWeight: 600, color: 'var(--accent-mint)' }}>
                  {balance !== null ? `${balance} ${network.symbol}` : '...'}
                </div>
              </div>
            </div>

            {network.explorer && network.explorer.startsWith('http') && (
              <div style={{ marginTop: '6px' }}>
                <a
                  href={`${network.explorer}/address/${address}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: '11px',
                    color: '#38bdf8',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  View Address on Block Explorer &rarr;
                </a>
              </div>
            )}
          </div>

          <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              No private keys or write access
            </span>
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={disconnectWallet}
              style={{ padding: '3px 8px', fontSize: '11px' }}
            >
              Disconnect
            </button>
          </div>
        </div>
      )}

      {/* No Wallet Detected Helper Modal */}
      {noWalletModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
          }}
          onClick={() => setNoWalletModal(false)}
        >
          <div
            className="card"
            style={{
              width: '380px',
              maxWidth: '90vw',
              background: '#11161d',
              border: '1px solid var(--border-default)',
              boxShadow: '0 20px 40px rgba(0,0,0,0.8)',
              padding: 'var(--space-6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 8px 0', fontSize: 'var(--text-lg)', color: 'var(--text-primary)' }}>
              No Web3 Wallet Detected
            </h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', lineHeight: '1.5', margin: '0 0 16px 0' }}>
              A browser Web3 extension (like MetaMask, Rabby, or Coinbase Wallet) was not detected in your browser.
            </p>
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', lineHeight: '1.4', margin: '0 0 16px 0', background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '4px' }}>
              <strong>Notice:</strong> The DAO Accountability Engine is completely autonomous. All proof submissions and verifications run through backend and Foundry tooling. Connecting a browser wallet is optional and strictly read-only.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setNoWalletModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

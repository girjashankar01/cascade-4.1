import { useState } from 'react';
import { CopyIcon } from './Icons';

interface CopyValueProps {
  value: string;
  displayValue?: string;
  truncate?: boolean;
}

export function CopyValue({ value, displayValue, truncate = true }: CopyValueProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Ignore
    }
  };

  const formatted = displayValue || (truncate && value.length > 16 
    ? `${value.slice(0, 8)}...${value.slice(-6)}` 
    : value);

  return (
    <span className="mono-val" title={value}>
      <span>{formatted}</span>
      <button
        type="button"
        className="copy-btn"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy value to clipboard'}
        title="Copy to clipboard"
      >
        {copied ? (
          <span style={{ color: 'var(--accent-mint)', fontSize: '10px', fontWeight: 'bold' }}>✓</span>
        ) : (
          <CopyIcon />
        )}
      </button>
    </span>
  );
}

export function AddressValue({ address }: { address: string }) {
  if (!address) return <span className="mono-val">0x00...00</span>;
  return (
    <CopyValue
      value={address}
      displayValue={`${address.slice(0, 6)}...${address.slice(-4)}`}
    />
  );
}

export function HashValue({ hash }: { hash: string }) {
  if (!hash) return <span className="mono-val">0x00...00</span>;
  return (
    <CopyValue
      value={hash}
      displayValue={`${hash.slice(0, 10)}...${hash.slice(-8)}`}
    />
  );
}

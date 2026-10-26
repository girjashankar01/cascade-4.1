import { useEffect, useRef } from 'react';
import { animate, useReducedMotion } from 'motion/react';
import { getMotionDuration } from '../../design/motion';

export interface BalanceComparisonProps {
  treasuryBefore: number;
  treasuryAfter: number;
  recipientBefore: number;
  recipientAfter: number;
  tokenSymbol?: string;
}

function formatTokens(val: number, symbol: string = 'USDC'): string {
  return `${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ${symbol}`;
}

export function AnimatedBalance({
  start,
  end,
  symbol = 'USDC',
  className = '',
}: {
  start: number;
  end: number;
  symbol?: string;
  className?: string;
}) {
  const numberRef = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      if (numberRef.current) {
        numberRef.current.textContent = formatTokens(end, symbol);
      }
      return;
    }

    const duration = getMotionDuration('--motion-duration-explain') || 0.6;
    const controls = animate(0, 1000, {
      duration,
      onUpdate: (progress) => {
        if (numberRef.current) {
          const current = start + (end - start) * (progress / 1000);
          numberRef.current.textContent = formatTokens(Math.round(current), symbol);
        }
      },
      onComplete: () => {
        if (numberRef.current) {
          numberRef.current.textContent = formatTokens(end, symbol);
        }
      },
    });

    return () => controls.stop();
  }, [start, end, symbol, reduced]);

  // Largest representation to reserve width and avoid layout jitter
  const maxLabel = formatTokens(Math.max(start, end, 10000000), symbol);

  return (
    <span className={`balance-figure ${className}`} style={{ position: 'relative' }}>
      <span ref={numberRef}>{formatTokens(end, symbol)}</span>
      <span className="balance-reserve" aria-hidden="true">
        {maxLabel}
      </span>
    </span>
  );
}

export function BalanceComparison({
  treasuryBefore,
  treasuryAfter,
  recipientBefore,
  recipientAfter,
  tokenSymbol = 'USDC',
}: BalanceComparisonProps) {
  const treasuryDiff = treasuryAfter - treasuryBefore;
  const recipientDiff = recipientAfter - recipientBefore;

  return (
    <div className="balance-table" role="table" aria-label="Balance Comparison Table">
      <div className="balance-row" role="row" style={{ backgroundColor: 'var(--color-canvas)', fontWeight: 600 }}>
        <span role="columnheader">Account</span>
        <span role="columnheader">Prior State</span>
        <span role="columnheader">Predicted / Live State</span>
      </div>

      <div className="balance-row" role="row">
        <span className="balance-account" role="rowheader">Treasury</span>
        <span role="cell" style={{ color: 'var(--color-muted)', fontVariantNumeric: 'tabular-nums' }}>
          {formatTokens(treasuryBefore, tokenSymbol)}
        </span>
        <span role="cell">
          <AnimatedBalance
            start={treasuryBefore}
            end={treasuryAfter}
            symbol={tokenSymbol}
            className={treasuryDiff < 0 ? 'outflow' : ''}
          />
        </span>
      </div>

      <div className="balance-row" role="row">
        <span className="balance-account" role="rowheader">Recipient</span>
        <span role="cell" style={{ color: 'var(--color-muted)', fontVariantNumeric: 'tabular-nums' }}>
          {formatTokens(recipientBefore, tokenSymbol)}
        </span>
        <span role="cell">
          <AnimatedBalance
            start={recipientBefore}
            end={recipientAfter}
            symbol={tokenSymbol}
            className={recipientDiff > 0 ? 'inflow' : ''}
          />
        </span>
      </div>
    </div>
  );
}

export default BalanceComparison;

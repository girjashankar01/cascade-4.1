import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../ui/Button';
import { Icon } from '../ui/Icon';
import { StatusMark } from '../ui/StatusMark';
import { ThemeToggle } from '../ui/ThemeToggle';
import { BalanceComparison } from '../../features/workbench/BalanceComparison';
import { LazyLock } from '../lock/LazyLock';

describe('Design Extract Components & Theme Tests', () => {
  it('renders Button with variants and handles clicks', () => {
    let clicked = false;
    render(
      <Button variant="primary" onClick={() => { clicked = true; }}>
        Execute Guarded Payout
      </Button>
    );
    const btn = screen.getByRole('button', { name: /Execute Guarded Payout/i });
    expect(btn).toBeDefined();
    expect(btn.className).toContain('btn-primary');

    fireEvent.click(btn);
    expect(clicked).toBe(true);
  });

  it('renders Icon component with stroke and vector attributes', () => {
    const { container } = render(<Icon name="lock" size={24} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeDefined();
    expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
    expect(svg?.getAttribute('stroke-width')).toBe('1.6');
  });

  it('renders VerdictMark with plain-language text and appropriate status', () => {
    render(<StatusMark verdict="VERIFIED" />);
    expect(screen.getByText(/Verified — matched the approved plan/i)).toBeDefined();

    render(<StatusMark verdict="MISMATCH" />);
    expect(screen.getByText(/Mismatch — stopped before money moved/i)).toBeDefined();

    render(<StatusMark verdict="UNSUPPORTED" />);
    expect(screen.getByText(/Unsupported — requires manual review/i)).toBeDefined();
  });

  it('toggles theme with ThemeToggle and persists data-theme attribute', () => {
    render(<ThemeToggle />);
    const toggleBtn = screen.getByRole('button');
    expect(toggleBtn).toBeDefined();

    // Toggle theme
    fireEvent.click(toggleBtn);
    const theme1 = document.documentElement.getAttribute('data-theme');
    expect(theme1 === 'light' || theme1 === 'dark').toBe(true);

    fireEvent.click(toggleBtn);
    const theme2 = document.documentElement.getAttribute('data-theme');
    expect(theme2).not.toBe(theme1);
  });

  it('renders BalanceComparison table with tabular figures', () => {
    render(
      <BalanceComparison
        treasuryBefore={10000000}
        treasuryAfter={9000000}
        recipientBefore={0}
        recipientAfter={1000000}
        tokenSymbol="USDC"
      />
    );

    expect(screen.getByText(/Treasury/i)).toBeDefined();
    expect(screen.getByText(/Recipient/i)).toBeDefined();
  });

  it('renders LazyLock with shackle status', () => {
    render(<LazyLock engaged={true} />);
    const lock = screen.getByLabelText(/The lock is engaged|A solid metal lock with its shackle closed/i);
    expect(lock).toBeDefined();
  });
});

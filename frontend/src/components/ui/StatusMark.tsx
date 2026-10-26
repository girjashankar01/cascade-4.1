import { Icon, type IconName } from './Icon';

export type VerdictType =
  | 'VERIFIED'
  | 'MISMATCH'
  | 'UNSUPPORTED'
  | 'UNCERTAIN'
  | 'allowed'
  | 'blocked'
  | 'PASS'
  | 'FAIL'
  | 'EXECUTED'
  | 'ATTESTED'
  | 'BLOCKED'
  | string;

export interface StatusMarkProps {
  verdict?: VerdictType;
  outcome?: 'allowed' | 'blocked';
  status?: string;
  compact?: boolean;
  className?: string;
}

interface VerdictConfig {
  key: string;
  label: string;
  shortLabel: string;
  icon: IconName;
  className: string;
}

function normalizeVerdict(input?: string): VerdictConfig {
  const norm = (input || '').toUpperCase().trim();

  if (norm === 'VERIFIED' || norm === 'ALLOWED' || norm === 'PASS') {
    return {
      key: 'VERIFIED',
      label: 'Verified — matched the approved plan',
      shortLabel: 'Verified',
      icon: 'check',
      className: 'status-mark-verified',
    };
  }

  if (norm === 'MISMATCH' || norm === 'BLOCKED' || norm === 'FAIL') {
    return {
      key: 'MISMATCH',
      label: 'Mismatch — stopped before money moved',
      shortLabel: 'Mismatch',
      icon: 'stop',
      className: 'status-mark-mismatch',
    };
  }

  if (norm === 'UNSUPPORTED') {
    return {
      key: 'UNSUPPORTED',
      label: 'Unsupported — requires manual review',
      shortLabel: 'Unsupported',
      icon: 'details',
      className: 'status-mark-unsupported',
    };
  }

  if (norm === 'EXECUTED') {
    return {
      key: 'EXECUTED',
      label: 'Executed — transaction confirmed on-chain',
      shortLabel: 'Executed',
      icon: 'check',
      className: 'status-mark-verified',
    };
  }

  if (norm === 'ATTESTED') {
    return {
      key: 'ATTESTED',
      label: 'Attested — cryptographic proof issued',
      shortLabel: 'Attested',
      icon: 'lock',
      className: 'status-mark-verified',
    };
  }

  return {
    key: 'UNCERTAIN',
    label: norm ? `${norm} — check details` : 'Uncertain — check details before retry',
    shortLabel: norm || 'Uncertain',
    icon: 'result',
    className: 'status-mark-uncertain',
  };
}

export function StatusMark({
  verdict,
  outcome,
  status,
  compact = false,
  className = '',
}: StatusMarkProps) {
  const raw = verdict || (outcome === 'allowed' ? 'VERIFIED' : outcome === 'blocked' ? 'MISMATCH' : status);
  const config = normalizeVerdict(raw);

  return (
    <span
      className={`status-mark ${config.className} ${compact ? 'status-mark-compact' : ''} ${className}`}
      title={config.label}
    >
      <Icon name={config.icon} className="status-mark-icon" />
      <span className="status-mark-text">{compact ? config.shortLabel : config.label}</span>
    </span>
  );
}

export const VerdictMark = StatusMark;
export default StatusMark;
